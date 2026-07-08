"""HTML sanitizer for AI output that may be rendered/published (§7).

Dependency-free, allowlist-oriented sanitizer: it removes ``<script>``/
``<style>`` blocks entirely (including content), strips event-handler attributes
(``onclick`` etc.), neutralizes ``javascript:`` URLs, and drops a small set of
dangerous tags. Applied to ``content_rewrite``/``faq_generator``/
``content_expansion`` output before it is stored or published.

This is intentionally conservative and self-contained (no ``bleach`` dependency);
it never trusts AI-produced markup.
"""

from __future__ import annotations

import re

from intelligence.validation.context import ValidationContext
from intelligence.validation.result import ValidatorOutcome

__all__ = ["HtmlSanitizer", "sanitize_html"]

_BLOCK_TAG_RE = re.compile(
    r"<(script|style|iframe|object|embed|form)\b[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)
_SELF_TAG_RE = re.compile(
    r"<\s*(script|style|iframe|object|embed|form|link|meta|base)\b[^>]*/?>",
    re.IGNORECASE,
)
_EVENT_ATTR_RE = re.compile(r"\son[a-z]+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", re.IGNORECASE)
_JS_URI_RE = re.compile(r"(href|src)\s*=\s*(\"|')?\s*javascript:[^\"'>\s]*(\"|')?", re.IGNORECASE)


def sanitize_html(text: str) -> tuple[str, bool]:
    """Return ``(sanitized_text, changed)``."""
    if not text:
        return text, False
    original = text
    text = _BLOCK_TAG_RE.sub("", text)
    text = _SELF_TAG_RE.sub("", text)
    text = _EVENT_ATTR_RE.sub("", text)
    text = _JS_URI_RE.sub("", text)
    return text, text != original


class HtmlSanitizer:
    """Sanitizes string content on an AI payload.

    With explicit ``fields`` only those top-level keys are sanitized; with an
    empty ``fields`` list every string leaf (including nested ones, e.g. FAQ
    answers) is sanitized recursively.
    """

    def __init__(self, fields: list[str] | None = None) -> None:
        self._fields = fields or []

    def validate(
        self, payload: dict, *, context: ValidationContext | None = None
    ) -> ValidatorOutcome:
        if not isinstance(payload, dict):
            return ValidatorOutcome(ok=True, payload=payload)
        if self._fields:
            changed_any = False
            for field in self._fields:
                value = payload.get(field)
                if isinstance(value, str):
                    sanitized, changed = sanitize_html(value)
                    if changed:
                        payload[field] = sanitized
                        changed_any = True
            return ValidatorOutcome(ok=True, corrected=changed_any, payload=payload)
        # Recursive mode: sanitize every string leaf in place.
        changed = self._sanitize_in_place(payload)
        return ValidatorOutcome(ok=True, corrected=changed, payload=payload)

    def _sanitize_in_place(self, node: object) -> bool:
        changed = False
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(value, str):
                    sanitized, did = sanitize_html(value)
                    if did:
                        node[key] = sanitized
                        changed = True
                else:
                    changed = self._sanitize_in_place(value) or changed
        elif isinstance(node, list):
            for i, value in enumerate(node):
                if isinstance(value, str):
                    sanitized, did = sanitize_html(value)
                    if did:
                        node[i] = sanitized
                        changed = True
                else:
                    changed = self._sanitize_in_place(value) or changed
        return changed
