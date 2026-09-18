from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ReductionAction(Base):
    """A configured reduction initiative.

    cost and expected_reduction are CONFIGURED PROJECT ASSUMPTIONS in Stage 1.
    `data_source` records where each value came from and must never be blank.
    """

    __tablename__ = "reduction_actions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    action_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_reduction: Mapped[float | None] = mapped_column(Float, nullable=True)
    implementation_time: Mapped[str | None] = mapped_column(String(64), nullable=True)
    availability: Mapped[str] = mapped_column(String(32), nullable=False, default="available")
    data_source: Mapped[str] = mapped_column(String(256), nullable=False)

    # --- optimizer inputs ---
    maximum_capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    parameter_type: Mapped[str] = mapped_column(String(16), nullable=False, default="binary")

    # --- provenance: every number must say where it came from ---
    evidence_source: Mapped[str] = mapped_column(
        Text, nullable=False, default="DEMO ASSUMPTION - prototype value, not a measurement."
    )
    source_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_demo_assumption: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # --- versioning: an edited action must not rewrite history ---
    action_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # --- dependencies / conflicts (JSON lists of action ids) ---
    requires_action_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    conflicts_with_action_ids: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
