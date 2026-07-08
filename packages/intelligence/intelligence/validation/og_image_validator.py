"""OG image validator (§13.4).

Validates a proposed Open Graph image payload: when ``source_image_element_id``
is set it must resolve to an existing image ``element_id`` on the same page
(supplied on the :class:`ValidationContext`), and any provided dimensions are
checked against the OG guideline (>= 1200x630). Missing dimensions leave
``dimensions_valid`` null (unknown) rather than failing.
"""

from __future__ import annotations

from intelligence.validation.context import ValidationContext
from intelligence.validation.result import ValidatorOutcome

__all__ = ["OgImageValidator", "OG_MIN_WIDTH", "OG_MIN_HEIGHT"]

OG_MIN_WIDTH = 1200
OG_MIN_HEIGHT = 630


class OgImageValidator:
    def validate(
        self, payload: dict, *, context: ValidationContext | None = None
    ) -> ValidatorOutcome:
        if not isinstance(payload, dict):
            return ValidatorOutcome(ok=True, payload=payload)

        errors: list[str] = []
        element_id = payload.get("source_image_element_id")
        if element_id:
            known = context.page_element_ids if context else set()
            if element_id not in known:
                errors.append(
                    f"source_image_element_id {element_id!r} does not resolve to an "
                    "image on this page"
                )

        width = payload.get("width")
        height = payload.get("height")
        if isinstance(width, int) and isinstance(height, int):
            payload["dimensions_valid"] = width >= OG_MIN_WIDTH and height >= OG_MIN_HEIGHT

        return ValidatorOutcome(ok=not errors, errors=errors, payload=payload)
