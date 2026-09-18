"""Optimization, What-If and Re-optimization endpoints.

OR-Tools CP-SAT is authoritative here. No AI participates.
"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import resolve_scope
from app.db.session import get_db
from app.services import optimization_service as opt

router = APIRouter(prefix="/api", tags=["optimization"])


class OptimizeRequest(BaseModel):
    budget: float = Field(..., ge=0, description="Sustainability budget (INR lakh)")
    scope_key: str = Field(default="default", max_length=128)
    trigger_reason: str = Field(default="manual", max_length=64)


class ScenarioRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=160)
    budget: float | None = Field(default=None, ge=0)
    # {action_id: {cost?, expected_reduction?, availability?, maximum_capacity?}}
    action_overrides: dict[str, dict[str, Any]] = Field(default_factory=dict)
    extra_constraints: list[dict[str, Any]] = Field(default_factory=list)
    notes: str | None = None


class ReoptimizeRequest(BaseModel):
    budget: float | None = Field(default=None, ge=0)
    trigger: str = Field(default="manual", max_length=48)
    trigger_detail: str | None = None


@router.post("/optimization/run")
def run_optimization(
    payload: OptimizeRequest,
    db: Session = Depends(get_db),
    scope: str = Depends(resolve_scope),
) -> dict:
    """Solve the budget-constrained allocation. Persists every run."""
    if scope == "__ALL__":
        raise HTTPException(
            status_code=400, detail="Select a company before running an optimization."
        )
    run = opt.run_optimization(
        db,
        budget=payload.budget,
        scope_key=scope,
        trigger_reason=payload.trigger_reason,
        is_baseline=True,
    )
    return opt.run_to_dict(db, run)


@router.get("/optimization/latest")
def latest(
    db: Session = Depends(get_db), scope: str = Depends(resolve_scope)
) -> dict:
    run = opt.latest_run(db, baseline_only=True, scope_key=scope)
    if run is None:
        return {"run_id": None, "message": "No optimization has been run yet."}
    return opt.run_to_dict(db, run)


@router.get("/optimization/{run_id}")
def get_run(run_id: int, db: Session = Depends(get_db)) -> dict:
    run = opt.get_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Optimization run {run_id} not found.")
    return opt.run_to_dict(db, run)


# ----------------------------------------------------------- what-if


@router.post("/scenarios")
def create_scenario(payload: ScenarioRequest, db: Session = Depends(get_db)) -> dict:
    """Run an independent optimization. The baseline is never modified."""
    return opt.create_scenario(
        db,
        name=payload.name,
        budget=payload.budget,
        overrides=payload.action_overrides,
        extra_constraints=payload.extra_constraints,
        notes=payload.notes,
    )


# --------------------------------------------------- re-optimization


@router.post("/reoptimization/run")
def reoptimize(payload: ReoptimizeRequest, db: Session = Depends(get_db)) -> dict:
    return opt.reoptimize(
        db, budget=payload.budget, trigger=payload.trigger, trigger_detail=payload.trigger_detail
    )


@router.get("/reoptimization/history")
def history(limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db)) -> list:
    return opt.reoptimization_history(db, limit)


@router.get("/reoptimization/status")
def status(db: Session = Depends(get_db)) -> dict:
    latest_run = opt.latest_run(db, baseline_only=True)
    hist = opt.reoptimization_history(db, 1)
    return {
        "last_optimization_at": (
            latest_run.created_at.isoformat() if latest_run and latest_run.created_at else None
        ),
        "last_optimization_run_id": latest_run.id if latest_run else None,
        "last_reoptimization": hist[0] if hist else None,
    }
