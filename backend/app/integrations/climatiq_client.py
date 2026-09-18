"""Climatiq API client - ACTIVITY DATA -> EMISSION FACTOR -> CO2e.

WHAT THIS IS:
    A calculation service. You give it activity data you already have
    (kWh, litres, tonnes, tonne-km) and it returns CO2e using a published
    emission factor. Results are stored with data_class = 'calculated'.

WHAT THIS IS NOT:
    A source of live factory operational data. Nothing here observes a
    plant. Never send EPA-measured emissions here just because the API
    exists - measured and calculated are different concepts and are kept
    in separate records.

Schema verified against https://www.climatiq.io/docs:
    base    https://api.climatiq.io
    auth    Authorization: Bearer <API_KEY>
    POST    /data/v1/estimate
    GET     /data/v1/search
    GET     /data/v1/data-versions   -> {"latest_release": "37", ...}
"""
import json
import time
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.integrations.base import (
    FetchResult,
    IntegrationError,
    NotConfigured,
    SourceStatus,
    request_json,
)

logger = get_logger(__name__)

PROVIDER = "Climatiq"
SOURCE_NAME = "climatiq"
IS_CORE_DEPENDENCY = False

SCOPE_NOTE = (
    "Converts supplied activity data into CO2e using published emission "
    "factors. It does not observe or report operational activity."
)

# Parameter shape per emission source. Climatiq requires the parameter
# names the chosen factor expects; these are the common ones.
SOURCE_PARAMETERS: dict[str, tuple[str, str]] = {
    "electricity": ("energy", "energy_unit"),
    "fuel": ("volume", "volume_unit"),
    "logistics": ("distance", "distance_unit"),
    "production": ("weight", "weight_unit"),
    "waste": ("weight", "weight_unit"),
}


ACTIVITY_MAP_PATH = Path(__file__).resolve().parent.parent.parent / "climatiq_activity_map.json"


def _load_activity_map() -> dict:
    """Configured activity IDs. Missing file simply means nothing is mapped."""
    if not ACTIVITY_MAP_PATH.exists():
        return {}
    try:
        data = json.loads(ACTIVITY_MAP_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def resolve_activity(source: str) -> tuple[str, str | None]:
    """Return (activity_id, region) for a source. Never guessed - config only."""
    entry = _load_activity_map().get(source)
    if isinstance(entry, dict):
        return str(entry.get("activity_id", "")).strip(), (entry.get("region") or None)
    if isinstance(entry, str):
        return entry.strip(), None
    return "", None


def resolve_activity_id(source: str) -> str:
    return resolve_activity(source)[0]


def _headers() -> dict[str, str]:
    s = get_settings()
    if not s.climatiq_configured:
        raise NotConfigured(PROVIDER, "CLIMATIQ_API_KEY")
    return {
        "Authorization": f"Bearer {s.climatiq_api_key}",
        "Content-Type": "application/json",
    }


def data_versions() -> FetchResult:
    """Current data version. Lets us avoid pinning a stale version."""
    s = get_settings()
    url = f"{s.climatiq_base_url}/data/v1/data-versions"
    data, final = request_json(
        "GET", url, PROVIDER, headers=_headers(), timeout=s.http_timeout_seconds
    )
    return FetchResult(data=data, provider=PROVIDER, source_url=final, fetched_at=time.time())


def search_factors(
    query: str,
    data_version: str | None = None,
    region: str | None = None,
    year: int | None = None,
    results_per_page: int = 10,
) -> FetchResult:
    """Find emission factors. Activity IDs are LOOKED UP here, never guessed."""
    s = get_settings()
    params: dict[str, Any] = {
        "data_version": data_version or s.climatiq_data_version or "^37",
        "query": query,
        "results_per_page": results_per_page,
    }
    if region:
        params["region"] = region
    if year:
        params["year"] = year

    url = f"{s.climatiq_base_url}/data/v1/search"
    data, final = request_json(
        "GET", url, PROVIDER, headers=_headers(), params=params,
        timeout=s.http_timeout_seconds,
    )
    results = data.get("results", []) if isinstance(data, dict) else []
    return FetchResult(data=results, provider=PROVIDER, source_url=final, fetched_at=time.time())


def estimate(
    activity_id: str,
    parameters: dict[str, Any],
    data_version: str | None = None,
    region: str | None = None,
) -> FetchResult:
    """Calculate CO2e for supplied activity data.

    `activity_id` must come from search_factors or explicit configuration.
    It is never invented here.
    """
    s = get_settings()
    if not activity_id:
        raise IntegrationError(
            "An activity_id is required. Look one up via the search endpoint - "
            "activity IDs are never guessed.",
            SourceStatus.ERROR, PROVIDER,
        )

    selector: dict[str, Any] = {
        "activity_id": activity_id,
        "data_version": data_version or s.climatiq_data_version or "^37",
    }
    if region:
        selector["region"] = region
    body = {"emission_factor": selector, "parameters": parameters}
    url = f"{s.climatiq_base_url}/data/v1/estimate"
    data, final = request_json(
        "POST", url, PROVIDER, headers=_headers(), json_body=body,
        timeout=s.http_timeout_seconds,
    )
    if not isinstance(data, dict) or "co2e" not in data:
        raise IntegrationError(
            f"{PROVIDER} response did not contain a co2e value.",
            SourceStatus.ERROR, PROVIDER,
        )
    return FetchResult(
        data=data, provider=PROVIDER, source_url=final, fetched_at=time.time(),
        status=SourceStatus.LATEST_AVAILABLE,
    )


# Typical diesel density, used only to convert a volume the user entered
# into the WEIGHT that Climatiq's diesel factor requires.
DIESEL_KG_PER_LITRE = 0.8375


def build_parameters(emission_source: str, value: float, unit: str) -> dict[str, Any]:
    """Build the parameter object for a source.

    Each Climatiq factor declares a unit_type and accepts only the matching
    parameters. These shapes were confirmed by live estimate calls:
      electricity  Energy            -> energy / energy_unit
      fuel         Weight            -> weight / weight_unit
      logistics    WeightOverDistance-> weight + distance
      production   Weight            -> weight / weight_unit
      waste        Weight            -> weight / weight_unit
    """
    u = (unit or "").strip()

    if emission_source == "electricity":
        return {"energy": value, "energy_unit": u}

    if emission_source == "fuel":
        # The diesel factor is weight-based. A volume must be converted.
        if u.lower() in ("l", "litre", "liter", "litres", "liters"):
            return {"weight": round(value * DIESEL_KG_PER_LITRE, 4), "weight_unit": "kg"}
        if u.lower() == "m3":
            return {"weight": round(value * 1000 * DIESEL_KG_PER_LITRE, 4), "weight_unit": "kg"}
        return {"weight": value, "weight_unit": u}

    if emission_source == "logistics":
        # t.km is tonnes x kilometres. Send 1 tonne over N km so the product
        # equals the tonne-kilometres the user entered.
        if u.lower() in ("t.km", "t-km", "tkm"):
            return {"weight": 1, "weight_unit": "t", "distance": value, "distance_unit": "km"}
        return {"weight": 1, "weight_unit": "t", "distance": value, "distance_unit": u}

    if emission_source in ("production", "waste"):
        return {"weight": value, "weight_unit": u}

    raise ValueError(f"No Climatiq parameter mapping for emission source '{emission_source}'.")


def normalize(payload: dict, activity_value: float, activity_unit: str,
              emission_source: str) -> dict:
    """Map a Climatiq estimate to our internal shape. Only real fields."""
    ef = payload.get("emission_factor") or {}
    co2e = payload.get("co2e")
    co2e_unit = payload.get("co2e_unit", "kg")

    # Normalize to kg for internal storage. An unrecognised unit must NOT be
    # silently assumed to be kg - that would corrupt every downstream total.
    _TO_KG = {
        "kg": 1.0, "t": 1000.0, "tonne": 1000.0, "tonnes": 1000.0,
        "g": 0.001, "gram": 0.001, "grams": 0.001,
        "lb": 0.45359237, "lbs": 0.45359237,
    }
    co2e_kg = None
    if isinstance(co2e, (int, float)):
        factor = _TO_KG.get(str(co2e_unit).strip().lower())
        if factor is None:
            raise IntegrationError(
                f"{PROVIDER} returned CO2e in an unrecognised unit '{co2e_unit}'. "
                "Refusing to assume kilograms.",
                SourceStatus.ERROR, PROVIDER,
            )
        co2e_kg = co2e * factor

    ref_parts = [ef.get("name"), ef.get("source"), str(ef.get("year") or ""), ef.get("region")]
    reference = " | ".join([p for p in ref_parts if p])

    return {
        "source_name": SOURCE_NAME,
        "data_type": "activity_calculation",
        "data_class": "calculated",
        "emission_source": emission_source,
        "activity_value": activity_value,
        "activity_unit": activity_unit,
        "co2e_kg": round(co2e_kg, 4) if isinstance(co2e_kg, (int, float)) else None,
        "co2e_reported": co2e,
        "co2e_reported_unit": co2e_unit,
        "calculation_method": payload.get("co2e_calculation_method"),
        "calculation_origin": payload.get("co2e_calculation_origin"),
        "factor_reference": reference or ef.get("activity_id"),
        "factor_activity_id": ef.get("activity_id"),
        "factor_source": ef.get("source"),
        "factor_year": ef.get("year"),
        "factor_region": ef.get("region"),
        "audit_trail": payload.get("audit_trail"),
        "scope_note": SCOPE_NOTE,
    }


def check_availability() -> dict[str, Any]:
    s = get_settings()
    if not s.climatiq_configured:
        return {"provider": PROVIDER, "status": SourceStatus.UNAVAILABLE.value,
                "message": "CLIMATIQ_API_KEY is not set.", "scope": SCOPE_NOTE}
    try:
        res = data_versions()
        latest = res.data.get("latest_release") if isinstance(res.data, dict) else None
        return {"provider": PROVIDER, "status": SourceStatus.LATEST_AVAILABLE.value,
                "message": f"Reachable. Latest data version: {latest}.", "scope": SCOPE_NOTE}
    except IntegrationError as exc:
        return {"provider": PROVIDER, "status": exc.status.value,
                "message": exc.message, "scope": SCOPE_NOTE}


def estimate_for_source(emission_source: str, value: float, unit: str) -> dict:
    """Look up the configured factor for a source and calculate CO2e.

    Everything here comes from climatiq_activity_map.json. Nothing is guessed.
    """
    activity_id, region = resolve_activity(emission_source)
    if not activity_id:
        raise IntegrationError(
            f"No Climatiq activity_id configured for '{emission_source}'. "
            "Add one to climatiq_activity_map.json, or use Demo Mode.",
            SourceStatus.ERROR, PROVIDER,
        )
    params = build_parameters(emission_source, value, unit)
    try:
        res = estimate(activity_id, params, region=region)
    except IntegrationError:
        if region:
            # A region-specific factor may not exist; retry unpinned rather
            # than failing outright. The response still reports which region
            # was actually used, so provenance stays truthful.
            res = estimate(activity_id, params)
        else:
            raise
    return normalize(res.data, value, unit, emission_source)
