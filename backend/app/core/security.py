"""Password hashing and JWT issuing.

Rules enforced here rather than left to convention:
  * Passwords are bcrypt-hashed with a per-password salt. The plaintext is
    never stored, never logged, and never returned by any endpoint.
  * bcrypt silently truncates input beyond 72 BYTES, so a longer password is
    rejected outright instead of being quietly weakened.
  * The JWT secret must be at least 32 bytes. PyJWT warns below that, and a
    short HMAC key is a real weakness - so a missing secret is generated at
    startup rather than defaulting to something guessable.
"""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

ALGORITHM = "HS256"
TOKEN_TTL_HOURS = 8
BCRYPT_ROUNDS = 12
MAX_PASSWORD_BYTES = 72  # bcrypt's hard limit
MIN_PASSWORD_LEN = 8

_RUNTIME_SECRET: str | None = None


def _secret() -> str:
    """The signing key. Never logged."""
    global _RUNTIME_SECRET
    configured = (get_settings().jwt_secret or "").strip()
    if len(configured.encode()) >= 32:
        return configured
    if _RUNTIME_SECRET is None:
        _RUNTIME_SECRET = secrets.token_urlsafe(48)
        logger.warning(
            "JWT_SECRET is missing or shorter than 32 bytes. A random secret was "
            "generated for this process. Sessions will not survive a restart - set "
            "JWT_SECRET in backend/.env for persistent logins."
        )
    return _RUNTIME_SECRET


# ----------------------------------------------------------------- passwords


def validate_password(password: str) -> str | None:
    """Return a human-readable reason the password is unacceptable, or None."""
    if len(password) < MIN_PASSWORD_LEN:
        return f"Password must be at least {MIN_PASSWORD_LEN} characters."
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        return (
            f"Password is too long ({len(password.encode())} bytes). bcrypt only "
            f"uses the first {MAX_PASSWORD_BYTES} bytes, so longer passwords are "
            "not accepted."
        )
    if password.lower() in {"password", "12345678", "qwertyui", "changeme"}:
        return "That password is too common. Choose something else."
    return None


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    """Constant-time check. Any malformed hash fails closed."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# --------------------------------------------------------------------- JWT


def create_token(user_id: int, email: str, role: str, company_id: int | None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "company_id": company_id,
        "iat": now,
        "exp": now + timedelta(hours=TOKEN_TTL_HOURS),
    }
    return jwt.encode(payload, _secret(), algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any] | None:
    """Return the claims, or None for anything invalid or expired."""
    try:
        return jwt.decode(token, _secret(), algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def slugify_scope(name: str) -> str:
    """Company name -> a stable scope_key used to partition its data."""
    cleaned = "".join(c.lower() if c.isalnum() else "-" for c in name.strip())
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-")[:100] or "company"
