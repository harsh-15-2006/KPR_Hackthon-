"""FastAPI entrypoint. Route logic lives in app/routes, never here."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import SessionLocal, db_status, init_db
from app.routes import actions, ai, auth, emissions, hotspots, optimization, reports, trust
from app.services.action_service import seed_actions_if_empty

settings = get_settings()

# Install the JSON formatter with secret redaction BEFORE anything can log.
# Without this call the redaction filter is dead code and a stray
# logger.info(payload) could print an API key.
configure_logging(settings.log_level)

logger = logging.getLogger("carbon_intelligence")


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Create tables and seed the action library once, at startup.

    Startup must NEVER crash on an external dependency. Any failure is
    logged as a single readable line and the app continues in a degraded
    but honest state.
    """
    try:
        init_db()
    except Exception:  # noqa: BLE001 - startup must not propagate a traceback
        logger.exception("init_db failed")

    try:
        db = SessionLocal()
        try:
            inserted = seed_actions_if_empty(db)
            if inserted:
                logger.info("Seeded %s reduction actions.", inserted)
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not seed reduction actions: %s", type(exc).__name__)
    problem = settings.database_url_problem
    if problem:
        # Malformed is NOT the same as blank - say which it is.
        logger.warning("DATABASE_URL is misconfigured, falling back to SQLite. %s", problem)
    elif settings.using_sqlite_fallback:
        logger.warning(
            "DATABASE_URL is blank - using a local SQLite file. "
            "Set DATABASE_URL to your Supabase connection string for Postgres."
        )
    if not settings.climatiq_configured:
        logger.warning("CLIMATIQ_API_KEY is not set - Demo Mode only.")
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Industrial Carbon Intelligence - Stage 1",
    description=(
        "Stage 1: multi-source emission calculation, hotspot identification, "
        "and a configured reduction-action library. Optimization is Stage 2."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(emissions.router)
app.include_router(hotspots.router)
app.include_router(actions.router)
app.include_router(optimization.router)
app.include_router(ai.router)
app.include_router(reports.router)
app.include_router(trust.router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Never leak a stack trace to the client."""
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected server error occurred. Please try again."},
    )


@app.get("/api/health")
def health() -> dict:
    """Service state. Reports booleans and status strings only - never a key."""
    db = db_status()
    return {
        "status": "ok" if db.get("healthy") else "degraded",
        "database": db,
        "integrations": settings.integration_status(),
        "notes": {
            "epa": "Optional reference connector - US power-sector scope only.",
            "electricity_maps": "Grid carbon intensity, not facility consumption.",
            "climatiq": "Activity data -> emission factor calculation.",
            "gemini": "Explanation layer only; never performs optimization.",
            "supabase_rest": "Optional PostgREST keys. Postgres persistence is reported under 'database'.",
        },
    }
