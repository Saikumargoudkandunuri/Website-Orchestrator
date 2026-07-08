"""Keyword gap reasoning prompt (engine capability ``keyword_gap_reasoning``)."""

from __future__ import annotations

from typing import Any

from intelligence.ai.provider_interface import AICompletionRequest
from intelligence.prompts._context import JSON_ONLY_INSTRUCTION, render_context
from intelligence.prompts.base_prompt_template import BasePromptTemplate, PromptContext

__all__ = ["KeywordGapReasoningPrompt"]


class KeywordGapReasoningPrompt(BasePromptTemplate):
    capability = "keyword_gap_reasoning"
    version = "1.0.0"

    def build(self, context: PromptContext) -> AICompletionRequest:
        system = (
            "You are a keyword research specialist. Identify the most valuable "
            "keyword gaps for a site based on its current keyphrase coverage "
            "and topic focus. Base your analysis only on provided context. "
            + JSON_ONLY_INSTRUCTION
        )
        covered = context.top_keywords[:20]
        covered_text = ", ".join(covered) if covered else "(none)"
        prompt = (
            "Identify keyword gaps and opportunities for this site.\n\n"
            f"{render_context(context)}\n"
            f"Currently covered keywords: {covered_text}\n\n"
            "Return: keyword_gaps [{keyword, rationale, estimated_opportunity (high|medium|low)}], "
            "topic_gaps[], long_tail_suggestions[]."
        )
        return self._request(prompt=prompt, system_prompt=system, context=context, max_tokens=600)

    def response_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "keyword_gaps": {"type": "array"},
                "topic_gaps": {"type": "array", "items": {"type": "string"}},
                "long_tail_suggestions": {"type": "array", "items": {"type": "string"}},
            },
        }
