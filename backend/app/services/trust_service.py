"""Data Trust layer.

Runs deterministic checks over an emission record and assigns a trust
score and a state. Records that look implausible are HELD FOR HUMAN
REVIEW rather than silently entering carbon analysis.

WHAT THIS IS NOT:
    This is not fraud proof. It cannot show that a figure is true, and it
    never declares a company fraudulent. It flags records that are
    inconsistent, implausible or unattributed, and routes them to a person.
"""
import json
import statistics
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.emission import EmissionRecord

logger = get_logger(__name__)

VERIFIED, PLAUSIBLE, NEEDS_REVIEW, ANOMALOUS = (
    "verified", "plausible", "needs_review", "anomalous",
)

DISCLAIMER = (
    "The data trust layer flags inconsistent or implausible records for human "
    "review. It does NOT prove a value is true and never alleges fraud."
)

# Plausible CO2e per unit of activity, used only as an ORDER-OF-MAGNITUDE
# sanity band. Values outside it are flagged for review, never rejected
# outright or silently corrected.
INTENSITY_BANDS: dict[str, tuple[float, float, str]] = {
    "electricity": (0.05, 2.0, "kg CO2e per kWh"),
    "fuel": (0.5, 5.0, "kg CO2e per litre"),
    "logistics": (0.005, 2.0, "kg CO2e per t-km"),
    "production": (50.0, 5000.0, "kg CO2e per tonne"),
    "waste": (5.0, 2000.0, "kg CO2e per tonne"),
}

# Each failed rule subtracts from a starting score of 100.
PENALTY = {
    "schema_range": 40,
    "intensity_benchmark": 25,
    "historical_trend": 20,
    "cross_source": 15,
    "provenance": 15,
    "duplicate": 35,
}


def _norm_unit(source: str, value: float, unit: str) -> float | None:
    """Activity value in the band's base unit, or None if not comparable."""
    u = (unit or "").strip().lower()
    table = {
        "electricity": {"kwh": 1.0, "mwh": 1000.0},
        "fuel": {"l": 1.0, "kg": 1.0, "m3": 1000.0},
        "logistics": {"t.km": 1.0, "t-km": 1.0, "km": 1.0},
        "production": {"t": 1.0, "kg": 0.001},
        "waste": {"t": 1.0, "kg": 0.001},
    }.get(source, {})
    factor = table.get(u)
    return None if factor is None else value * factor


def evaluate(db: Session, record: EmissionRecord) -> dict[str, Any]:
    """Run every check. Returns status, score and the rules that fired."""
    rules: list[dict[str, Any]] = []
    score = 100.0

    def fire(rule: str, detail: str, severity: str = "warning") -> None:
        nonlocal score
        score -= PENALTY.get(rule, 10)
        rules.append({"rule": rule, "detail": detail, "severity": severity})

    # 1. schema / range ----------------------------------------------------
    if record.activity_value is None or record.activity_value <= 0:
        fire("schema_range", "Activity value is missing or not positive.", "error")
    if record.co2e is None or record.co2e < 0:
        fire("schema_range", "CO2e is missing or negative.", "error")

    # 2. intensity benchmark ----------------------------------------------
    band = INTENSITY_BANDS.get(record.source)
    intensity = None
    if band and record.activity_value and record.co2e is not None:
        base = _norm_unit(record.source, record.activity_value, record.activity_unit)
        if base and base > 0:
            intensity = record.co2e / base
            lo, hi, label = band
            if intensity < lo:
                fire(
                    "intensity_benchmark",
                    f"Implied intensity {intensity:.4f} {label} is below the plausible "
                    f"range {lo}-{hi}. Emissions may be understated.",
                )
            elif intensity > hi:
                fire(
                    "intensity_benchmark",
                    f"Implied intensity {intensity:.4f} {label} is above the plausible "
                    f"range {lo}-{hi}. Emissions may be overstated.",
                )

    # 3. historical trend --------------------------------------------------
    peers = db.scalars(
        select(EmissionRecord)
        .where(EmissionRecord.source == record.source, EmissionRecord.id != record.id)
        .order_by(EmissionRecord.created_at.desc())
        .limit(30)
    ).all()
    peer_vals = [p.co2e for p in peers if p.co2e is not None and p.co2e > 0]
    if len(peer_vals) >= 3 and record.co2e:
        med = statistics.median(peer_vals)
        if med > 0:
            ratio = record.co2e / med
            if ratio > 5 or ratio < 0.2:
                fire(
                    "historical_trend",
                    f"CO2e {record.co2e:.0f} kg is {ratio:.1f}x the median of the last "
                    f"{len(peer_vals)} {record.source} records ({med:.0f} kg).",
                )

    # 4. cross-source consistency -----------------------------------------
    if record.source == "electricity" and intensity is not None:
        grid = db.scalars(
            select(EmissionRecord).where(EmissionRecord.source == "electricity").limit(50)
        ).all()
        others = [
            r.co2e / (_norm_unit("electricity", r.activity_value, r.activity_unit) or 1)
            for r in grid
            if r.id != record.id and r.activity_value and r.co2e is not None
        ]
        others = [o for o in others if o > 0]
        if len(others) >= 3:
            m = statistics.median(others)
            if m > 0 and (intensity / m > 3 or intensity / m < 0.33):
                fire(
                    "cross_source",
                    f"Grid intensity {intensity:.3f} disagrees with other electricity "
                    f"records (median {m:.3f} kg/kWh).",
                )

    # 5. provenance --------------------------------------------------------
    if not record.calculation_source:
        fire("provenance", "No calculation source recorded.", "error")
    elif record.calculation_source == "demo":
        rules.append({
            "rule": "provenance",
            "detail": "Value produced in Demo Mode - an illustrative assumption, not a measurement.",
            "severity": "info",
        })
    if not record.emission_factor_reference:
        fire("provenance", "No emission factor reference stored.")

    # 6. duplicate ---------------------------------------------------------
    dup = db.scalars(
        select(EmissionRecord).where(
            EmissionRecord.source == record.source,
            EmissionRecord.activity_type == record.activity_type,
            EmissionRecord.activity_value == record.activity_value,
            EmissionRecord.activity_unit == record.activity_unit,
            EmissionRecord.id != record.id,
        ).limit(1)
    ).first()
    if dup is not None:
        fire(
            "duplicate",
            f"Identical activity already stored as record #{dup.id}. "
            "Re-submitting the same activity inflates the total.",
            "error",
        )

    score = max(0.0, min(100.0, score))
    errors = [r for r in rules if r["severity"] == "error"]
    warnings = [r for r in rules if r["severity"] == "warning"]

    if errors or score < 50:
        status = ANOMALOUS
    elif warnings or score < 80:
        status = NEEDS_REVIEW
    elif score < 100:
        status = PLAUSIBLE
    else:
        status = VERIFIED

    return {"status": status, "trust_score": round(score, 1), "rules": rules}


def evaluate_and_store(db: Session, record: EmissionRecord) -> dict[str, Any]:
    result = evaluate(db, record)
    record.validation_status = result["status"]
    record.trust_score = result["trust_score"]
    record.triggered_rules = json.dumps(result["rules"])
    db.commit()
    return result


def revalidate_all(db: Session) -> dict[str, int]:
    """Re-run checks over every record. Returns a status histogram."""
    counts: dict[str, int] = {}
    for rec in db.scalars(select(EmissionRecord)).all():
        r = evaluate(db, rec)
        rec.validation_status = r["status"]
        rec.trust_score = r["trust_score"]
        rec.triggered_rules = json.dumps(r["rules"])
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    db.commit()
    return counts


def record_to_dict(r: EmissionRecord) -> dict[str, Any]:
    try:
        rules = json.loads(r.triggered_rules) if r.triggered_rules else []
    except (ValueError, TypeError):
        rules = []
    return {
        "id": r.id,
        "source": r.source,
        "activity_type": r.activity_type,
        "activity_value": r.activity_value,
        "activity_unit": r.activity_unit,
        "co2e": r.co2e,
        "co2e_unit": r.co2e_unit,
        "calculation_source": r.calculation_source,
        "emission_factor_reference": r.emission_factor_reference,
        "validation_status": r.validation_status,
        "trust_score": r.trust_score,
        "triggered_rules": rules,
        "reviewed_by": r.reviewed_by,
        "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
        "review_note": r.review_note,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def eligible_for_analysis(status: str) -> bool:
    """Only cleared records feed carbon analysis and optimization."""
    return status in (VERIFIED, PLAUSIBLE)
