"""Hotspot aggregation.

This is a DETERMINISTIC calculation over stored emission records.
It is not a prediction and it is not an AI model.

    source_share = source_co2e / total_co2e * 100
"""
from sqlalchemy.orm import Session

from app.schemas.emission import HotspotSummary, SourceBreakdown
from app.services.emission_service import list_records
from app.utils.sources import SOURCE_CONFIG, SOURCES

CALCULATION_NOTE = (
    "Deterministic aggregation of stored emission records: "
    "source_share = source_co2e / total_co2e * 100. Not a prediction."
)


_KG_PER_UNIT: dict[str, float] = {
    "kg": 1.0, "kgco2e": 1.0, "kilogram": 1.0, "kilograms": 1.0,
    "t": 1000.0, "tonne": 1000.0, "tonnes": 1000.0, "tco2e": 1000.0, "mt": 1000.0,
    "g": 0.001, "gram": 0.001, "grams": 0.001,
    "lb": 0.45359237, "lbs": 0.45359237, "pound": 0.45359237, "pounds": 0.45359237,
    "short_ton": 907.18474, "shortton": 907.18474,
}


def _normalise_to_kg(co2e: float, unit: str) -> float:
    """Convert a CO2e value to kilograms.

    An UNRECOGNISED unit raises rather than being silently assumed to be
    kilograms. Quietly treating, say, pounds as kg would corrupt the total
    and then present the result as authoritative - exactly the kind of
    silent mislabelling this project forbids.
    """
    u = (unit or "").strip().lower()
    if not u:
        raise ValueError("CO2e unit is missing; it cannot be assumed to be kg.")
    factor = _KG_PER_UNIT.get(u)
    if factor is None:
        raise ValueError(
            f"Unrecognised CO2e unit '{unit}'. Refusing to assume kilograms. "
            f"Known units: {', '.join(sorted(_KG_PER_UNIT))}"
        )
    return co2e * factor


def build_summary(db: Session) -> HotspotSummary:
    records = list_records(db)

    totals: dict[str, float] = {s: 0.0 for s in SOURCES}
    counts: dict[str, int] = {s: 0 for s in SOURCES}

    for r in records:
        if r.source in totals:
            totals[r.source] += _normalise_to_kg(r.co2e, r.co2e_unit)
            counts[r.source] += 1

    total = sum(totals.values())

    breakdown: list[SourceBreakdown] = []
    for s in SOURCES:
        pct = (totals[s] / total * 100.0) if total > 0 else 0.0
        breakdown.append(
            SourceBreakdown(
                source=s,
                label=SOURCE_CONFIG[s]["label"],
                co2e=round(totals[s], 4),
                co2e_unit="kg",
                contribution_pct=round(pct, 2),
                record_count=counts[s],
            )
        )

    breakdown.sort(key=lambda b: b.co2e, reverse=True)

    top = breakdown[0] if breakdown and breakdown[0].co2e > 0 else None

    return HotspotSummary(
        total_co2e=round(total, 4),
        co2e_unit="kg",
        record_count=len(records),
        by_source=breakdown,
        highest_source=top.source if top else None,
        highest_source_label=top.label if top else None,
        highest_source_co2e=top.co2e if top else None,
        highest_source_pct=top.contribution_pct if top else None,
        calculation_note=CALCULATION_NOTE,
    )
