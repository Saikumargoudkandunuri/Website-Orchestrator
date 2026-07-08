"""GeneratorEngine protocol and GenerationRequest/GeneratedArtifact models (§2).

Distinct from the analytical ``Engine`` protocol from Milestone 3 because
generation and analysis have different failure modes, retry semantics, and
downstream consumers:
- Analysis feeds Recommendation/Scoring.
- Generation feeds Governance (ContentAsset state machine).

The ``GeneratorEngine`` protocol is only implemented by:
- AI Content Generation Engine (§4.1)
- Reporting Engine (§4.6)

All other engines implement ``Engine`` from Milestone 3's engine_contract.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from engines.shared.engine_contract import AnalysisTarget
from intelligence.models.ai_invocation import AIInvocation

__all__ = [
    "GenerationRequest",
    "GeneratedArtifact",
    "GenerationError",
    "GeneratorEngine",
]


class GenerationRequest(BaseModel):
    """The common input envelope for every GeneratorEngine's ``generate()`` method."""

    target: AnalysisTarget
    generation_type: str  # e.g. "blog_post", "location_page", "executive_report"
    context: dict[str, Any] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)
    tenant_id: str = ""
    organization_id: str | None = None
    client_id: str | None = None


class GeneratedArtifact(BaseModel):
    """The common output from a GeneratorEngine's ``generate()`` method.

    Always starts in ``draft`` status; the governance flow takes it from there.
    """

    id: str
    generation_type: str
    content: Any  # typed, generation_type-specific payload
    ai_invocations: list[AIInvocation] = Field(default_factory=list)
    status: str = "draft"  # always starts here
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = 1


class GenerationError(BaseModel):
    """A typed generation failure."""

    message: str
    generation_type: str
    cause: str | None = None


@runtime_checkable
class GeneratorEngine(Protocol):
    """The single typed contract for generation engines (§2).

    Distinct from ``Engine`` — implemented only by ContentGeneration and Reporting.
    """

    engine_name: str
    engine_version: str

    def generate(
        self, request: GenerationRequest
    ) -> "Result[GeneratedArtifact, GenerationError]":  # type: ignore[name-defined]
        """Generate an artifact from ``request`` and return a typed result.

        Never raises for a handled failure — returns Err(GenerationError) instead.
        """
        ...

    def supports(self, request_type: str) -> bool:
        """Return ``True`` when this engine can generate ``request_type``."""
        ...
