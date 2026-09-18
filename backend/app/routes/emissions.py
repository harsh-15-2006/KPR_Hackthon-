"""Emission endpoints: calculate, list, summary, by-source, CSV import."""
import csv
import io

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.deps import resolve_scope
from app.db.session import get_db
from app.schemas.emission import (
    EmissionCalculateRequest,
    EmissionRecordOut,
    SourceMeta,
)
from app.services import emission_service
from app.services.emission_service import EmissionCalculationError
from app.utils.sources import SOURCE_CONFIG, SOURCES, is_valid_source

router = APIRouter(prefix="/api/emissions", tags=["emissions"])

CSV_COLUMNS = ["source", "activity_type", "activity_value", "activity_unit", "period"]


@router.get("/sources", response_model=list[SourceMeta])
def get_sources() -> list[SourceMeta]:
    """Per-source activity metadata. Units differ by source by design."""
    return [
        SourceMeta(
            source=s,
            label=SOURCE_CONFIG[s]["label"],
            activity_types=SOURCE_CONFIG[s]["activity_types"],
            allowed_units=SOURCE_CONFIG[s]["allowed_units"],
            default_unit=SOURCE_CONFIG[s]["default_unit"],
            help=SOURCE_CONFIG[s]["help"],
        )
        for s in SOURCES
    ]


@router.post("/calculate", response_model=EmissionRecordOut, status_code=201)
def calculate(
    payload: EmissionCalculateRequest,
    demo: bool = Query(default=False, description="Use Demo Mode instead of Climatiq"),
    db: Session = Depends(get_db),
    scope: str = Depends(resolve_scope),
) -> EmissionRecordOut:
    if scope == "__ALL__":
        raise HTTPException(
            status_code=400,
            detail="Select a company (scope_key) before adding data as an administrator.",
        )
    try:
        record = emission_service.calculate_and_store(db, payload, demo_mode=demo, scope_key=scope)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except EmissionCalculationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return EmissionRecordOut.model_validate(record)


@router.get("", response_model=list[EmissionRecordOut])
def list_emissions(
    source: str | None = Query(default=None),
    db: Session = Depends(get_db),
    scope: str = Depends(resolve_scope),
) -> list[EmissionRecordOut]:
    if source and not is_valid_source(source):
        raise HTTPException(status_code=422, detail="Unknown source '" + source + "'.")
    return [
        EmissionRecordOut.model_validate(r)
        for r in emission_service.list_records(db, source, scope_key=scope)
    ]


@router.get("/csv-template")
def csv_template() -> dict:
    """Documented CSV shape. Columns are never guessed at import time."""
    return {
        "columns": CSV_COLUMNS,
        "example_rows": [
            {
                "source": "electricity",
                "activity_type": "grid_electricity",
                "activity_value": "125000",
                "activity_unit": "kWh",
                "period": "2026-Q1",
            },
            {
                "source": "logistics",
                "activity_type": "road_freight",
                "activity_value": "48000",
                "activity_unit": "t.km",
                "period": "2026-Q1",
            },
        ],
        "notes": (
            "activity_unit must be valid for the chosen source. "
            "Allowed units differ per source - see GET /api/emissions/sources."
        ),
    }


@router.post("/preview-csv")
async def preview_csv(file: UploadFile = File(...)) -> dict:
    """Validate a CSV and return a preview. Nothing is imported here."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=422, detail="Please upload a .csv file.")

    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=422, detail="Could not read the file. Please save it as UTF-8 CSV."
        ) from None

    reader = csv.DictReader(io.StringIO(text))
    headers = [h.strip() for h in (reader.fieldnames or [])]
    missing = [c for c in CSV_COLUMNS if c not in headers and c != "period"]
    if missing:
        raise HTTPException(
            status_code=422,
            detail="CSV is missing required column(s): " + ", ".join(missing),
        )

    valid_rows: list[dict] = []
    errors: list[dict] = []
    for i, row in enumerate(reader, start=2):
        try:
            parsed = EmissionCalculateRequest(
                source=(row.get("source") or "").strip().lower(),
                activity_type=(row.get("activity_type") or "").strip(),
                activity_value=float((row.get("activity_value") or "").strip()),
                activity_unit=(row.get("activity_unit") or "").strip(),
                period=(row.get("period") or "").strip() or None,
            )
            parsed.validate_unit_for_source()
            valid_rows.append(parsed.model_dump())
        except ValidationError as exc:
            # Use the structured errors, not str(exc) -- the last line of the
            # string form is a docs URL, which is useless to the user.
            parts = []
            for e in exc.errors():
                field = e["loc"][-1] if e.get("loc") else ""
                message = e.get("msg", "Invalid value.")
                message = message.replace("Value error, ", "")
                parts.append(f"{field}: {message}" if field else message)
            errors.append({"row": i, "error": "; ".join(parts)})
        except ValueError as exc:
            errors.append({"row": i, "error": str(exc)})

    return {
        "columns": headers,
        "valid_count": len(valid_rows),
        "error_count": len(errors),
        "rows": valid_rows[:50],
        "errors": errors[:50],
    }


@router.post("/import", response_model=list[EmissionRecordOut], status_code=201)
def import_rows(
    rows: list[EmissionCalculateRequest],
    demo: bool = Query(default=False),
    db: Session = Depends(get_db),
    scope: str = Depends(resolve_scope),
) -> list[EmissionRecordOut]:
    """Import confirmed rows. Called only after the user confirms the preview."""
    if not rows:
        raise HTTPException(status_code=422, detail="No rows to import.")
    created = []
    for row in rows:
        try:
            created.append(
                emission_service.calculate_and_store(db, row, demo_mode=demo, scope_key=scope)
            )
        except (ValueError, EmissionCalculationError) as exc:
            raise HTTPException(
                status_code=502,
                detail="Import stopped at '" + row.activity_type + "': " + str(exc),
            ) from exc
    return [EmissionRecordOut.model_validate(r) for r in created]


@router.delete("", status_code=200)
def clear_emissions(
    db: Session = Depends(get_db), scope: str = Depends(resolve_scope)
) -> dict:
    return {"deleted": emission_service.delete_all(db, scope_key=scope)}


@router.get("/config")
def runtime_config() -> dict:
    """Tells the UI whether Climatiq is usable. Never returns the key itself."""
    s = get_settings()
    return {
        "climatiq_configured": s.climatiq_configured,
        "gemini_enabled": s.gemini_configured,
        "using_sqlite_fallback": s.using_sqlite_fallback,
    }
