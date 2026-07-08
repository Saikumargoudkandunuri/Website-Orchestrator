"""URL/slug validator (§7).

Validates an AI-proposed slug: URL-safe characters only (lowercase letters,
digits, hyphens), a length limit, no leading/trailing/double hyphens, and no
collision with an existing slug (checked against the set supplied on the
:class:`ValidationContext`, which the service populates from the repository).
"""

from __future__ import annotations

import re

from intelligence.validation.context import ValidationContext
from intelligence.validation.result import ValidatorOutcome

__all__ = ["UrlSlugValidator", "is_valid_slug", "MAX_SLUG_LENGTH"]

MAX_SLUG_LENGTH = 75
_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def is_valid_slug(slug: str) -> bool:
    """Return ``True`` when ``slug`` is a clean, URL-safe slug."""
    return bool(slug) and len(slug) <= MAX_SLUG_LENGTH and bool(_SLUG_RE.match(slug))


class UrlSlugValidator:
    def __init__(self, slug_field: str = "slug") -> None:
        self._field = slug_field

    def validate(
        self, payload: dict, *, context: ValidationContext | None = None
    ) -> ValidatorOutcome:
        slug = payload.get(self._field) if isinstance(payload, dict) else None
        if not isinstance(slug, str):
            return ValidatorOutcome(ok=False, errors=["slug is missing or not a string"])

        errors: list[str] = []
        if not is_valid_slug(slug):
            errors.append(
                f"slug {slug!r} is not URL-safe (lowercase, digits, single hyphens, "
                f"<= {MAX_SLUG_LENGTH} chars)"
            )
        existing = context.existing_slugs if context else set()
        if slug in existing:
            errors.append(f"slug {slug!r} collides with an existing page slug")
        return ValidatorOutcome(ok=not errors, errors=errors, payload=payload)
