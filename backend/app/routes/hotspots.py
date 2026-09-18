"""Hotspot endpoints. Deterministic aggregation, not prediction."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.emission import HotspotSummary, SourceBreakdown
from app.services import hotspot_service

router = APIRouter(prefix="/api/emissions", tags=["hotspots"])


@router.get("/summary", response_model=HotspotSummary)
def summary(db: Session = Depends(get_db)) -> HotspotSummary:
    return hotspot_service.build_summary(db)


@router.get("/by-source", response_model=list[SourceBreakdown])
def by_source(db: Session = Depends(get_db)) -> list[SourceBreakdown]:
    return hotspot_service.build_summary(db).by_source
