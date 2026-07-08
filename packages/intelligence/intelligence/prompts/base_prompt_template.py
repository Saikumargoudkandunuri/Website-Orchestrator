"""Base contract for reusable, versioned prompt templates (§6.1).

Every AI capability is expressed as a :class:`BasePromptTemplate` subclass that:

* declares a stable ``capability`` name and an independent ``version`` (bumped
  whenever the prompt text changes — this is what makes
  ``AIInvocation.prompt_version`` meaningful for later audits/reruns);
* builds a provider-agnostic :class:`~intelligence.ai.provider_interface.AICompletionRequest`
  from a typed :class:`PromptContext`; and
* declares the JSON ``response_schema()`` its output must satisfy, which the
  validation pipeline enforces.

Prompts never receive raw HTML — only already-extracted, relevant fields via
:class:`PromptContext` — so they stay small, cheap, and testable independent of
crawler internals.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from intelligence.ai.provider_interface import AICompletionRequest

__all__ = ["PromptContext", "BasePromptTemplate"]


class PromptContext(BaseModel):
    """Already-extracted, relevant page context handed to a prompt (§6.1).

    Assembled by the calling service from the current ``KnowledgeObject`` plus
    raw crawl data. Every field is optional so a prompt can degrade gracefully
    when the crawler could not extract it (missing title, very short content,
    non-English page, etc.).
    """

    page_url: str = ""
    page_type: str | None = None
    language: str | None = None
    title: str | None = None
    meta_description: str | None = None
    slug: str | None = None
    headings: list[str] = Field(default_factory=list)
    first_paragraph: str | None = None
    content_excerpt: str | None = None  # bounded plain-text excerpt, never raw HTML
    word_count: int = 0
    primary_focus_keyphrase: str | None = None
    secondary_keyphrases: list[str] = Field(default_factory=list)
    top_keywords: list[str] = Field(default_factory=list)  # observed density-ranked
    images: list[dict[str, Any]] = Field(default_factory=list)  # {element_id, filename, alt}
    existing_schema_types: list[str] = Field(default_factory=list)
    known_internal_urls: list[str] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)


class BasePromptTemplate(ABC):
    """Abstract, versioned prompt template (§6.1)."""

    capability: str = ""
    version: str = "0.0.0"

    @abstractmethod
    def build(self, context: PromptContext) -> AICompletionRequest:
        """Build the provider-agnostic completion request for this capability."""
        ...

    @abstractmethod
    def response_schema(self) -> dict[str, Any]:
        """Return the JSON schema the model output must satisfy."""
        ...

    # --- Shared helpers ------------------------------------------------------

    def _request(
        self,
        *,
        prompt: str,
        system_prompt: str,
        context: PromptContext,
        max_tokens: int = 800,
        temperature: float = 0.2,
        json_mode: bool = True,
    ) -> AICompletionRequest:
        """Assemble an :class:`AICompletionRequest`, stamping audit metadata."""
        return AICompletionRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            json_mode=json_mode,
            metadata={
                "capability": self.capability,
                "prompt_version": self.version,
                "page_url": context.page_url,
            },
        )
