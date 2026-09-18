"""Fault tolerance for external connectors.

This is DISTINCT from the data-trust layer. Data trust asks "is this value
plausible?". Fault tolerance asks "can I reach the provider at all, and if
not, what am I allowed to serve instead?".

The one inviolable rule: a failure NEVER becomes a fabricated value.
Degradation is limited to serving a previously-real payload, explicitly
marked STALE. A missing value stays missing - it is never zero-filled.

Behaviour
---------
  success              -> persist cache, health HEALTHY,   status LIVE/LATEST_AVAILABLE
  transient failure    -> bounded retries with exponential backoff
  still failing + cache within freshness policy -> serve cache, marked STALE
  still failing + cache too old or absent       -> UNAVAILABLE, no data
  repeated failures    -> circuit opens, stop hammering the provider
"""
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.integrations.base import IntegrationError, SourceStatus
from app.models.operational import CachedResponse, SourceHealth

logger = get_logger(__name__)


class HealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"      # recovering, or some failures observed
    STALE = "STALE"            # serving last-known-good within policy
    UNAVAILABLE = "UNAVAILABLE"
    ERROR = "ERROR"


@dataclass(frozen=True)
class FreshnessPolicy:
    """How old a cached payload may be before it stops being usable.

    max_age_seconds is chosen from the PROVIDER's real update cadence, not
    invented. Serving anything older than this is refused outright.
    """

    max_age_seconds: int
    description: str


# Cadences reflect what each provider actually publishes.
FRESHNESS: dict[str, FreshnessPolicy] = {
    # Electricity Maps publishes frequently; an hour-old value is still
    # usable context but must be labelled stale.
    "electricity_maps": FreshnessPolicy(3600, "Grid intensity updates frequently; 1h tolerance."),
    # EPA CAMPD is hourly data published with a lag; a day is tolerable.
    "epa": FreshnessPolicy(86400, "EPA publishes hourly data with reporting lag; 24h tolerance."),
    # Climatiq is a calculation service - a factor lookup is stable for a while.
    "climatiq": FreshnessPolicy(86400, "Emission factors are stable within a data version; 24h."),
    # Gemini responses are never reused as data.
    "gemini": FreshnessPolicy(0, "AI output is never served from cache as data."),
}
DEFAULT_FRESHNESS = FreshnessPolicy(3600, "Default 1h tolerance.")


@dataclass
class CircuitPolicy:
    failure_threshold: int = 4      # consecutive failures before opening
    cooldown_seconds: int = 60      # how long to stay open


DEFAULT_CIRCUIT = CircuitPolicy()


@dataclass
class ResilientResult:
    """Outcome of a fault-tolerant fetch. `data` is None when unavailable."""

    data: Any | None
    source_name: str
    status: SourceStatus
    health: HealthStatus
    from_cache: bool = False
    source_timestamp: str | None = None
    fetched_at: str | None = None
    age_seconds: float | None = None
    message: str = ""
    errors: list[str] = field(default_factory=list)

    @property
    def usable(self) -> bool:
        return self.data is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source_name,
            "status": self.status.value,
            "health": self.health.value,
            "from_cache": self.from_cache,
            "source_timestamp": self.source_timestamp,
            "fetched_at": self.fetched_at,
            "age_seconds": self.age_seconds,
            "message": self.message,
            "errors": self.errors,
        }


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ------------------------------------------------------------ health store


def get_health(db: Session, source_name: str) -> SourceHealth:
    row = db.scalar(select(SourceHealth).where(SourceHealth.source_name == source_name))
    if row is None:
        row = SourceHealth(source_name=source_name, status=HealthStatus.UNAVAILABLE.value)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def circuit_is_open(health: SourceHealth) -> bool:
    until = _aware(health.circuit_open_until)
    return until is not None and _now() < until


def record_success(db: Session, source_name: str, source_timestamp: str | None) -> SourceHealth:
    h = get_health(db, source_name)
    h.status = HealthStatus.HEALTHY.value
    h.last_success_at = _now()
    h.fetched_at = _now()
    h.consecutive_failures = 0
    h.stale_since = None
    h.last_error = None
    h.freshness_status = "fresh"
    h.circuit_open_until = None
    if source_timestamp:
        try:
            h.last_source_timestamp = datetime.fromisoformat(
                source_timestamp.replace("Z", "+00:00")
            )
        except (ValueError, AttributeError):
            pass
    db.commit()
    return h


def record_failure(
    db: Session, source_name: str, error: str, policy: CircuitPolicy = DEFAULT_CIRCUIT
) -> SourceHealth:
    h = get_health(db, source_name)
    h.last_failure_at = _now()
    h.consecutive_failures = (h.consecutive_failures or 0) + 1
    h.last_error = error[:500]
    if h.stale_since is None:
        h.stale_since = _now()
    if h.consecutive_failures >= policy.failure_threshold:
        h.status = HealthStatus.UNAVAILABLE.value
        h.circuit_open_until = _now() + timedelta(seconds=policy.cooldown_seconds)
        logger.warning(
            "Circuit opened",
            extra={"event": "circuit_open", "source": source_name,
                   "status": str(h.consecutive_failures)},
        )
    else:
        h.status = HealthStatus.DEGRADED.value
    db.commit()
    return h


# ------------------------------------------------------------- cache store


def store_cache(db: Session, source_name: str, cache_key: str, payload: Any,
                source_timestamp: str | None) -> None:
    existing = db.scalar(
        select(CachedResponse).where(
            CachedResponse.source_name == source_name,
            CachedResponse.cache_key == cache_key,
        )
    )
    ts = None
    if source_timestamp:
        try:
            ts = datetime.fromisoformat(source_timestamp.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            ts = None
    blob = json.dumps(payload, default=str)
    if existing:
        existing.payload = blob
        existing.source_timestamp = ts
        existing.stored_at = _now()
        existing.is_good = True
    else:
        db.add(CachedResponse(source_name=source_name, cache_key=cache_key,
                              payload=blob, source_timestamp=ts))
    db.commit()


def read_cache(db: Session, source_name: str, cache_key: str) -> tuple[Any, float, datetime] | None:
    """Return (payload, age_seconds, stored_at) or None."""
    row = db.scalar(
        select(CachedResponse).where(
            CachedResponse.source_name == source_name,
            CachedResponse.cache_key == cache_key,
            CachedResponse.is_good.is_(True),
        )
    )
    if row is None:
        return None
    stored = _aware(row.stored_at) or _now()
    age = (_now() - stored).total_seconds()
    try:
        return json.loads(row.payload), age, stored
    except (ValueError, TypeError):
        return None


# ------------------------------------------------------------- main entry


def resilient_fetch(
    db: Session,
    source_name: str,
    cache_key: str,
    fetch: Callable[[], Any],
    source_timestamp_of: Callable[[Any], str | None] | None = None,
    max_retries: int = 2,
    base_backoff: float = 0.5,
    circuit: CircuitPolicy = DEFAULT_CIRCUIT,
) -> ResilientResult:
    """Call `fetch` with retries, backoff, circuit breaking and STALE fallback."""
    policy = FRESHNESS.get(source_name, DEFAULT_FRESHNESS)
    errors: list[str] = []

    health = get_health(db, source_name)

    # --- circuit open: do not hammer the provider ---
    if circuit_is_open(health):
        msg = (
            f"{source_name} circuit is open after {health.consecutive_failures} "
            "consecutive failures; not calling the provider."
        )
        return _degrade(db, source_name, cache_key, policy, msg, [msg])

    # --- attempt with exponential backoff ---
    for attempt in range(max_retries + 1):
        try:
            data = fetch()
        except IntegrationError as exc:
            errors.append(exc.message)
            if attempt < max_retries:
                time.sleep(base_backoff * (2 ** attempt))
                continue
            record_failure(db, source_name, exc.message, circuit)
            return _degrade(db, source_name, cache_key, policy, exc.message, errors)
        except Exception as exc:  # noqa: BLE001 - connector bug must not fabricate data
            msg = f"{source_name} connector raised an unexpected error: {type(exc).__name__}"
            errors.append(msg)
            record_failure(db, source_name, msg, circuit)
            return _degrade(db, source_name, cache_key, policy, msg, errors)

        src_ts = source_timestamp_of(data) if source_timestamp_of else None
        if policy.max_age_seconds > 0:
            store_cache(db, source_name, cache_key, data, src_ts)
        record_success(db, source_name, src_ts)
        return ResilientResult(
            data=data,
            source_name=source_name,
            status=SourceStatus.LATEST_AVAILABLE,
            health=HealthStatus.HEALTHY,
            from_cache=False,
            source_timestamp=src_ts,
            fetched_at=_now().isoformat(),
            age_seconds=0.0,
            message="Fetched from provider.",
        )

    # unreachable, but keeps the type checker honest
    return _degrade(db, source_name, cache_key, policy, "Unknown failure.", errors)


def _degrade(
    db: Session,
    source_name: str,
    cache_key: str,
    policy: FreshnessPolicy,
    message: str,
    errors: list[str],
) -> ResilientResult:
    """Serve last-known-good ONLY within the freshness policy. Never fabricate."""
    if policy.max_age_seconds <= 0:
        return ResilientResult(
            data=None, source_name=source_name, status=SourceStatus.UNAVAILABLE,
            health=HealthStatus.UNAVAILABLE,
            message=f"{message} No cached fallback is permitted for this source.",
            errors=errors,
        )

    cached = read_cache(db, source_name, cache_key)
    if cached is None:
        return ResilientResult(
            data=None, source_name=source_name, status=SourceStatus.UNAVAILABLE,
            health=HealthStatus.UNAVAILABLE,
            message=f"{message} No previous good data exists, so no value is available.",
            errors=errors,
        )

    payload, age, stored = cached
    if age > policy.max_age_seconds:
        return ResilientResult(
            data=None, source_name=source_name, status=SourceStatus.UNAVAILABLE,
            health=HealthStatus.UNAVAILABLE,
            age_seconds=round(age, 1),
            message=(
                f"{message} Cached data is {int(age)}s old, which exceeds the "
                f"{policy.max_age_seconds}s freshness limit for {source_name}, "
                "so it will not be served."
            ),
            errors=errors,
        )

    h = get_health(db, source_name)
    h.status = HealthStatus.STALE.value
    h.freshness_status = "stale"
    db.commit()

    return ResilientResult(
        data=payload, source_name=source_name, status=SourceStatus.STALE,
        health=HealthStatus.STALE, from_cache=True,
        fetched_at=stored.isoformat(), age_seconds=round(age, 1),
        message=(
            f"{message} Serving last-known-good data from {int(age)}s ago, "
            "marked STALE."
        ),
        errors=errors,
    )


def health_snapshot(db: Session) -> list[dict[str, Any]]:
    """Source health for the UI. Status is derived, never hardcoded."""
    rows = db.scalars(select(SourceHealth)).all()
    out = []
    for r in rows:
        policy = FRESHNESS.get(r.source_name, DEFAULT_FRESHNESS)
        out.append({
            "source_name": r.source_name,
            "status": r.status,
            "last_success_at": r.last_success_at.isoformat() if r.last_success_at else None,
            "last_failure_at": r.last_failure_at.isoformat() if r.last_failure_at else None,
            "last_source_timestamp": (
                r.last_source_timestamp.isoformat() if r.last_source_timestamp else None
            ),
            "fetched_at": r.fetched_at.isoformat() if r.fetched_at else None,
            "consecutive_failures": r.consecutive_failures,
            "stale_since": r.stale_since.isoformat() if r.stale_since else None,
            "last_error": r.last_error,
            "freshness_status": r.freshness_status,
            "circuit_open": circuit_is_open(r),
            "freshness_policy_seconds": policy.max_age_seconds,
        })
    return out
