"""Intelligence-layer error hierarchy (Milestone 2).

Defined in this subsystem (rather than in ``core.exceptions``) so Milestone 1's
Core_Package stays untouched, while still rooting every intelligence failure at
the platform's single root :class:`core.exceptions.OrchestratorError` so a caller
can catch any orchestrator error uniformly.
"""

from __future__ import annotations

from core.exceptions import OrchestratorError

__all__ = [
    "IntelligenceError",
    "AIProviderError",
    "PromptError",
    "ValidationFailedError",
    "KnowledgeObjectError",
    "ImmutableFieldError",
]


class IntelligenceError(OrchestratorError):
    """Base for all Intelligence (Milestone 2) failures."""


class AIProviderError(IntelligenceError):
    """An AI provider call failed (unreachable, timeout, bad response, etc.).

    Carries only a credential-free summary; provider API keys are never placed
    in the message or attributes.
    """


class PromptError(IntelligenceError):
    """A prompt template could not be built or is misconfigured."""


class ValidationFailedError(IntelligenceError):
    """AI output failed validation and could not be corrected within retries."""


class KnowledgeObjectError(IntelligenceError):
    """A KnowledgeObject could not be read, composed, or persisted."""


class ImmutableFieldError(IntelligenceError):
    """A proposal targeted a field listed in ``immutable_fields`` (§4.12)."""
