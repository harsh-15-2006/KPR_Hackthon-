"""Hotspot endpoints. Deterministic aggregation, not prediction."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import resolve_scope
from app.db.session import get_db
from app.schemas.emission import HotspotSummary, SourceBreakdown
from app.services import hotspot_service

router = APIRouter(prefix="/api/emissions", tags=["hotspots"])


@router.get("/summary", response_model=HotspotSummary)
def summary(
    db: Session = Depends(get_db), scope: str = Depends(resolve_scope)
) -> HotspotSummary:
    return hotspot_service.build_summary(db, scope_key=scope)


@router.get("/by-source", response_model=list[SourceBreakdown])
def by_source(
    db: Session = Depends(get_db), scope: str = Depends(resolve_scope)
) -> list[SourceBreakdown]:
    return hotspot_service.build_summary(db, scope_key=scope).by_source
