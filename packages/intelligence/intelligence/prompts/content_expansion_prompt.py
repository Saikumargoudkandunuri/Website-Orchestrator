"""Content expansion prompt (§6, capability ``content_expansion``).

Output is rendered/publishable, so it must pass the HTML sanitizer before use.
"""

from __future__ import annotations

from typing import Any

from intelligence.ai.provider_interface import AICompletionRequest
from intelligence.prompts._context import JSON_ONLY_INSTRUCTION, render_context
from intelligence.prompts.base_prompt_template import BasePromptTemplate, PromptContext

__all__ = ["ContentExpansionPrompt"]


class ContentExpansionPrompt(BasePromptTemplate):
    capability = "content_expansion"
    version = "1.0.0"

    def build(self, context: PromptContext) -> AICompletionRequest:
        system = (
            "You expand thin content with accurate, on-topic detail that covers "
            "identified gaps, without inventing facts or adding unsafe markup. "
            + JSON_ONLY_INSTRUCTION
        )
        gaps = ", ".join(context.extra.get("missing_topics", [])) or "(unspecified)"
        prompt = (
            "Propose additional content for this page.\n\n"
            f"{render_context(context)}\n"
            f"Gaps to address: {gaps}\n\n"
            "Return: expansion."
        )
        return self._request(
            prompt=prompt, system_prompt=system, context=context, max_tokens=900
        )

    def response_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["expansion"],
            "properties": {"expansion": {"type": "string"}},
        }
