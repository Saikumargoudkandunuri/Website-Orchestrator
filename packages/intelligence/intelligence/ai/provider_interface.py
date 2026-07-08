"""The provider-agnostic AI interface (§5.1).

A single internal contract every concrete AI vendor adapter implements, so the
rest of the system depends on the *interface* — never on OpenAI/Claude/Gemini/
etc. directly. Switching providers is a configuration change, never a code
change, in any service outside ``intelligence/ai/``.

Handled failures surface as a typed :class:`~core.results.Err` carrying an
:class:`~intelligence.errors.AIProviderError` (Req 15.5 discipline), never as a
raw exception across the boundary.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from core.results import Result
from intelligence.errors import AIProviderError
from intelligence.models.ai_invocation import TokenUsage

__all__ = [
    "AICompletionRequest",
    "AICompletionResponse",
    "AIProvider",
]


class AICompletionRequest(BaseModel):
    """A provider-agnostic completion request (§5.1).

    ``metadata`` carries capability/prompt_version/page_id for logging and audit
    only; adapters must not forward it to the provider wire payload.
    """

    prompt: str
    system_prompt: str | None = None
    max_tokens: int = 1024
    temperature: float = 0.2
    json_mode: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class AICompletionResponse(BaseModel):
    """A provider-agnostic completion response (§5.1)."""

    raw_text: str
    tokens_used: TokenUsage | None = None
    model: str
    finish_reason: str | None = None


@runtime_checkable
class AIProvider(Protocol):
    """The single interface every provider adapter implements (§5.1)."""

    def complete(
        self, request: AICompletionRequest
    ) -> Result[AICompletionResponse, AIProviderError]:
        """Perform one completion; return :class:`~core.results.Ok` on success or
        :class:`~core.results.Err` with an :class:`AIProviderError` on a handled
        failure. Never raises for a handled failure."""
        ...

    def name(self) -> str:
        """The provider's stable identifier (e.g. ``"openai"``)."""
        ...

    def supports_json_mode(self) -> bool:
        """Whether the provider can be asked to return strict JSON."""
        ...
