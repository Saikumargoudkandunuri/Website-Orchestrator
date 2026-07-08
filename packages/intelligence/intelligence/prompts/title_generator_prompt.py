"""SEO title generator prompt (§6, capability ``title_generator``)."""

from __future__ import annotations

from typing import Any

from intelligence.ai.provider_interface import AICompletionRequest
from intelligence.prompts._context import JSON_ONLY_INSTRUCTION, render_context
from intelligence.prompts.base_prompt_template import BasePromptTemplate, PromptContext

__all__ = ["TitleGeneratorPrompt"]


class TitleGeneratorPrompt(BasePromptTemplate):
    capability = "title_generator"
    version = "1.0.0"

    def build(self, context: PromptContext) -> AICompletionRequest:
        system = (
            "You write SEO titles of 50-60 characters that front-load the focus "
            "keyphrase and reflect the page accurately. " + JSON_ONLY_INSTRUCTION
        )
        prompt = (
            "Write one SEO title for this page.\n\n"
            f"{render_context(context)}\n\n"
            "Return: seo_title (<=60 chars), reasoning."
        )
        return self._request(prompt=prompt, system_prompt=system, context=context)

    def response_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["seo_title"],
            "properties": {
                "seo_title": {"type": "string"},
                "reasoning": {"type": "string"},
            },
        }
