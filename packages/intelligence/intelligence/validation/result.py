"""Shared validation result types (§7).

A single validator returns a :class:`ValidatorOutcome`; the pipeline aggregates
them into a :class:`ValidationResult` whose ``status`` (``passed`` | ``failed``
| ``corrected``) is what gets recorded on ``AIInvocation.validation_result``.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from intelligence.models.ai_invocation import ValidationOutcome

__all__ = ["ValidatorOutcome", "ValidationResult"]


class ValidatorOutcome(BaseModel):
    """The outcome of a single validator.

    * ``ok`` — the payload is acceptable (possibly after ``corrected`` changes);
    * ``corrected`` — the validator mutated the payload to make it acceptable
      (e.g. sanitized HTML, downgraded an unverifiable URL);
    * ``errors`` — human-readable reasons it failed (empty when ``ok``);
    * ``warnings`` — non-fatal flags for human review (e.g. keyword mismatch);
    * ``payload`` — the (possibly corrected) payload to carry forward.
    """

    ok: bool
    corrected: bool = False
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    payload: Any = None


class ValidationResult(BaseModel):
    """Aggregate result of running a capability's validator chain."""

    status: ValidationOutcome
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    payload: Any = None

    @property
    def passed(self) -> bool:
        return self.status in (ValidationOutcome.PASSED, ValidationOutcome.CORRECTED)
