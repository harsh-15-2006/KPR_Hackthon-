"""Reduction-action library access and seeding.

Actions live in the database. They are never generated freely by a model.
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.action import ReductionAction
from app.services.demo_data import SEED_ACTIONS, SEED_DATA_SOURCE


def seed_actions_if_empty(db: Session) -> int:
    """Insert the configured action library once. Returns rows inserted."""
    existing = db.scalar(select(func.count()).select_from(ReductionAction)) or 0
    if existing > 0:
        return 0
    for row in SEED_ACTIONS:
        db.add(ReductionAction(**row, data_source=SEED_DATA_SOURCE,
                               evidence_source=SEED_DATA_SOURCE,
                               is_demo_assumption=True))
    db.commit()
    return len(SEED_ACTIONS)


def list_actions(
    db: Session,
    source: str | None = None,
    availability: str | None = None,
    search: str | None = None,
) -> list[ReductionAction]:
    stmt = select(ReductionAction)
    if source and source != "all":
        stmt = stmt.where(ReductionAction.source == source)
    if availability and availability != "all":
        stmt = stmt.where(ReductionAction.availability == availability)
    if search:
        like = "%" + search.strip().lower() + "%"
        stmt = stmt.where(
            func.lower(ReductionAction.action_name).like(like)
            | func.lower(ReductionAction.description).like(like)
        )
    stmt = stmt.order_by(ReductionAction.source, ReductionAction.action_name)
    return list(db.scalars(stmt).all())


def count_actions(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(ReductionAction)) or 0
