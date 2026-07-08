"""Growth-layer error hierarchy (Milestone 4).

Defined in-package so Milestone 1/2/3 packages stay untouched, while every
growth failure roots at :class:`~core.exceptions.OrchestratorError` so callers
can catch any orchestrator error uniformly.
"""

from __future__ import annotations

from core.exceptions import OrchestratorError

__all__ = [
    "GrowthError",
    "GrowthAnalysisError",
    "GrowthGenerationError",
    "GrowthStorageError",
    "GrowthDataProviderError",
    "GrowthGovernanceError",
    "GrowthJobError",
    "GrowthAutomationError",
    "GrowthTenantError",
    "GrowthNotFoundError",
    "GrowthPermissionError",
    "GrowthAuthenticationError",
]


class GrowthError(OrchestratorError):
    """Base for all Milestone 4 growth failures."""


class GrowthAnalysisError(GrowthError):
    """A growth engine's analysis step failed."""


class GrowthGenerationError(GrowthError):
    """A growth engine's generation step failed (ContentGeneration/Reporting)."""


class GrowthStorageError(GrowthError):
    """A growth engine's output could not be persisted or loaded."""


class GrowthDataProviderError(GrowthError):
    """A third-party data provider call failed.

    Carries only a safe, credential-free summary.
    """


class GrowthGovernanceError(GrowthError):
    """A ContentAsset governance operation failed."""


class GrowthJobError(GrowthError):
    """A background job failed to enqueue, run, or complete."""


class GrowthAutomationError(GrowthError):
    """An automation rule failed to evaluate or dispatch."""


class GrowthTenantError(GrowthError):
    """A tenancy resolution or isolation error."""


class GrowthNotFoundError(GrowthError):
    """A requested growth entity was not found."""


class GrowthPermissionError(GrowthError):
    """The authenticated principal lacks permission for the requested operation."""


class GrowthAuthenticationError(GrowthError):
    """The request did not present valid Growth API credentials."""
