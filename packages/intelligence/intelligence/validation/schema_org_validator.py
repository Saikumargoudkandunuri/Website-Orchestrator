"""schema.org JSON-LD validator (§7).

Validates AI-generated JSON-LD before it is allowed into
``SchemaIntelligenceSection.generated_jsonld``: it must parse as JSON, be an
object (or ``@graph`` array of objects), and carry a ``@context`` referencing
schema.org plus a ``@type``. Type names are checked against a known schema.org
type set (extensible) — unknown types are flagged, not silently trusted.
"""

from __future__ import annotations

import json
from typing import Any

from intelligence.validation.context import ValidationContext
from intelligence.validation.result import ValidatorOutcome

__all__ = ["SchemaOrgValidator", "KNOWN_SCHEMA_TYPES"]

#: A pragmatic set of common schema.org types (extensible). Unknown types are
#: flagged for review rather than rejected outright.
KNOWN_SCHEMA_TYPES: frozenset[str] = frozenset(
    {
        "Article", "BlogPosting", "NewsArticle", "WebPage", "WebSite",
        "Organization", "LocalBusiness", "Product", "Offer", "Service",
        "BreadcrumbList", "FAQPage", "Question", "Answer", "Person",
        "Review", "AggregateRating", "Event", "Recipe", "VideoObject",
        "ImageObject", "HowTo", "ItemList", "SearchAction", "ContactPoint",
        "PostalAddress",
    }
)


class SchemaOrgValidator:
    """Validates the ``jsonld`` string field of a schema-generation payload."""

    def __init__(self, jsonld_field: str = "jsonld") -> None:
        self._field = jsonld_field

    def validate(
        self, payload: dict, *, context: ValidationContext | None = None
    ) -> ValidatorOutcome:
        raw = payload.get(self._field) if isinstance(payload, dict) else None
        if not isinstance(raw, str) or not raw.strip():
            return ValidatorOutcome(ok=False, errors=["missing JSON-LD string"])

        try:
            doc = json.loads(raw)
        except (ValueError, TypeError):
            return ValidatorOutcome(ok=False, errors=["JSON-LD is not valid JSON"])

        errors: list[str] = []
        warnings: list[str] = []
        nodes = doc.get("@graph") if isinstance(doc, dict) and "@graph" in doc else [doc]
        if not isinstance(nodes, list):
            nodes = [nodes]

        context_ok = isinstance(doc, dict) and "schema.org" in str(doc.get("@context", ""))
        if not context_ok:
            errors.append("JSON-LD is missing an @context referencing schema.org")

        for node in nodes:
            if not isinstance(node, dict):
                errors.append("JSON-LD node is not an object")
                continue
            node_type = node.get("@type")
            if not node_type:
                errors.append("JSON-LD node is missing @type")
                continue
            types = node_type if isinstance(node_type, list) else [node_type]
            for t in types:
                if t not in KNOWN_SCHEMA_TYPES:
                    warnings.append(f"unrecognized schema.org @type: {t!r}")

        return ValidatorOutcome(
            ok=not errors, errors=errors, warnings=warnings, payload=payload
        )
