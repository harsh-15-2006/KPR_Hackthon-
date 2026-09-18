"""Optimization, constraint and scenario persistence.

Every optimization run is stored with a SNAPSHOT of the actions and
constraints it used, so an old result stays reproducible even after the
action library is edited later.
"""
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BusinessConstraintRow(Base):
    __tablename__ = "business_constraints"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    constraint_type: Mapped[str] = mapped_column(String(48), nullable=False)
    emission_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    action_ids: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list
    numeric_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class OptimizationRun(Base):
    __tablename__ = "optimization_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    scope_key: Mapped[str] = mapped_column(String(128), nullable=False, default="default")
    budget: Mapped[float] = mapped_column(Float, nullable=False)
    solver: Mapped[str] = mapped_column(String(48), nullable=False, default="ortools-cpsat")
    solver_version: Mapped[str | None] = mapped_column(String(48), nullable=True)
    solver_status: Mapped[str] = mapped_column(String(24), nullable=False)
    total_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    expected_reduction: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    unused_budget: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    budget_utilization: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    objective_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    best_bound: Mapped[float | None] = mapped_column(Float, nullable=True)
    wall_time_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Snapshots make the run reproducible after the library changes.
    actions_snapshot: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    constraints_snapshot: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    constraints_applied: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    trigger_reason: Mapped[str] = mapped_column(String(64), nullable=False, default="manual")
    is_baseline: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    scenario_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class OptimizationAllocation(Base):
    __tablename__ = "optimization_allocations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("optimization_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action_name: Mapped[str] = mapped_column(String(200), nullable=False)
    emission_source: Mapped[str] = mapped_column(String(32), nullable=False)
    selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    units: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    allocated_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    expected_reduction: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    reduction_per_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class Scenario(Base):
    """A what-if. NEVER modifies the baseline."""

    __tablename__ = "scenarios"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    baseline_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    modified_budget: Mapped[float | None] = mapped_column(Float, nullable=True)
    overrides: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ReoptimizationRun(Base):
    __tablename__ = "reoptimization_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    previous_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    new_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trigger: Mapped[str] = mapped_column(String(48), nullable=False, default="manual")
    trigger_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    change_summary: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
