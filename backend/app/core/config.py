"""Application configuration.

Every secret is read from the environment. Nothing is hardcoded, and no
secret is ever returned by an API route or written to a log. The
`*_configured` properties exist so the UI can show a truthful
"UNAVAILABLE" state without the key itself ever leaving the backend.
"""
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent

_PLACEHOLDERS = {"", "your_key_here", "changeme", "none", "null"}


def _is_set(value: str) -> bool:
    return value.strip().lower() not in _PLACEHOLDERS


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- EPA Clean Air Markets (US power sector only) ---
    epa_api_key: str = ""
    epa_base_url: str = "https://api.epa.gov/easey"

    # --- Electricity Maps (GRID carbon intensity, not facility consumption) ---
    electricity_maps_api_key: str = ""
    electricity_maps_base_url: str = "https://api.electricitymaps.com"
    electricity_maps_default_zone: str = ""

    # --- Climatiq (activity data -> emissions) ---
    climatiq_api_key: str = ""
    climatiq_base_url: str = "https://api.climatiq.io"
    climatiq_data_version: str = ""

    # --- Supabase ---
    supabase_url: str = ""
    supabase_publishable_key: str = ""
    supabase_secret_key: str = ""
    database_url: str = ""

    # --- Gemini (explanation layer only) ---
    gemini_api_key: str = ""
    gemini_model: str = ""
    gemini_enabled: bool = False

    # --- App ---
    cors_origins: str = "http://localhost:5173,http://localhost:5174"
    log_level: str = "INFO"
    http_timeout_seconds: float = 30.0
    refresh_interval_seconds: int = 0

    # A blank value in .env (e.g. `GEMINI_ENABLED=`) must not crash startup.
    @field_validator("gemini_enabled", mode="before")
    @classmethod
    def _blank_bool_is_false(cls, v: object) -> object:
        if v is None:
            return False
        if isinstance(v, str) and v.strip() == "":
            return False
        return v

    # Likewise a blank numeric must fall back to its default, not explode.
    # Blank refresh interval means "polling disabled".
    @field_validator("refresh_interval_seconds", mode="before")
    @classmethod
    def _blank_refresh_is_disabled(cls, v: object) -> object:
        if v is None or (isinstance(v, str) and v.strip() == ""):
            return 0
        return v

    # A blank timeout must NOT become 0 - that would mean no time to respond.
    @field_validator("http_timeout_seconds", mode="before")
    @classmethod
    def _blank_timeout_is_default(cls, v: object) -> object:
        if v is None or (isinstance(v, str) and v.strip() == ""):
            return 30.0
        return v

    # ---------- availability flags (safe to expose to the UI) ----------

    @property
    def epa_configured(self) -> bool:
        return _is_set(self.epa_api_key)

    @property
    def electricity_maps_configured(self) -> bool:
        return _is_set(self.electricity_maps_api_key)

    @property
    def climatiq_configured(self) -> bool:
        return _is_set(self.climatiq_api_key)

    @property
    def supabase_configured(self) -> bool:
        return _is_set(self.supabase_url) and _is_set(self.supabase_secret_key)

    @property
    def gemini_configured(self) -> bool:
        return self.gemini_enabled and _is_set(self.gemini_api_key) and _is_set(self.gemini_model)

    # ---------- database ----------

    @property
    def database_url_problem(self) -> str | None:
        """Explain why DATABASE_URL is unusable, or None if it is fine.

        A very common mistake is pasting the Supabase PROJECT URL
        (https://<ref>.supabase.co) into DATABASE_URL, which expects a
        POSTGRES CONNECTION STRING. Left unguarded that raises
        NoSuchModuleError('sqlalchemy.dialects:https') at import time and
        takes the whole app down before it can report anything useful.
        """
        url = self.database_url.strip()
        if not url:
            return None
        if url.startswith(("postgresql://", "postgres://", "postgresql+psycopg://", "sqlite:///")):
            return None
        if url.startswith(("http://", "https://")):
            return (
                "DATABASE_URL looks like a Supabase PROJECT URL, not a Postgres "
                "connection string. Put that value in SUPABASE_URL instead, and set "
                "DATABASE_URL from Project Settings -> Database -> Connection string "
                "(use the Session pooler, port 5432). It should start with postgresql://"
            )
        return (
            "DATABASE_URL is not a recognised connection string. It should start "
            "with postgresql:// (Supabase) or be left blank to use local SQLite."
        )

    @staticmethod
    def _encode_password(url: str) -> str:
        """Percent-encode reserved characters in the password.

        Supabase generates passwords containing characters like '@', ':' and
        '/', which are URL delimiters. Pasting such a password verbatim gives
        a URL with two '@' signs, and the driver then splits at the wrong one
        and tries to resolve a host literally named '@aws-0-...'.
        Encoding the password makes the pasted string work as-is.
        """
        from urllib.parse import quote

        if "://" not in url:
            return url
        scheme, rest = url.split("://", 1)
        if "@" not in rest:
            return url
        # Split at the LAST '@' so an '@' inside the password stays with it.
        userinfo, hostpart = rest.rsplit("@", 1)
        if ":" not in userinfo:
            return url
        user, password = userinfo.split(":", 1)
        # safe="" so every reserved character is encoded. Already-encoded
        # passwords are left alone by checking for a '%' escape first.
        if "%" in password:
            return url
        return f"{scheme}://{user}:{quote(password, safe='')}@{hostpart}"

    @property
    def sqlalchemy_url(self) -> str:
        """Supabase Postgres when DATABASE_URL is valid, else a local dev SQLite file.

        A malformed DATABASE_URL falls back to SQLite rather than crashing, so
        the app still starts and can TELL the user what is wrong.
        """
        url = self.database_url.strip()
        if url and self.database_url_problem is None:
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+psycopg://", 1)
            elif url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+psycopg://", 1)
            return self._encode_password(url)
        return f"sqlite:///{BASE_DIR / 'local_dev.db'}"

    @property
    def using_sqlite_fallback(self) -> bool:
        return not self.database_url.strip() or self.database_url_problem is not None

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def integration_status(self) -> dict[str, bool]:
        """Booleans only. Never the keys themselves.

        Note `supabase_rest` is about the PostgREST/Data API keys, which are
        OPTIONAL. The Postgres connection used for persistence is reported
        separately under /api/health -> database, because a project can be
        (and normally is) connected to Supabase Postgres without those keys.
        """
        return {
            "epa": self.epa_configured,
            "electricity_maps": self.electricity_maps_configured,
            "climatiq": self.climatiq_configured,
            "supabase_rest": self.supabase_configured,
            "gemini": self.gemini_configured,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
