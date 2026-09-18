"""Climatiq API integration. Isolated here so nothing else knows about HTTP.

The API key is read from the environment and is never returned to the client.
"""
import json
from pathlib import Path
from typing import Any

import httpx

from app.config import get_settings
from app.utils.sources import SOURCE_CONFIG

ACTIVITY_MAP_PATH = (
    Path(__file__).resolve().parent.parent.parent / "climatiq_activity_map.json"
)


class ClimatiqError(Exception):
    """User-facing Climatiq failure. The message is safe to display."""


class ClimatiqNotConfigured(ClimatiqError):
    """Raised when no API key / activity id is configured."""


def _load_activity_map() -> dict[str, str]:
    if ACTIVITY_MAP_PATH.exists():
        try:
            data = json.loads(ACTIVITY_MAP_PATH.read_text(encoding="utf-8"))
            return {k: v for k, v in data.items() if isinstance(v, str)}
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def resolve_activity_id(source: str) -> str:
    """Activity IDs come from configuration, never from a guess."""
    override = _load_activity_map().get(source, "").strip()
    if override:
        return override
    return str(SOURCE_CONFIG.get(source, {}).get("climatiq_activity_id", "")).strip()


def build_payload(source: str, activity_value: float, activity_unit: str) -> dict[str, Any]:
    cfg = SOURCE_CONFIG[source]
    settings = get_settings()
    activity_id = resolve_activity_id(source)
    if not activity_id:
        raise ClimatiqNotConfigured(
            "No Climatiq activity_id is configured for source '"
            + source
            + "'. Look one up in the Climatiq Data Explorer and add it to "
            "climatiq_activity_map.json, or use Demo Mode."
        )
    return {
        "emission_factor": {
            "activity_id": activity_id,
            "data_version": settings.climatiq_data_version,
        },
        "parameters": {
            cfg["climatiq_param"]: activity_value,
            cfg["climatiq_unit_param"]: activity_unit,
        },
    }


def estimate(source: str, activity_value: float, activity_unit: str) -> dict[str, Any]:
    """Call Climatiq /data/v1/estimate and map ONLY fields it actually returns."""
    settings = get_settings()
    if not settings.climatiq_configured:
        raise ClimatiqNotConfigured(
            "Climatiq API key is not configured. Set CLIMATIQ_API_KEY in "
            "backend/.env, or switch on Demo Mode."
        )

    payload = build_payload(source, activity_value, activity_unit)
    url = settings.climatiq_base_url + "/data/v1/estimate"
    headers = {"Authorization": "Bearer " + settings.climatiq_api_key}

    try:
        with httpx.Client(timeout=settings.climatiq_timeout_seconds) as client:
            resp = client.post(url, json=payload, headers=headers)
    except httpx.TimeoutException as exc:
        raise ClimatiqError(
            "Climatiq API request timed out. Please retry, or use Demo Mode."
        ) from exc
    except httpx.RequestError as exc:
        raise ClimatiqError(
            "Could not reach the Climatiq API. Check your network connection."
        ) from exc

    if resp.status_code == 401:
        raise ClimatiqError("Climatiq rejected the API key (401). Check CLIMATIQ_API_KEY.")
    if resp.status_code == 403:
        raise ClimatiqError(
            "Climatiq denied access (403). Your plan may not cover this data version."
        )
    if resp.status_code == 404:
        raise ClimatiqError(
            "Climatiq could not find that emission factor (404). Check the "
            "activity_id in climatiq_activity_map.json."
        )
    if resp.status_code == 429:
        raise ClimatiqError("Climatiq rate limit reached (429). Please wait and retry.")
    if resp.status_code >= 400:
        detail = ""
        try:
            body = resp.json()
            detail = body.get("message") or body.get("error") or ""
        except ValueError:
            detail = resp.text[:200]
        raise ClimatiqError(
            ("Climatiq API request failed (" + str(resp.status_code) + "). " + detail).strip()
        )

    try:
        data = resp.json()
    except ValueError as exc:
        raise ClimatiqError("Climatiq returned a response that could not be read.") from exc

    if "co2e" not in data:
        raise ClimatiqError("Climatiq response did not contain a co2e value.")

    ef = data.get("emission_factor") or {}
    # Only fields Climatiq actually returns are mapped through.
    ref_bits = [ef.get("name"), ef.get("source"), str(ef.get("year") or ""), ef.get("region")]
    reference = " | ".join([b for b in ref_bits if b])

    return {
        "co2e": data["co2e"],
        "co2e_unit": data.get("co2e_unit", "kg"),
        "emission_factor_reference": reference or ef.get("activity_id"),
        "calculation_source": "climatiq",
    }
