"""Content analysis prompt (§6, capability ``content_analysis``)."""

from __future__ import annotations

from typing import Any

from intelligence.ai.provider_interface import AICompletionRequest
from intelligence.prompts._context import JSON_ONLY_INSTRUCTION, render_context
from intelligence.prompts.base_prompt_template import BasePromptTemplate, PromptContext

__all__ = ["ContentAnalysisPrompt"]


class ContentAnalysisPrompt(BasePromptTemplate):
    capability = "content_analysis"
    version = "1.0.0"

    def build(self, context: PromptContext) -> AICompletionRequest:
        system = (
            "You are a content strategist. Assess topical coverage and gaps of a "
            "page from its extracted content. " + JSON_ONLY_INSTRUCTION
        )
        prompt = (
            "Assess this page's content quality and coverage.\n\n"
            f"{render_context(context)}\n\n"
            "Return: thin_content (bool), missing_topics (topics a strong page on "
            "this subject should cover but this one omits), topic_coverage_score "
            "(0..1), semantic_completeness_score (0..1)."
        )
        return self._request(prompt=prompt, system_prompt=system, context=context)

    def response_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["thin_content"],
            "properties": {
                "thin_content": {"type": "boolean"},
                "missing_topics": {"type": "array", "items": {"type": "string"}},
                "topic_coverage_score": {"type": "number"},
                "semantic_completeness_score": {"type": "number"},
            },
        }
