"""External link validator (§13.4).

Stricter posture than internal-link suggestions: a proposed external
``suggested_target_url`` that is not syntactically valid (http/https with a host)
is **downgraded to null** rather than trusted, keeping the description-only
fallback so a hallucinated URL is never persisted as fact. This is a
``corrected`` outcome, not a failure — the suggestion survives, minus the
unverifiable URL.

A live HEAD-request resolvability check is intentionally out of scope this
milestone (documented in ``MILESTONE_2.md``); syntactic validation is the
guarantee provided now.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from intelligence.validation.context import ValidationContext
from intelligence.validation.result import ValidatorOutcome

__all__ = ["ExternalLinkValidator", "is_syntactically_valid_url"]


def is_syntactically_valid_url(url: str) -> bool:
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    return parts.scheme in ("http", "https") and bool(parts.netloc) and "." in parts.netloc


class ExternalLinkValidator:
    def __init__(self, field: str = "suggested_external_links") -> None:
        self._field = field

    def validate(
        self, payload: dict, *, context: ValidationContext | None = None
    ) -> ValidatorOutcome:
        if not isinstance(payload, dict):
            return ValidatorOutcome(ok=True, payload=payload)
        links = payload.get(self._field)
        if not isinstance(links, list):
            return ValidatorOutcome(ok=True, payload=payload)

        corrected = False
        warnings: list[str] = []
        for link in links:
            if not isinstance(link, dict):
                continue
            url = link.get("suggested_target_url")
            if url is not None and not is_syntactically_valid_url(str(url)):
                link["suggested_target_url"] = None
                corrected = True
                warnings.append(
                    f"downgraded unverifiable external URL to null: {url!r}"
                )
        return ValidatorOutcome(
            ok=True, corrected=corrected, warnings=warnings, payload=payload
        )
