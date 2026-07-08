"""Provider-agnostic AI invocation audit record (§5.3).

Every call through an :class:`~intelligence.ai.provider_interface.AIProvider` is
wrapped by the orchestrator into an ``AIInvocation`` so a future Reviewer agent
(or a human debugging today) can audit, cost-account, or re-run any past AI
decision. The **raw** pre-validation response is retained alongside the
validation outcome — never discard raw AI output once validated/transformed.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field

__all__ = ["TokenUsage", "ValidationOutcome", "AIInvocation"]


class TokenUsage(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class ValidationOutcome(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    CORRECTED = "corrected"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AIInvocation(BaseModel):
    id: str
    tenant_id: str
    page_id: str | None = None
    capability: str
    prompt_version: str
    provider: str
    model: str
    tokens_used: TokenUsage | None = None
    cost_estimate: float | None = None
    confidence: float | None = None
    raw_response: str = ""  # pre-validation output, retained for auditability
    validation_result: ValidationOutcome = ValidationOutcome.PASSED
    created_at: datetime = Field(default_factory=_utc_now)
