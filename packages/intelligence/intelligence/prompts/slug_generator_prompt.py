"""Slug generator prompt (§6, capability ``slug_generator``)."""

from __future__ import annotations

from typing import Any

from intelligence.ai.provider_interface import AICompletionRequest
from intelligence.prompts._context import JSON_ONLY_INSTRUCTION, render_context
from intelligence.prompts.base_prompt_template import BasePromptTemplate, PromptContext

__all__ = ["SlugGeneratorPrompt"]


class SlugGeneratorPrompt(BasePromptTemplate):
    capability = "slug_generator"
    version = "1.0.0"

    def build(self, context: PromptContext) -> AICompletionRequest:
        system = (
            "You propose short, readable, URL-safe slugs (lowercase, hyphenated, "
            "no stop words, <=60 chars) that include the focus keyphrase. "
            + JSON_ONLY_INSTRUCTION
        )
        prompt = (
            "Propose an SEO-friendly slug for this page.\n\n"
            f"{render_context(context, include_content=False)}\n\n"
            "Return: slug (lowercase-hyphenated), reasoning."
        )
        return self._request(
            prompt=prompt, system_prompt=system, context=context, max_tokens=200
        )

    def response_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["slug"],
            "properties": {
                "slug": {"type": "string"},
                "reasoning": {"type": "string"},
            },
        }
