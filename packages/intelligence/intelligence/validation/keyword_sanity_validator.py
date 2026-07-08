"""Keyword sanity validator (§7.5, §13.4).

Cross-checks AI keyword claims against the deterministic, observed
``keyword_density`` / ``keyword_placement`` ground truth (§4.4). Two behaviors:

* **Secondary keyphrase count (§13.4)** — enforced to the range 4-10; out-of-
  range output is a hard failure so the orchestrator retries with the constraint
  restated (never silently truncate/pad).
* **Focus-keyphrase plausibility (§7.5)** — if the AI's ``primary_focus_keyphrase``
  shares no token with the observed top keywords, it is *flagged* (warning) for
  human review, not rejected — the observed data is advisory here.
"""

from __future__ import annotations

import re

from intelligence.validation.context import ValidationContext
from intelligence.validation.result import ValidatorOutcome

__all__ = ["KeywordSanityValidator", "SECONDARY_MIN", "SECONDARY_MAX"]

SECONDARY_MIN = 4
SECONDARY_MAX = 10


class KeywordSanityValidator:
    def validate(
        self, payload: dict, *, context: ValidationContext | None = None
    ) -> ValidatorOutcome:
        if not isinstance(payload, dict):
            return ValidatorOutcome(ok=False, errors=["keyword payload is not an object"])

        errors: list[str] = []
        warnings: list[str] = []

        secondary = payload.get("secondary_keyphrases")
        if isinstance(secondary, list):
            n = len(secondary)
            if n < SECONDARY_MIN or n > SECONDARY_MAX:
                errors.append(
                    f"secondary_keyphrases count {n} is outside the required "
                    f"range {SECONDARY_MIN}-{SECONDARY_MAX}"
                )

        focus = payload.get("primary_focus_keyphrase")
        top = [k.lower() for k in (context.top_keywords if context else [])]
        if isinstance(focus, str) and focus.strip() and top:
            focus_tokens = set(_tokenize(focus))
            top_tokens = set()
            for kw in top:
                top_tokens.update(_tokenize(kw))
            if focus_tokens and not (focus_tokens & top_tokens):
                warnings.append(
                    f"AI focus keyphrase {focus!r} shares no token with the "
                    "observed top keywords; flagged for human review"
                )

        return ValidatorOutcome(
            ok=not errors, errors=errors, warnings=warnings, payload=payload
        )


def _tokenize(text: str) -> list[str]:
    return [t for t in re.split(r"\W+", text.lower()) if t]
