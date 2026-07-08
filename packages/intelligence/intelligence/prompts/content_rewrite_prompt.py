"""Content rewrite prompt (§6, capability ``content_rewrite``).

Output is rendered/publishable, so it must pass the HTML sanitizer before use.
"""

from __future__ import annotations

from typing import Any

from intelligence.ai.provider_interface import AICompletionRequest
from intelligence.prompts._context import JSON_ONLY_INSTRUCTION, render_context
from intelligence.prompts.base_prompt_template import BasePromptTemplate, PromptContext

__all__ = ["ContentRewritePrompt"]


class ContentRewritePrompt(BasePromptTemplate):
    capability = "content_rewrite"
    version = "1.0.0"

    def build(self, context: PromptContext) -> AICompletionRequest:
        system = (
            "You rewrite passages for clarity and SEO while preserving meaning "
            "and facts. Do not add scripts or unsafe markup. "
            + JSON_ONLY_INSTRUCTION
        )
        target = context.extra.get("rewrite_target") or context.first_paragraph or ""
        prompt = (
            "Rewrite the following passage for this page.\n\n"
            f"{render_context(context, include_content=False)}\n"
            f"Passage: {target}\n\n"
            "Return: rewritten."
        )
        return self._request(prompt=prompt, system_prompt=system, context=context)

    def response_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["rewritten"],
            "properties": {"rewritten": {"type": "string"}},
        }
