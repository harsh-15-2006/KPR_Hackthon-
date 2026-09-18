"""Structured JSON logging with secret redaction.

Any value that looks like a credential is masked before it reaches a log
line, so an accidental `logger.info(payload)` cannot leak a key.
"""
import json
import logging
import re
import sys
from typing import Any

# Patterns that must never appear in a log line.
_SECRET_KEYS = re.compile(
    r"(api[_-]?key|secret|token|password|authorization|auth[_-]?token|bearer)",
    re.IGNORECASE,
)
_BEARER = re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]{8,}", re.IGNORECASE)

# Keys smuggled through a URL query string, e.g. ?api_key=... or &auth-token=...
# EPA explicitly supports ?api_key=, so a request URL can carry a live secret.
_QUERY_SECRET = re.compile(
    r"([?&](?:api[_-]?key|key|token|auth[_-]?token|apikey|access[_-]?token)=)[^&\s\"']+",
    re.IGNORECASE,
)


def redact(value: Any) -> Any:
    """Recursively mask anything that looks like a credential."""
    if isinstance(value, dict):
        return {
            k: ("***REDACTED***" if _SECRET_KEYS.search(str(k)) else redact(v))
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    if isinstance(value, str):
        value = _BEARER.sub(r"\1***REDACTED***", value)
        value = _QUERY_SECRET.sub(r"\1***REDACTED***", value)
        return value
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": redact(record.getMessage()),
        }
        for field in ("event", "source", "facility_id", "run_id", "status", "duration_ms"):
            if hasattr(record, field):
                payload[field] = redact(getattr(record, field))
        if record.exc_info:
            # Tracebacks routinely contain request URLs and header dicts, so
            # they must be redacted too - not passed through raw.
            payload["exc"] = redact(self.formatException(record.exc_info))
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    # uvicorn's own access log is noisy and duplicates ours
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
