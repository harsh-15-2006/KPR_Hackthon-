"""SQLAlchemy engine/session wiring with a resilient startup.

Targets Supabase PostgreSQL via DATABASE_URL. If that database cannot be
reached at startup, the app does NOT crash: it logs exactly why, falls back
to a local SQLite file so every feature still works, and reports the
degraded state through /api/health.

A stack trace is never shown to the user.
"""
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import BASE_DIR, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

SQLITE_URL = f"sqlite:///{BASE_DIR / 'local_dev.db'}"


class Base(DeclarativeBase):
    pass


def _build_engine(url: str):
    connect_args = (
        {"check_same_thread": False} if url.startswith("sqlite") else {"connect_timeout": 10}
    )
    return create_engine(url, connect_args=connect_args, pool_pre_ping=True, future=True)


# Engine/session are module-level but REBINDABLE, so startup can fall back.
engine = _build_engine(settings.sqlalchemy_url)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)

# Runtime database state, surfaced by /api/health. Never contains credentials.
DB_STATE: dict[str, object] = {
    "configured": "postgres" if not settings.using_sqlite_fallback else "sqlite",
    "active": "unknown",
    "healthy": False,
    "degraded_reason": None,
}


def _probe(eng) -> tuple[bool, str | None]:
    """Cheap connectivity check. Returns (ok, first-line-of-error)."""
    try:
        with eng.connect() as c:
            c.execute(text("select 1"))
        return True, None
    except SQLAlchemyError as exc:
        detail = str(exc.__cause__ or exc).split("\n")[0]
        return False, detail[:220]
    except Exception as exc:  # noqa: BLE001 - startup must never propagate
        return False, f"{type(exc).__name__}: {str(exc).split(chr(10))[0][:200]}"


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables, falling back to SQLite if the configured DB is unreachable."""
    global engine

    problem = settings.database_url_problem
    if problem:
        _fallback(problem, log_detail=problem)
    elif settings.using_sqlite_fallback:
        DB_STATE.update(active="sqlite", healthy=True, degraded_reason=None)
    else:
        ok, detail = _probe(engine)
        if ok:
            DB_STATE.update(active="postgres", healthy=True, degraded_reason=None)
            logger.info("Connected to Postgres.")
        else:
            reason = (
                f"Could not reach the configured database ({detail}). "
                "If the host looks like db.<ref>.supabase.co, that endpoint is "
                "IPv6-only - use the Session pooler connection string instead. "
                "Running on local SQLite so the app still works."
            )
            _fallback(reason, log_detail=detail or "unknown error")

    from app.models import action, emission, operational, optimization  # noqa: F401

    try:
        Base.metadata.create_all(bind=engine)
    except SQLAlchemyError as exc:
        detail = str(exc.__cause__ or exc).split("\n")[0][:200]
        logger.error("Could not create tables: %s", detail)
        DB_STATE.update(healthy=False, degraded_reason=f"Table creation failed: {detail}")


def _fallback(reason: str, log_detail: str) -> None:
    global engine
    logger.warning("Database unavailable; falling back to SQLite. %s", log_detail)
    engine = _build_engine(SQLITE_URL)
    SessionLocal.configure(bind=engine)
    DB_STATE.update(active="sqlite", healthy=True, degraded_reason=reason)


def db_status() -> dict:
    """Database state for /api/health. Never includes credentials."""
    return dict(DB_STATE)
