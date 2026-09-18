from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EmissionRecord(Base):
    """One calculated CO2e result for one activity entry."""

    __tablename__ = "emission_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    activity_type: Mapped[str] = mapped_column(String(128), nullable=False)
    activity_value: Mapped[float] = mapped_column(Float, nullable=False)
    activity_unit: Mapped[str] = mapped_column(String(32), nullable=False)
    co2e: Mapped[float] = mapped_column(Float, nullable=False)
    co2e_unit: Mapped[str] = mapped_column(String(16), nullable=False, default="kg")
    emission_factor_reference: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # "climatiq" or "demo" -- provenance is never hidden from the user.
    calculation_source: Mapped[str] = mapped_column(String(32), nullable=False)
    period: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # --- data trust layer ---
    validation_status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    trust_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    triggered_rules: Mapped[str | None] = mapped_column(Text, nullable=True)   # JSON list
    reviewed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
