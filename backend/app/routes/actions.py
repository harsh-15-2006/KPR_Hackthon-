"""Reduction-action library and business-constraint endpoints.

Every action carries `evidence_source` and `is_demo_assumption`. A value
with no stated origin cannot be created - the API rejects a blank
evidence_source rather than letting an unattributed number into the system.
"""
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.action import ReductionAction
from app.models.optimization import BusinessConstraintRow
from app.utils.sources import SOURCES, is_valid_source

router = APIRouter(prefix="/api", tags=["library"])

CONSTRAINT_TYPES = (
    "max_actions_per_source", "mutually_exclusive", "required_action",
    "max_total_actions", "max_spend_per_source",
)


# ------------------------------------------------------------ schemas


class ActionIn(BaseModel):
    action_name: str = Field(..., min_length=1, max_length=200)
    source: str
    description: str = ""
    cost: float | None = Field(default=None, ge=0)
    expected_reduction: float | None = Field(default=None, ge=0)
    maximum_capacity: int = Field(default=1, ge=1)
    parameter_type: str = Field(default="binary")
    implementation_time: str | None = None
    availability: str = Field(default="available")
    evidence_source: str = Field(..., min_length=3)
    source_url: str | None = None
    is_demo_assumption: bool = True
    requires_action_ids: list[str] = Field(default_factory=list)
    conflicts_with_action_ids: list[str] = Field(default_factory=list)

    @field_validator("source")
    @classmethod
    def _src(cls, v: str) -> str:
        v = v.strip().lower()
        if not is_valid_source(v):
            raise ValueError(f"Unsupported source '{v}'. Supported: {', '.join(SOURCES)}")
        return v

    @field_validator("parameter_type")
    @classmethod
    def _pt(cls, v: str) -> str:
        if v not in ("binary", "integer"):
            raise ValueError("parameter_type must be 'binary' or 'integer'")
        return v

    @field_validator("availability")
    @classmethod
    def _av(cls, v: str) -> str:
        if v not in ("available", "limited", "unavailable"):
            raise ValueError("availability must be available, limited or unavailable")
        return v


class ActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    action_name: str
    source: str
    description: str
    cost: float | None
    expected_reduction: float | None
    maximum_capacity: int
    parameter_type: str
    implementation_time: str | None
    availability: str
    data_source: str
    evidence_source: str
    source_url: str | None
    is_demo_assumption: bool
    action_version: int
    created_at: datetime
    updated_at: datetime


class ConstraintIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=160)
    constraint_type: str
    emission_source: str | None = None
    action_ids: list[str] = Field(default_factory=list)
    numeric_value: float | None = None
    is_active: bool = True
    description: str | None = None

    @field_validator("constraint_type")
    @classmethod
    def _ct(cls, v: str) -> str:
        if v not in CONSTRAINT_TYPES:
            raise ValueError(f"constraint_type must be one of: {', '.join(CONSTRAINT_TYPES)}")
        return v


# ------------------------------------------------------------ actions


def _to_out(r: ReductionAction) -> ActionOut:
    return ActionOut.model_validate(r)


@router.get("/actions", response_model=list[ActionOut])
def list_actions(
    source: str | None = Query(default=None),
    availability: str | None = Query(default=None),
    search: str | None = Query(default=None),
    sort: str = Query(default="source"),
    db: Session = Depends(get_db),
) -> list[ActionOut]:
    stmt = select(ReductionAction)
    if source and source != "all":
        if not is_valid_source(source):
            raise HTTPException(status_code=422, detail=f"Unknown source '{source}'.")
        stmt = stmt.where(ReductionAction.source == source)
    if availability and availability != "all":
        stmt = stmt.where(ReductionAction.availability == availability)
    if search:
        like = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            func.lower(ReductionAction.action_name).like(like)
            | func.lower(ReductionAction.description).like(like)
        )
    order = {
        "source": (ReductionAction.source, ReductionAction.action_name),
        "cost": (ReductionAction.cost,),
        "reduction": (ReductionAction.expected_reduction.desc(),),
        "name": (ReductionAction.action_name,),
    }.get(sort, (ReductionAction.source, ReductionAction.action_name))
    return [_to_out(r) for r in db.scalars(stmt.order_by(*order)).all()]


@router.get("/actions/count")
def count(db: Session = Depends(get_db)) -> dict:
    total = db.scalar(select(func.count()).select_from(ReductionAction)) or 0
    demo = db.scalar(
        select(func.count()).select_from(ReductionAction)
        .where(ReductionAction.is_demo_assumption.is_(True))
    ) or 0
    return {"count": total, "demo_assumptions": demo}


@router.post("/actions", response_model=ActionOut, status_code=201)
def create_action(payload: ActionIn, db: Session = Depends(get_db)) -> ActionOut:
    exists = db.scalar(
        select(ReductionAction).where(
            ReductionAction.action_name == payload.action_name,
            ReductionAction.source == payload.source,
        )
    )
    if exists:
        raise HTTPException(
            status_code=409,
            detail=f"An action named '{payload.action_name}' already exists for {payload.source}.",
        )
    row = ReductionAction(
        action_name=payload.action_name,
        source=payload.source,
        description=payload.description,
        cost=payload.cost,
        expected_reduction=payload.expected_reduction,
        maximum_capacity=payload.maximum_capacity,
        parameter_type=payload.parameter_type,
        implementation_time=payload.implementation_time,
        availability=payload.availability,
        evidence_source=payload.evidence_source,
        source_url=payload.source_url,
        is_demo_assumption=payload.is_demo_assumption,
        data_source=payload.evidence_source,
        requires_action_ids=json.dumps(payload.requires_action_ids),
        conflicts_with_action_ids=json.dumps(payload.conflicts_with_action_ids),
        effective_from=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_out(row)


@router.put("/actions/{action_id}", response_model=ActionOut)
def update_action(action_id: int, payload: ActionIn, db: Session = Depends(get_db)) -> ActionOut:
    row = db.get(ReductionAction, action_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Action {action_id} not found.")
    for f in (
        "action_name", "source", "description", "cost", "expected_reduction",
        "maximum_capacity", "parameter_type", "implementation_time", "availability",
        "evidence_source", "source_url", "is_demo_assumption",
    ):
        setattr(row, f, getattr(payload, f))
    row.data_source = payload.evidence_source
    row.requires_action_ids = json.dumps(payload.requires_action_ids)
    row.conflicts_with_action_ids = json.dumps(payload.conflicts_with_action_ids)
    # Editing bumps the version. Past optimization runs keep their snapshot.
    row.action_version = (row.action_version or 1) + 1
    row.effective_from = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return _to_out(row)


@router.delete("/actions/{action_id}")
def delete_action(action_id: int, db: Session = Depends(get_db)) -> dict:
    row = db.get(ReductionAction, action_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Action {action_id} not found.")
    name = row.action_name
    db.delete(row)
    db.commit()
    return {"deleted": action_id, "action_name": name}


# -------------------------------------------------------- constraints


@router.get("/constraints")
def list_constraints(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(BusinessConstraintRow).order_by(BusinessConstraintRow.name)).all()
    return [
        {
            "id": r.id, "name": r.name, "constraint_type": r.constraint_type,
            "emission_source": r.emission_source,
            "action_ids": json.loads(r.action_ids) if r.action_ids else [],
            "numeric_value": r.numeric_value, "is_active": r.is_active,
            "description": r.description,
        }
        for r in rows
    ]


@router.post("/constraints", status_code=201)
def create_constraint(payload: ConstraintIn, db: Session = Depends(get_db)) -> dict:
    if db.scalar(select(BusinessConstraintRow).where(BusinessConstraintRow.name == payload.name)):
        raise HTTPException(status_code=409, detail=f"Constraint '{payload.name}' already exists.")
    row = BusinessConstraintRow(
        name=payload.name, constraint_type=payload.constraint_type,
        emission_source=payload.emission_source,
        action_ids=json.dumps(payload.action_ids),
        numeric_value=payload.numeric_value, is_active=payload.is_active,
        description=payload.description,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "name": row.name, "constraint_type": row.constraint_type}


@router.put("/constraints/{cid}")
def update_constraint(cid: int, payload: ConstraintIn, db: Session = Depends(get_db)) -> dict:
    row = db.get(BusinessConstraintRow, cid)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Constraint {cid} not found.")
    row.name = payload.name
    row.constraint_type = payload.constraint_type
    row.emission_source = payload.emission_source
    row.action_ids = json.dumps(payload.action_ids)
    row.numeric_value = payload.numeric_value
    row.is_active = payload.is_active
    row.description = payload.description
    db.commit()
    return {"id": row.id, "name": row.name, "is_active": row.is_active}


@router.delete("/constraints/{cid}")
def delete_constraint(cid: int, db: Session = Depends(get_db)) -> dict:
    row = db.get(BusinessConstraintRow, cid)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Constraint {cid} not found.")
    db.delete(row)
    db.commit()
    return {"deleted": cid}
