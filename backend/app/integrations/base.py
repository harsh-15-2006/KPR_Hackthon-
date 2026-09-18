"""Shared HTTP plumbing for every external integration.

One place for timeouts, retries, rate-limit handling and error mapping,
so each client only has to describe its own endpoints.

Design rule: a failure NEVER becomes fabricated data. Every failure path
raises an IntegrationError carrying a truthful status the UI can display.
"""
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)


class SourceStatus(str, Enum):
    """Truthful states the frontend is allowed to display."""

    LIVE = "LIVE"
    LATEST_AVAILABLE = "LATEST_AVAILABLE"
    ESTIMATED = "ESTIMATED"
    VALIDATED = "VALIDATED"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"
    ERROR = "ERROR"


class IntegrationError(Exception):
    """A user-safe external-API failure. The message may be shown in the UI."""

    def __init__(self, message: str, status: SourceStatus = SourceStatus.ERROR,
                 provider: str = "", http_status: int | None = None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.provider = provider
        self.http_status = http_status

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "status": self.status.value,
            "message": self.message,
            "http_status": self.http_status,
        }


class NotConfigured(IntegrationError):
    """No API key configured. Distinct from a failed call."""

    def __init__(self, provider: str, env_var: str):
        super().__init__(
            f"{provider} is not configured. Set {env_var} in backend/.env.",
            status=SourceStatus.UNAVAILABLE,
            provider=provider,
        )


@dataclass
class FetchResult:
    """A successful fetch plus the provenance needed to store it honestly."""

    data: Any
    provider: str
    source_url: str
    fetched_at: float
    source_timestamp: str | None = None
    status: SourceStatus = SourceStatus.LATEST_AVAILABLE


# Retrying a GET is safe; these are the only statuses worth retrying.
_RETRYABLE = {429, 500, 502, 503, 504}


def request_json(
    method: str,
    url: str,
    provider: str,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    timeout: float = 30.0,
    max_retries: int = 2,
) -> tuple[Any, str]:
    """Perform an HTTP request and return (parsed_json, final_url).

    Raises IntegrationError on every failure path. Never returns fake data.
    """
    attempt = 0
    last_error: str = ""

    while attempt <= max_retries:
        attempt += 1
        try:
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                resp = client.request(
                    method, url, headers=headers or {}, params=params, json=json_body
                )
        except httpx.TimeoutException as exc:
            last_error = f"{provider} request timed out after {timeout:.0f}s."
            if attempt > max_retries:
                raise IntegrationError(last_error, SourceStatus.ERROR, provider) from exc
            time.sleep(0.6 * attempt)
            continue
        except httpx.RequestError as exc:
            last_error = f"Could not reach {provider}. Check network connectivity."
            if attempt > max_retries:
                raise IntegrationError(last_error, SourceStatus.UNAVAILABLE, provider) from exc
            time.sleep(0.6 * attempt)
            continue

        if resp.status_code in _RETRYABLE and attempt <= max_retries:
            time.sleep(1.2 * attempt if resp.status_code == 429 else 0.6 * attempt)
            continue

        if resp.status_code == 401:
            raise IntegrationError(
                f"{provider} rejected the API key (401). Check the key in backend/.env.",
                SourceStatus.ERROR, provider, 401,
            )
        if resp.status_code == 403:
            raise IntegrationError(
                f"{provider} denied access (403). The key may be missing, invalid, "
                "or the plan may not cover this endpoint.",
                SourceStatus.ERROR, provider, 403,
            )
        if resp.status_code == 404:
            raise IntegrationError(
                f"{provider} returned 404 - the requested resource does not exist.",
                SourceStatus.ERROR, provider, 404,
            )
        if resp.status_code == 429:
            raise IntegrationError(
                f"{provider} rate limit reached (429). Please wait and retry.",
                SourceStatus.ERROR, provider, 429,
            )
        if resp.status_code >= 400:
            detail = _extract_error(resp)
            raise IntegrationError(
                f"{provider} request failed ({resp.status_code}). {detail}".strip(),
                SourceStatus.ERROR, provider, resp.status_code,
            )

        try:
            return resp.json(), str(resp.url)
        except ValueError as exc:
            raise IntegrationError(
                f"{provider} returned a malformed (non-JSON) response.",
                SourceStatus.ERROR, provider, resp.status_code,
            ) from exc

    raise IntegrationError(last_error or f"{provider} request failed.", SourceStatus.ERROR, provider)


def _extract_error(resp: httpx.Response) -> str:
    try:
        body = resp.json()
        if isinstance(body, dict):
            err = body.get("error")
            if isinstance(err, dict):
                return str(err.get("message") or err.get("code") or "")
            return str(body.get("message") or body.get("detail") or err or "")
    except ValueError:
        pass
    return resp.text[:200]
