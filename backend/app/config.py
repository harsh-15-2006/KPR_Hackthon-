"""Backwards-compatible shim.

The real configuration now lives in app/core/config.py. This module used to
hold a SECOND, divergent Settings class, which meant fixes applied to one
(such as the blank-env-var crash guard) silently did not apply to code
importing the other. Re-exporting keeps existing imports working against a
single source of truth.
"""
from app.core.config import BASE_DIR, Settings, get_settings  # noqa: F401

__all__ = ["BASE_DIR", "Settings", "get_settings"]
