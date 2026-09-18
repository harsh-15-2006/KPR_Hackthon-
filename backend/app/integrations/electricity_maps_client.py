"""Electricity Maps API client - LIVE GRID carbon intensity.

WHAT THIS IS:
    The carbon intensity of the electricity GRID in a zone, in gCO2eq/kWh.

WHAT THIS IS NOT:
    A facility's own electricity consumption, and not a factory meter
    reading. Those two things are stored separately and must never be
    conflated. This value is REGIONAL GRID CONTEXT, and is stored with
    data_class = 'api_derived'.

Schema verified against the official reference:
    base    https://api.electricitymaps.com
    auth    auth-token: <API_KEY>        (NOT Authorization: Bearer)
    GET     /v4/carbon-intensity/latest?zone=IN-SO
    fields  zone, carbonIntensity, datetime, updatedAt, createdAt,
            emissionFactorType, isEstimated, estimationMethod

India coverage verified live from the public /v3/zones endpoint:
    IN (Mainland India), IN-NO, IN-SO, IN-EA, IN-WE, IN-NE
"""
import time
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

PROVIDER = "Electricity Maps"
SOURCE_NAME = "electricity_maps"
IS_CORE_DEPENDENCY = False   # electricity analysis degrades gracefully without it

SCOPE_NOTE = (
    "Grid electricity carbon intensity (gCO2eq/kWh) for an electricity zone. "
    "This is regional grid context, NOT a facility's own electricity "
    "consumption or meter reading."
)

UNIT = "gCO2eq/kWh"

# Verified live from https://api.electricitymaps.com/v3/zones
INDIA_ZONES = {
    "IN": "Mainland India",
    "IN-EA": "Eastern India",
    "IN-NE": "North Eastern India",
    "IN-NO": "Northern India",
    "IN-SO": "Southern India",
    "IN-WE": "Western India",
}


def _headers() -> dict[str, str]:
    s = get_settings()
    if not s.electricity_maps_configured:
        raise NotConfigured(PROVIDER, "ELECTRICITY_MAPS_API_KEY")
    # Verified: a custom header, not Authorization/Bearer.
    return {"auth-token": s.electricity_maps_api_key}


def latest_carbon_intensity(
    zone: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
) -> FetchResult:
    """Latest grid carbon intensity for a zone, or for a lat/lon's zone.

    lat/lon is a CONVENIENCE for resolving which grid zone applies. It is
    never a mandatory workflow, and the result still describes the ZONE,
    not a point measurement at those coordinates.
    """
    s = get_settings()
    params: dict[str, Any] = {}
    if zone:
        params["zone"] = zone
    elif lat is not None and lon is not None:
        params["lat"] = lat
        params["lon"] = lon
    else:
        fallback = (s.electricity_maps_default_zone or "").strip()
        if not fallback:
            raise IntegrationError(
                "No zone supplied and ELECTRICITY_MAPS_DEFAULT_ZONE is not set.",
                SourceStatus.ERROR, PROVIDER,
            )
        params["zone"] = fallback

    url = f"{s.electricity_maps_base_url}/v4/carbon-intensity/latest"
    data, final_url = request_json(
        "GET", url, PROVIDER, headers=_headers(), params=params,
        timeout=s.http_timeout_seconds,
    )

    if not isinstance(data, dict) or "carbonIntensity" not in data:
        raise IntegrationError(
            f"{PROVIDER} response did not contain carbonIntensity.",
            SourceStatus.ERROR, PROVIDER,
        )

    return FetchResult(
        data=data,
        provider=PROVIDER,
        source_url=final_url,
        fetched_at=time.time(),
        source_timestamp=data.get("datetime"),
        status=SourceStatus.LATEST_AVAILABLE,
    )


def normalize(payload: dict) -> dict:
    """Map an Electricity Maps payload to our internal shape.

    Only fields the API actually returns are mapped. `isEstimated` is
    carried through because an estimated grid value must not be presented
    as a measured one.
    """
    ci = payload.get("carbonIntensity")
    # Absent isEstimated means UNKNOWN, not False. Coercing it to False would
    # assert the value was measured when we simply do not know.
    estimated = payload.get("isEstimated")
    estimated = None if estimated is None else bool(estimated)
    zone = payload.get("zone")
    return {
        "source_name": SOURCE_NAME,
        "data_type": "grid_carbon_intensity",
        "data_class": "api_derived",
        "emission_source": "electricity",
        "zone": zone,
        "zone_name": INDIA_ZONES.get(zone or "", None),
        "value": ci,
        "unit": UNIT,
        "source_timestamp": payload.get("datetime"),
        "updated_at": payload.get("updatedAt"),
        "created_at": payload.get("createdAt"),
        "emission_factor_type": payload.get("emissionFactorType"),
        "is_estimated": estimated,
        "estimation_method": payload.get("estimationMethod"),
        "scope_note": SCOPE_NOTE,
    }


def electricity_co2e_kg(kwh: float, grid_intensity_g_per_kwh: float) -> float:
    """Combine a facility's OWN consumption with GRID intensity.

    kwh comes from the organization's operational data (self-reported or
    metered). grid_intensity comes from Electricity Maps. The product is
    CALCULATED, never measured - the caller must store it as such.
    """
    if kwh is None or grid_intensity_g_per_kwh is None:
        raise ValueError("Both kWh and grid intensity are required; neither may be assumed.")
    if kwh < 0 or grid_intensity_g_per_kwh < 0:
        raise ValueError("kWh and grid intensity must be non-negative.")
    return round(kwh * grid_intensity_g_per_kwh / 1000.0, 4)


def check_availability() -> dict[str, Any]:
    s = get_settings()
    if not s.electricity_maps_configured:
        return {"provider": PROVIDER, "status": SourceStatus.UNAVAILABLE.value,
                "message": "ELECTRICITY_MAPS_API_KEY is not set.", "scope": SCOPE_NOTE}
    try:
        latest_carbon_intensity()
        return {"provider": PROVIDER, "status": SourceStatus.LATEST_AVAILABLE.value,
                "message": "Reachable.", "scope": SCOPE_NOTE}
    except IntegrationError as exc:
        return {"provider": PROVIDER, "status": exc.status.value,
                "message": exc.message, "scope": SCOPE_NOTE}


def list_zones() -> dict[str, str]:
    """India zones, verified live. Offered as a picker, never as a requirement."""
    return dict(INDIA_ZONES)
