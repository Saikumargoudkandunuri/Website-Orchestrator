"""Recommendation synthesis prompt (engine capability ``recommendation_synthesis``)."""

from __future__ import annotations

from typing import Any

from intelligence.ai.provider_interface import AICompletionRequest
from intelligence.prompts._context import JSON_ONLY_INSTRUCTION, render_context
from intelligence.prompts.base_prompt_template import BasePromptTemplate, PromptContext

__all__ = ["RecommendationSynthesisPrompt"]


class RecommendationSynthesisPrompt(BasePromptTemplate):
    capability = "recommendation_synthesis"
    version = "1.0.0"

    def build(self, context: PromptContext) -> AICompletionRequest:
        system = (
            "You synthesize SEO findings into a clear, prioritized action plan "
            "a site owner can act on immediately. Be direct and specific. "
            "Do not invent new findings — only synthesize the provided ones. "
            + JSON_ONLY_INSTRUCTION
        )
        findings_summary = context.extra.get("findings_summary", [])
        findings_text = "\n".join(f"- {f}" for f in findings_summary[:15]) or "(none)"
        prompt = (
            "Synthesize these SEO findings into the top 3-5 recommendations.\n\n"
            f"{render_context(context, include_content=False)}\n"
            f"Findings:\n{findings_text}\n\n"
            "Return: recommendations [{problem_summary, recommended_action, "
            "estimated_benefit, difficulty(easy|moderate|hard), confidence (0-1)}]."
        )
        return self._request(prompt=prompt, system_prompt=system, context=context, max_tokens=900)

    def response_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["recommendations"],
            "properties": {
                "recommendations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["problem_summary", "recommended_action"],
                        "properties": {
                            "problem_summary": {"type": "string"},
                            "recommended_action": {"type": "string"},
                            "estimated_benefit": {"type": "string"},
                            "difficulty": {"type": "string"},
                            "confidence": {"type": "number"},
                        },
                    },
                }
            },
        }
