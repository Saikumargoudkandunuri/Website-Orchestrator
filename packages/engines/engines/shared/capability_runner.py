"""Shared AI capability runner for engine services (Milestone 3).

Reuses Milestone 2's AIProvider + ValidationPipeline + PromptRegistry exactly —
the engine layer adds no new AI abstraction, just a thin wrapper that:
1. Builds the prompt from ``PromptContext`` via the registry.
2. Calls the injected AIProvider.
3. Validates the response.
4. Returns the parsed payload or ``None`` on graceful failure.
No engine service imports a concrete AI provider directly.
"""

from __future__ import annotations

from typing import Any

from intelligence.ai.prompt_registry import PromptRegistry
from intelligence.ai.provider_interface import AIProvider
from intelligence.models.ai_invocation import AIInvocation, ValidationOutcome
from intelligence.prompts.base_prompt_template import PromptContext
from intelligence.repositories.ai_invocation_repository import AIInvocationRepository
from intelligence.validation.validation_pipeline import ValidationPipeline

# Re-export M2's CapabilityRunner unchanged — engine services instantiate it
# exactly as M2 services do (same AI discipline, same test double pattern).
from intelligence.services.capability_runner import (
    CapabilityResult,
    CapabilityRunner,
)

__all__ = ["CapabilityResult", "CapabilityRunner", "build_capability_runner"]


def build_capability_runner(
    *,
    provider: AIProvider,
    tenant_id: str,
    registry: PromptRegistry | None = None,
    invocation_repo: AIInvocationRepository | None = None,
    max_retries: int = 2,
) -> CapabilityRunner:
    """Convenience constructor for engine services."""
    from intelligence.ai.prompt_registry import default_prompt_registry

    return CapabilityRunner(
        provider=provider,
        prompt_registry=registry or default_prompt_registry(),
        pipeline=ValidationPipeline(),
        invocation_repo=invocation_repo,
        tenant_id=tenant_id,
        max_retries=max_retries,
    )
