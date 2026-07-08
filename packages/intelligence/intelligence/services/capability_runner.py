"""Shared AI-capability execution: prompt -> provider -> validate -> audit (§7, §8).

Every AI-backed analyzer routes through :class:`CapabilityRunner`, which owns the
one place that:

1. builds the capability's prompt from a :class:`PromptContext`;
2. calls the injected :class:`AIProvider` (single attempt per try);
3. validates the raw output through the :class:`ValidationPipeline`;
4. on a validation failure, retries (bounded, default max 2) with the validation
   error fed back into the prompt;
5. records **every** attempt as an :class:`AIInvocation` (raw response retained,
   validation result recorded); and
6. returns the validated payload, or ``None`` when generation/validation could
   not succeed — so an analyzer degrades gracefully (leaves fields null) rather
   than persisting invalid data or crashing.
"""

from __future__ import annotations

import uuid

from core.results import is_ok
from intelligence.ai.prompt_registry import PromptRegistry
from intelligence.ai.provider_interface import AICompletionRequest, AIProvider
from intelligence.models.ai_invocation import AIInvocation, ValidationOutcome
from intelligence.prompts.base_prompt_template import PromptContext
from intelligence.repositories.ai_invocation_repository import AIInvocationRepository
from intelligence.validation.context import ValidationContext
from intelligence.validation.validation_pipeline import ValidationPipeline

__all__ = ["CapabilityRunner", "CapabilityResult"]


class CapabilityResult:
    """Outcome of running one capability: the payload (or ``None``) + warnings."""

    __slots__ = ("payload", "warnings", "invocations")

    def __init__(
        self, payload: dict | None, warnings: list[str], invocations: list[AIInvocation]
    ) -> None:
        self.payload = payload
        self.warnings = warnings
        self.invocations = invocations


class CapabilityRunner:
    def __init__(
        self,
        *,
        provider: AIProvider,
        prompt_registry: PromptRegistry,
        pipeline: ValidationPipeline,
        invocation_repo: AIInvocationRepository | None = None,
        tenant_id: str,
        max_retries: int = 2,
    ) -> None:
        self._provider = provider
        self._registry = prompt_registry
        self._pipeline = pipeline
        self._invocations = invocation_repo
        self._tenant_id = tenant_id
        self._max_retries = max_retries

    def run(
        self,
        capability: str,
        context: PromptContext,
        *,
        page_id: str | None,
        validation_context: ValidationContext | None = None,
    ) -> CapabilityResult:
        template = self._registry.get(capability)
        schema = template.response_schema()
        request = template.build(context)
        vctx = validation_context or ValidationContext(capability=capability)

        warnings: list[str] = []
        invocations: list[AIInvocation] = []
        last_errors: list[str] = []

        for attempt in range(self._max_retries + 1):
            result = self._provider.complete(request)
            if not is_ok(result):
                # Provider failure: record and stop (graceful null).
                inv = self._record(
                    capability, template.version, page_id,
                    raw="", outcome=ValidationOutcome.FAILED,
                )
                invocations.append(inv)
                return CapabilityResult(None, warnings, invocations)

            response = result.unwrap()
            vres = self._pipeline.validate(
                capability, response.raw_text, schema, context=vctx
            )
            inv = self._record(
                capability, template.version, page_id,
                raw=response.raw_text, outcome=vres.status,
                model=response.model,
            )
            invocations.append(inv)
            warnings.extend(vres.warnings)

            if vres.passed:
                return CapabilityResult(vres.payload, warnings, invocations)

            last_errors = vres.errors
            # Feed the validation error back into the prompt for the next attempt.
            request = self._retry_request(request, last_errors)

        # Retries exhausted: graceful null, invalid data never persisted.
        return CapabilityResult(None, warnings, invocations)

    # --- Helpers -------------------------------------------------------------

    def _retry_request(
        self, request: AICompletionRequest, errors: list[str]
    ) -> AICompletionRequest:
        note = (
            "\n\nYour previous response failed validation: "
            + "; ".join(errors[:5])
            + ". Return corrected, schema-valid JSON."
        )
        return request.model_copy(update={"prompt": request.prompt + note})

    def _record(
        self,
        capability: str,
        prompt_version: str,
        page_id: str | None,
        *,
        raw: str,
        outcome: ValidationOutcome,
        model: str | None = None,
    ) -> AIInvocation:
        invocation = AIInvocation(
            id=uuid.uuid4().hex,
            tenant_id=self._tenant_id,
            page_id=page_id,
            capability=capability,
            prompt_version=prompt_version,
            provider=self._provider.name(),
            model=model or "unknown",
            raw_response=raw,
            validation_result=outcome,
        )
        if self._invocations is not None:
            self._invocations.save(self._tenant_id, invocation)
        return invocation
