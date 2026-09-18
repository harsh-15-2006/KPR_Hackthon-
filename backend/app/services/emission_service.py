"""Emission calculation orchestration.

Decides between Climatiq and Demo Mode, persists the result, and always
records which one produced the number. Demo results never masquerade as
Climatiq results.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.emission import EmissionRecord
from app.schemas.emission import EmissionCalculateRequest
from app.integrations import climatiq_client
from app.services.demo_data import demo_estimate


class EmissionCalculationError(Exception):
    """User-facing calculation failure."""


def calculate_and_store(
    db: Session, payload: EmissionCalculateRequest, demo_mode: bool = False
) -> EmissionRecord:
    payload.validate_unit_for_source()

    if demo_mode:
        try:
            result = demo_estimate(
                payload.source, payload.activity_value, payload.activity_unit
            )
        except ValueError as exc:
            raise EmissionCalculationError(str(exc)) from exc
    else:
        try:
            n = climatiq_client.estimate_for_source(
                payload.source, payload.activity_value, payload.activity_unit
            )
            result = {
                "co2e": n["co2e_kg"],
                "co2e_unit": "kg",
                "emission_factor_reference": n["factor_reference"],
                "calculation_source": "climatiq",
            }
        except climatiq_client.IntegrationError as exc:
            # Never silently substitute demo numbers for a failed real call.
            raise EmissionCalculationError(exc.message) from exc

    record = EmissionRecord(
        source=payload.source,
        activity_type=payload.activity_type,
        activity_value=payload.activity_value,
        activity_unit=payload.activity_unit,
        co2e=float(result["co2e"]),
        co2e_unit=result["co2e_unit"],
        emission_factor_reference=result.get("emission_factor_reference"),
        calculation_source=result["calculation_source"],
        period=payload.period,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    # Data trust layer runs on every new record. A flagged record is stored
    # but held for human review - it never silently enters carbon analysis.
    from app.services import trust_service
    trust_service.evaluate_and_store(db, record)
    db.refresh(record)
    return record


def list_records(db: Session, source: str | None = None) -> list[EmissionRecord]:
    stmt = select(EmissionRecord).order_by(EmissionRecord.created_at.desc())
    if source:
        stmt = stmt.where(EmissionRecord.source == source)
    return list(db.scalars(stmt).all())


def delete_all(db: Session) -> int:
    records = list(db.scalars(select(EmissionRecord)).all())
    count = len(records)
    for r in records:
        db.delete(r)
    db.commit()
    return count
