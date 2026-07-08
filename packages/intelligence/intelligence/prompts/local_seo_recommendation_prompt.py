"""Local SEO recommendation prompt (§4.3, capability ``local_seo_recommendation``)."""

from __future__ import annotations

from typing import Any

from intelligence.ai.provider_interface import AICompletionRequest
from intelligence.prompts._context import JSON_ONLY_INSTRUCTION, render_context
from intelligence.prompts.base_prompt_template import BasePromptTemplate, PromptContext

__all__ = ["LocalSeoRecommendationPrompt"]


class LocalSeoRecommendationPrompt(BasePromptTemplate):
    """Local SEO optimization recommendations (§4.3)."""
    
    capability = "local_seo_recommendation"
    version = "1.0.0"

    def build(self, context: PromptContext) -> AICompletionRequest:
        nap_issues = context.extra.get("nap_issues", [])
        gbp_data = context.extra.get("gbp_data", {})
        
        system = (
            "You provide actionable local SEO recommendations. "
            "Focus on NAP consistency, Google Business Profile optimization, "
            "local schema markup, and location page content. " +
            JSON_ONLY_INSTRUCTION
        )
        
        prompt = (
            "Generate local SEO recommendations for this location.\n\n"
            f"{render_context(context)}\n\n"
            f"NAP Issues: {nap_issues}\n"
            f"GBP Data: {gbp_data}\n\n"
            "Return: recommendations (list of {category, priority, action}), reasoning."
        )
        
        return self._request(
            prompt=prompt,
            system_prompt=system,
            context=context,
            max_tokens=800,
            temperature=0.3,
        )

    def response_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["recommendations"],
            "properties": {
                "recommendations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["category", "priority", "action"],
                        "properties": {
                            "category": {"type": "string"},
                            "priority": {"type": "string", "enum": ["high", "medium", "low"]},
                            "action": {"type": "string"},
                        },
                    },
                },
                "reasoning": {"type": "string"},
            },
        }
