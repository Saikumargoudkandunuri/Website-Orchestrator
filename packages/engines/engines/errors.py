"""Engine-layer error hierarchy (Milestone 3).

Defined in-package so Milestone 1/2 Core_Package stays untouched, while every
engine failure roots at :class:`~core.exceptions.OrchestratorError` so callers
can catch any orchestrator error uniformly.
"""

from __future__ import annotations

from core.exceptions import OrchestratorError

__all__ = [
    "EngineError",
    "EngineAnalysisError",
    "EngineNotFoundError",
    "EngineDataProviderError",
    "EngineOrchestratorError",
    "EngineStorageError",
]


class EngineError(OrchestratorError):
    """Base for all Milestone 3 engine failures."""


class EngineAnalysisError(EngineError):
    """An engine's analysis step failed."""


class EngineNotFoundError(EngineError):
    """No engine is registered for the requested name."""


class EngineDataProviderError(EngineError):
    """A third-party SEO data provider call failed (Competitor/Backlink engines).

    Carries only a safe, credential-free summary; provider API keys are never
    placed in the message or attributes.
    """


class EngineOrchestratorError(EngineError):
    """The engine orchestrator failed to schedule or collect engine results."""


class EngineStorageError(EngineError):
    """An engine's output could not be persisted or loaded."""
