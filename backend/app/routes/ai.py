"""AI Agent endpoint.

Gemini receives ONLY a backend-built structured context. It explains; it
never decides. If Gemini is unavailable the endpoint returns a truthful
failure AND the structured context, so the UI can still show real numbers.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai import gemini_client as gm
from app.core.config import get_settings
from app.core.fault_tolerance import health_snapshot
from app.db.session import get_db
from app.integrations.base import IntegrationError, NotConfigured
from app.services import hotspot_service
from app.services import optimization_service as opt

router = APIRouter(prefix="/api/ai", tags=["ai"])


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    include_optimization: bool = True
    include_hotspots: bool = True


def _build(db: Session, req: ChatRequest) -> dict:
    """Assemble the authoritative context. This is the model's whole world."""
    hotspots = None
    carbon = None
    if req.include_hotspots:
        try:
            s = hotspot_service.build_summary(db)
            carbon = {
                "total_co2e_kg": s.total_co2e,
                "record_count": s.record_count,
                "calculation_note": s.calculation_note,
            }
            hotspots = [
                {
                    "source": b.source, "label": b.label, "co2e_kg": b.co2e,
                    "contribution_pct": b.contribution_pct, "record_count": b.record_count,
                }
                for b in s.by_source if b.co2e > 0
            ]
        except ValueError as exc:
            carbon = {"error": str(exc)}

    optimization = None
    if req.include_optimization:
        run = opt.latest_run(db, baseline_only=True)
        if run is not None:
            optimization = opt.run_to_dict(db, run)

    return gm.build_context(
        carbon_analysis=carbon,
        hotspots=hotspots,
        optimization_result=optimization,
        source_health=health_snapshot(db),
        data_provenance=[
            {"class": "measured", "meaning": "reported by an external regulated source"},
            {"class": "api_derived", "meaning": "returned by an external API"},
            {"class": "calculated", "meaning": "computed by this system"},
            {"class": "demo_assumption", "meaning": "prototype assumption, not a measurement"},
        ],
    )


@router.post("/chat")
def chat(req: ChatRequest, db: Session = Depends(get_db)) -> dict:
    context = _build(db, req)
    settings = get_settings()
    try:
        result = gm.explain(req.question, context)
        return {
            "available": True,
            "answer": result["answer"],
            "model": result["model"],
            "context_keys": result["context_keys"],
            "disclaimer": result["disclaimer"],
            "context": context,
        }
    except (IntegrationError, NotConfigured) as exc:
        # Never fabricate an AI answer. Return the real data instead.
        return {
            "available": False,
            "answer": None,
            "model": settings.gemini_model or None,
            "error": str(exc),
            "note": (
                "The AI explanation layer is unavailable. All figures below come "
                "from the backend and OR-Tools and are unaffected."
            ),
            "context": context,
        }


@router.get("/status")
def ai_status() -> dict:
    return gm.check_availability()


@router.get("/context")
def context_preview(db: Session = Depends(get_db)) -> dict:
    """Exactly what the AI would be given. Useful for auditing grounding."""
    return _build(db, ChatRequest(question="preview"))
