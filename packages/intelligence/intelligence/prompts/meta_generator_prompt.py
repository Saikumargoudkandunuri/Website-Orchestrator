"""Meta description generator prompt (§6, capability ``meta_generator``)."""

from __future__ import annotations

from typing import Any

from intelligence.ai.provider_interface import AICompletionRequest
from intelligence.prompts._context import JSON_ONLY_INSTRUCTION, render_context
from intelligence.prompts.base_prompt_template import BasePromptTemplate, PromptContext

__all__ = ["MetaGeneratorPrompt"]


class MetaGeneratorPrompt(BasePromptTemplate):
    capability = "meta_generator"
    version = "1.0.0"

    def build(self, context: PromptContext) -> AICompletionRequest:
        system = (
            "You write compelling, accurate SEO meta descriptions of 150-160 "
            "characters that include the focus keyphrase naturally and never "
            "invent facts not present in the page. " + JSON_ONLY_INSTRUCTION
        )
        prompt = (
            "Write one meta description for this page.\n\n"
            f"{render_context(context)}\n\n"
            "Return: meta_description (<=160 chars), reasoning."
        )
        return self._request(prompt=prompt, system_prompt=system, context=context)

    def response_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["meta_description"],
            "properties": {
                "meta_description": {"type": "string"},
                "reasoning": {"type": "string"},
            },
        }
