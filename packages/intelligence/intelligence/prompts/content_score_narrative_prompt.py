"""Content score narrative prompt (engine capability ``content_score_narrative``)."""

from __future__ import annotations

from typing import Any

from intelligence.ai.provider_interface import AICompletionRequest
from intelligence.prompts._context import JSON_ONLY_INSTRUCTION, render_context
from intelligence.prompts.base_prompt_template import BasePromptTemplate, PromptContext

__all__ = ["ContentScoreNarrativePrompt"]


class ContentScoreNarrativePrompt(BasePromptTemplate):
    capability = "content_score_narrative"
    version = "1.0.0"

    def build(self, context: PromptContext) -> AICompletionRequest:
        system = (
            "You provide a holistic, AI-reasoned content quality assessment. "
            "This is distinct from a deterministic formula score — you reason "
            "about depth, relevance, and user value. "
            + JSON_ONLY_INSTRUCTION
        )
        score_data = context.extra.get("deterministic_score", {})
        prompt = (
            "Assess the holistic content quality of this page.\n\n"
            f"{render_context(context)}\n"
            f"Deterministic content score data: {score_data}\n\n"
            "Return: ai_content_score (0-100), reasoning, strengths[], weaknesses[]."
        )
        return self._request(prompt=prompt, system_prompt=system, context=context)

    def response_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["ai_content_score"],
            "properties": {
                "ai_content_score": {"type": "number"},
                "reasoning": {"type": "string"},
                "strengths": {"type": "array", "items": {"type": "string"}},
                "weaknesses": {"type": "array", "items": {"type": "string"}},
            },
        }
