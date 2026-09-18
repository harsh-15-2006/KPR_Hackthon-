"""Operational data and source-health models.

Phase 1: the core workflow is keyed on `scope_key`, never on a facility.
Phase 2: "Factory Data" is now "Operational Data" - a record of something
         that entered the carbon system, whatever its origin.
Phase 3: SourceHealth backs the fault-tolerance layer.

`facility_id` deliberately does not appear here. Facility is an optional
attribute of the EPA reference connector only.
"""
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base

DEFAULT_SCOPE = "default"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Allowed provenance values. Kept as a plain tuple so it can be reused by
# validators and by the API schema without a circular import.
DATA_CLASSES = ("measured", "api_derived", "calculated", "demo_assumption")
VALIDATION_STATES = (
    "pending", "verified", "plausible", "needs_review", "anomalous", "rejected",
)
FRESHNESS_STATES = ("fresh", "stale", "unknown")
SUBMISSION_METHODS = ("api", "manual", "replay", "connector")


class OperationalRecord(Base):
    """One piece of data entering the carbon system.

    Duplicate protection is enforced by the database on
    (source_name, scope_key, data_type, source_timestamp) - all NOT NULL,
    so the constraint cannot be defeated by a NULL.
    """

    __tablename__ = "operational_records"
    __table_args__ = (
        UniqueConstraint(
            "source_name", "scope_key", "data_type", "source_timestamp",
            name="operational_natural_uniq",
        ),
        UniqueConstraint("payload_hash", name="operational_hash_uniq"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # --- scope: replaces facility as the partition key ---
    scope_key: Mapped[str] = mapped_column(String(128), nullable=False, default=DEFAULT_SCOPE, index=True)

    # --- provenance ---
    source_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_record_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    data_type: Mapped[str] = mapped_column(String(64), nullable=False)
    data_class: Mapped[str] = mapped_column(String(32), nullable=False)
    submission_method: Mapped[str] = mapped_column(String(32), nullable=False, default="api")

    # --- payload ---
    emission_source: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # --- timing ---
    # source_timestamp is NOT NULL so it can take part in the unique key.
    source_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # --- integrity ---
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_payload: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- state ---
    validation_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    freshness_status: Mapped[str] = mapped_column(String(16), nullable=False, default="fresh")
    trust_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class SourceHealth(Base):
    """Fault-tolerance state for one external connector.

    Status is DERIVED from observed outcomes, never hardcoded to LIVE.
    """

    __tablename__ = "source_health"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="UNAVAILABLE")
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_source_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stale_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    freshness_status: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    circuit_open_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class CachedResponse(Base):
    """Last-known-good payload per (source, cache_key), for graceful degradation.

    Serving from here is ALWAYS marked STALE. It is never presented as live.
    """

    __tablename__ = "cached_responses"
    __table_args__ = (UniqueConstraint("source_name", "cache_key", name="cache_uniq"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    cache_key: Mapped[str] = mapped_column(String(256), nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    source_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    is_good: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
