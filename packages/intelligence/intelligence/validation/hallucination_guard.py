"""Hallucination guard (§7).

Capability-specific sanity checks against ground truth already known about the
page. For factual capabilities (``faq_generator``, ``meta_generator``) it flags
generated text that references concrete tokens — prices, phone numbers — not
observed anywhere in the crawled content. It flags (warning) rather than hard-
rejecting borderline cases, but rejects clear fabrications for factual outputs.
"""

from __future__ import annotations

import re

from intelligence.validation.context import ValidationContext
from intelligence.validation.result import ValidatorOutcome

__all__ = ["HallucinationGuard"]

_PRICE_RE = re.compile(r"(?:[$€£₹]\s?\d[\d,]*(?:\.\d+)?|\b\d[\d,]*\s?(?:USD|EUR|GBP|INR)\b)")
_PHONE_RE = re.compile(r"\+?\d[\d\s().-]{7,}\d")


class HallucinationGuard:
    """Checks generated text does not introduce unobserved concrete claims."""

    def __init__(self, text_fields: list[str], *, factual: bool = True) -> None:
        self._text_fields = text_fields
        self._factual = factual

    def validate(
        self, payload: dict, *, context: ValidationContext | None = None
    ) -> ValidatorOutcome:
        observed = (context.observed_text if context else "") or ""
        observed_lower = observed.lower()
        generated = self._collect_text(payload)
        errors: list[str] = []
        warnings: list[str] = []

        for price in set(_PRICE_RE.findall(generated)):
            if self._normalize(price) not in self._normalize(observed_lower):
                msg = f"generated text cites a price not present on the page: {price!r}"
                (errors if self._factual else warnings).append(msg)

        for phone in set(_PHONE_RE.findall(generated)):
            digits = re.sub(r"\D", "", phone)
            if len(digits) >= 7 and digits not in re.sub(r"\D", "", observed):
                msg = f"generated text cites a phone number not on the page: {phone!r}"
                (errors if self._factual else warnings).append(msg)

        return ValidatorOutcome(
            ok=not errors, errors=errors, warnings=warnings, payload=payload
        )

    def _collect_text(self, payload: object) -> str:
        parts: list[str] = []

        def walk(value: object) -> None:
            if isinstance(value, str):
                parts.append(value)
            elif isinstance(value, dict):
                for v in value.values():
                    walk(v)
            elif isinstance(value, list):
                for v in value:
                    walk(v)

        walk(payload)
        return " ".join(parts)

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"\s+", "", text)
