"""Data Quality Review endpoints.

A human approves or rejects. The AI may explain a flag but never decides.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.emission import EmissionRecord
from app.services import trust_service as trust

router = APIRouter(prefix="/api/trust", tags=["data-trust"])


class ReviewRequest(BaseModel):
    note: str | None = Field(default=None, max_length=500)
    reviewer: str = Field(default="reviewer", max_length=64)


@router.post("/revalidate")
def revalidate(db: Session = Depends(get_db)) -> dict:
    """Re-run every check over all stored records."""
    counts = trust.revalidate_all(db)
    return {"counts": counts, "disclaimer": trust.DISCLAIMER}


@router.get("/records")
def records(
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[dict]:
    stmt = select(EmissionRecord).order_by(EmissionRecord.id.desc())
    if status and status != "all":
        stmt = stmt.where(EmissionRecord.validation_status == status)
    return [trust.record_to_dict(r) for r in db.scalars(stmt).all()]


@router.get("/summary")
def summary(db: Session = Depends(get_db)) -> dict:
    rows = db.scalars(select(EmissionRecord)).all()
    counts: dict[str, int] = {}
    for r in rows:
        counts[r.validation_status or "pending"] = counts.get(r.validation_status or "pending", 0) + 1
    scored = [r.trust_score for r in rows if r.trust_score is not None]
    held = sum(
        1 for r in rows if not trust.eligible_for_analysis(r.validation_status or "pending")
    )
    return {
        "total": len(rows),
        "counts": counts,
        "average_trust_score": round(sum(scored) / len(scored), 1) if scored else None,
        "held_for_review": held,
        "states": {
            "verified": "All checks passed.",
            "plausible": "Minor issues only; eligible for analysis.",
            "needs_review": "Inconsistent or implausible; held for a human.",
            "anomalous": "Failed a hard check; held for a human.",
        },
        "disclaimer": trust.DISCLAIMER,
    }


@router.post("/records/{record_id}/approve")
def approve(record_id: int, body: ReviewRequest, db: Session = Depends(get_db)) -> dict:
    """A HUMAN clears a flagged record. The AI cannot call this."""
    r = db.get(EmissionRecord, record_id)
    if r is None:
        raise HTTPException(status_code=404, detail=f"Record {record_id} not found.")
    r.validation_status = trust.PLAUSIBLE
    r.reviewed_by = body.reviewer
    r.reviewed_at = datetime.now(timezone.utc)
    r.review_note = body.note or "Approved after human review."
    db.commit()
    return {"id": r.id, "validation_status": r.validation_status, "reviewed_by": r.reviewed_by}


@router.post("/records/{record_id}/reject")
def reject(record_id: int, body: ReviewRequest, db: Session = Depends(get_db)) -> dict:
    """Mark as rejected. The record is kept - never silently deleted."""
    r = db.get(EmissionRecord, record_id)
    if r is None:
        raise HTTPException(status_code=404, detail=f"Record {record_id} not found.")
    r.validation_status = "rejected"
    r.reviewed_by = body.reviewer
    r.reviewed_at = datetime.now(timezone.utc)
    r.review_note = body.note or "Rejected after human review."
    db.commit()
    return {"id": r.id, "validation_status": r.validation_status, "reviewed_by": r.reviewed_by}
