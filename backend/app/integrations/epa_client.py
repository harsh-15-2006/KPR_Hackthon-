"""EPA Clean Air Markets (CAM / CAMPD) API client.

SCOPE WARNING - read before using this data anywhere in the UI:
    This API covers US POWER-SECTOR facilities regulated under EPA
    programs such as the Acid Rain Program and CSAPR. It is NOT global
    factory data and must never be described as such. Emissions here are
    MEASURED/REPORTED by regulated units, so they are stored with
    data_class = 'measured'.

Schema verified against the official OpenAPI specs at
https://api.epa.gov/easey/facilities-mgmt/swagger-json and
https://api.epa.gov/easey/emissions-mgmt/swagger-json.

Two traps this client handles that EPA's own example code does not:
  1. Responses are an OBJECT wrapper {"items": [...]}, not a bare array.
  2. co2Mass is reported in SHORT TONS, not kilograms.
"""
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

PROVIDER = "EPA CAMPD"

# This connector is OPTIONAL. No core workflow (operational data intake,
# carbon analysis, optimization) may depend on it, on a facility ID, or on
# geolocation. It exists to demonstrate ingestion of genuinely MEASURED
# third-party data, and is the only place `facility` is a real concept.
IS_CORE_DEPENDENCY = False
CONNECTOR_KIND = "optional_reference"

SCOPE_NOTE = (
    "US power-sector facilities regulated under EPA programs (e.g. Acid Rain "
    "Program, CSAPR). Not global industrial data."
)

# Verified unit conversion: EPA reports CO2 mass in short tons.
SHORT_TON_TO_KG = 907.18474


def _headers() -> dict[str, str]:
    s = get_settings()
    if not s.epa_configured:
        raise NotConfigured(PROVIDER, "EPA_API_KEY")
    # Verified securityScheme: apiKey in header, name "x-api-key".
    return {"x-api-key": s.epa_api_key}


def _items(payload: Any) -> list[dict]:
    """EPA wraps collections in {"items": [...]}; tolerate a bare list too."""
    if isinstance(payload, dict):
        items = payload.get("items")
        if isinstance(items, list):
            return items
        return []
    if isinstance(payload, list):
        return payload
    return []


def list_facilities(
    state_code: str | None = None, page: int = 1, per_page: int = 100
) -> FetchResult:
    """Flat facility list. Note: this endpoint has NO year param and no lat/lon."""
    s = get_settings()
    params: dict[str, Any] = {"page": page, "perPage": min(per_page, 500)}
    if state_code:
        params["stateCode"] = state_code

    url = f"{s.epa_base_url}/facilities-mgmt/facilities"
    import time as _t

    data, final_url = request_json(
        "GET", url, PROVIDER, headers=_headers(), params=params,
        timeout=s.http_timeout_seconds,
    )
    return FetchResult(
        data=_items(data), provider=PROVIDER, source_url=final_url,
        fetched_at=_t.time(), status=SourceStatus.LATEST_AVAILABLE,
    )


def facility_attributes(
    year: int,
    state_code: str | None = None,
    facility_id: int | None = None,
    page: int = 1,
    per_page: int = 100,
) -> FetchResult:
    """Unit-level attributes INCLUDING latitude/longitude and programCodeInfo.

    year, page and perPage are all REQUIRED by the spec.
    """
    s = get_settings()
    params: dict[str, Any] = {
        "year": year,
        "page": page,
        "perPage": min(max(per_page, 1), 500),
    }
    if state_code:
        params["stateCode"] = state_code
    if facility_id is not None:
        params["facilityId"] = facility_id

    url = f"{s.epa_base_url}/facilities-mgmt/facilities/attributes"
    import time as _t

    data, final_url = request_json(
        "GET", url, PROVIDER, headers=_headers(), params=params,
        timeout=s.http_timeout_seconds,
    )
    return FetchResult(
        data=_items(data), provider=PROVIDER, source_url=final_url,
        fetched_at=_t.time(), status=SourceStatus.LATEST_AVAILABLE,
    )


def hourly_emissions(
    begin_date: str,
    end_date: str,
    facility_id: int | None = None,
    state_code: str | None = None,
    operating_hours_only: bool = True,
    page: int = 1,
    per_page: int = 100,
) -> FetchResult:
    """Unit-level hourly apportioned emissions.

    Dates are YYYY-MM-DD. beginDate, endDate, page and perPage are REQUIRED.
    Non-operating hours return NULL metrics, which is why
    operating_hours_only defaults to True.
    """
    s = get_settings()
    params: dict[str, Any] = {
        "beginDate": begin_date,
        "endDate": end_date,
        "page": page,
        "perPage": min(max(per_page, 1), 500),
        "operatingHoursOnly": str(bool(operating_hours_only)).lower(),
    }
    if facility_id is not None:
        params["facilityId"] = facility_id
    if state_code:
        params["stateCode"] = state_code

    url = f"{s.epa_base_url}/emissions-mgmt/emissions/apportioned/hourly"
    import time as _t

    data, final_url = request_json(
        "GET", url, PROVIDER, headers=_headers(), params=params,
        timeout=s.http_timeout_seconds,
    )
    return FetchResult(
        data=_items(data), provider=PROVIDER, source_url=final_url,
        fetched_at=_t.time(), status=SourceStatus.LATEST_AVAILABLE,
    )


def co2_mass_to_kg(co2_mass_short_tons: float | None) -> float | None:
    """EPA co2Mass is in SHORT TONS. Convert to kg for internal storage."""
    if co2_mass_short_tons is None:
        return None
    return round(float(co2_mass_short_tons) * SHORT_TON_TO_KG, 4)


def normalize_hourly_row(row: dict) -> dict | None:
    """Map one EPA hourly row to our internal emission shape.

    Returns None when the hour has no CO2 reading, rather than inventing a
    zero. A missing measurement is not the same as zero emissions.
    """
    co2 = row.get("co2Mass")
    if co2 is None:
        return None
    date = row.get("date")
    hour = row.get("hour")
    if date is None or hour is None:
        return None
    return {
        "source_facility_id": str(row.get("facilityId")),
        "facility_name": row.get("facilityName"),
        "unit_id": row.get("unitId"),
        "emission_source": "electricity",
        "activity_type": "power_generation",
        "activity_value": row.get("grossLoad"),   # MW, may be None
        "activity_unit": "MW",
        "co2e_kg": co2_mass_to_kg(co2),
        "data_class": "measured",
        "calculation_method": "EPA CAMPD apportioned hourly co2Mass (short tons -> kg)",
        "source_name": PROVIDER,
        "source_timestamp": f"{date}T{int(hour):02d}:00:00",
        "heat_input_mmbtu": row.get("heatInput"),
        "program_codes": row.get("programCodeInfo"),
        "op_time": row.get("opTime"),
    }


def check_availability() -> dict[str, Any]:
    """Truthful availability probe for the UI."""
    s = get_settings()
    if not s.epa_configured:
        return {"provider": PROVIDER, "status": SourceStatus.UNAVAILABLE.value,
                "message": "EPA_API_KEY is not set.", "scope": SCOPE_NOTE}
    try:
        list_facilities(page=1, per_page=1)
        return {"provider": PROVIDER, "status": SourceStatus.LATEST_AVAILABLE.value,
                "message": "Reachable.", "scope": SCOPE_NOTE}
    except IntegrationError as exc:
        return {"provider": PROVIDER, "status": exc.status.value,
                "message": exc.message, "scope": SCOPE_NOTE}
