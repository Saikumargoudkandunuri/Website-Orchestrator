"""Accessibility analysis prompt (§6, capability ``accessibility``)."""

from __future__ import annotations

from typing import Any

from intelligence.ai.provider_interface import AICompletionRequest
from intelligence.prompts._context import JSON_ONLY_INSTRUCTION, render_context
from intelligence.prompts.base_prompt_template import BasePromptTemplate, PromptContext

__all__ = ["AccessibilityPrompt"]


class AccessibilityPrompt(BasePromptTemplate):
    capability = "accessibility"
    version = "1.0.0"

    def build(self, context: PromptContext) -> AICompletionRequest:
        system = (
            "You are a web accessibility (WCAG) reviewer. Flag likely issues from "
            "the extracted structure and suggest concrete fixes. Full conformance "
            "requires manual assistive-technology testing. " + JSON_ONLY_INSTRUCTION
        )
        missing_alt = sum(1 for i in context.images if not i.get("alt"))
        prompt = (
            "Review this page for likely accessibility issues.\n\n"
            f"{render_context(context, include_content=False)}\n"
            f"Images missing alt text: {missing_alt}\n\n"
            "Return: issues[], recommendations[]."
        )
        return self._request(prompt=prompt, system_prompt=system, context=context)

    def response_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "issues": {"type": "array", "items": {"type": "string"}},
                "recommendations": {"type": "array", "items": {"type": "string"}},
            },
        }
