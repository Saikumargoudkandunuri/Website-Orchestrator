"""Boundary validators for onboarding inputs.

These are pure functions reused by the services and routes to reject malformed
input before any subsystem runs. They raise :class:`~core.exceptions.OrchestratorError`
subclasses so the API can map them to explicit HTTP failures.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from core.exceptions import OrchestratorError

__all__ = ["ValidationError", "validate_non_blank", "validate_url", "validate_enum"]


class ValidationError(OrchestratorError):
    """Raised when an onboarding input fails validation (mapped to 422)."""


def validate_non_blank(value: str | None, field: str) -> str:
    """Return ``value`` stripped, or raise if blank."""
    if value is None or not value.strip():
        raise ValidationError(f"{field} must be a non-blank value")
    return value.strip()


def validate_url(value: str | None) -> str:
    """Validate that ``value`` is an http/https URL; return the stripped URL."""
    cleaned = validate_non_blank(value, "url")
    parts = urlsplit(cleaned)
    if parts.scheme not in ("http", "https"):
        raise ValidationError("url must use the http or https scheme")
    if not parts.hostname:
        raise ValidationError("url must include a valid host")
    return cleaned


def validate_enum(value: str, allowed: set[str], field: str) -> str:
    """Validate ``value`` is one of ``allowed`` (case-insensitive)."""
    if value is None:
        raise ValidationError(f"{field} must not be empty")
    lowered = value.strip().lower()
    if lowered not in {a.lower() for a in allowed}:
        raise ValidationError(
            f"{field} must be one of {sorted(allowed)}; got {value!r}"
        )
    # Return the canonical casing.
    for candidate in allowed:
        if candidate.lower() == lowered:
            return candidate
    return value  # pragma: no cover - unreachable
