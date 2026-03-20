from __future__ import annotations

from typing import Any

SENSITIVE_KEYS = {"token", "access_token", "refresh_token", "authorization", "bearer"}


def redact_sensitive_fields(value: Any) -> Any:
    """Return a deep copy of *value* with secret-bearing keys removed.

    This is a defense-in-depth helper for inventory / audit / monitoring serialization.
    It intentionally removes raw token values while preserving non-secret token health
    metadata such as source, expires_at, status, and notes.
    """
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).lower() in SENSITIVE_KEYS:
                continue
            cleaned[key] = redact_sensitive_fields(item)
        return cleaned
    if isinstance(value, list):
        return [redact_sensitive_fields(item) for item in value]
    return value
