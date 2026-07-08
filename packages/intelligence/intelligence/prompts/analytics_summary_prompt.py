"""Analytics summary prompt (§4.8, capability ``analytics_summary``)."""

from __future__ import annotations

from typing import Any

from intelligence.ai.provider_interface import AICompletionRequest
from intelligence.prompts._context import JSON_ONLY_INSTRUCTION
from intelligence.prompts.base_prompt_template import BasePromptTemplate, PromptContext

__all__ = ["AnalyticsSummaryPrompt"]


class AnalyticsSummaryPrompt(BasePromptTemplate):
    """AI narrative summary for analytics data (§4.8)."""
    
    capability = "analytics_summary"
    version = "1.0.0"

    def build(self, context: PromptContext) -> AICompletionRequest:
        analytics_data = context.extra.get("analytics_data", {})
        trend_data = context.extra.get("trend_data", {})
        
        system = (
            "You generate clear, actionable analytics summaries for non-technical audiences. "
            "Highlight key trends, wins, and areas needing attention. "
            "Always cite specific numbers from the data. " +
            JSON_ONLY_INSTRUCTION
        )
        
        prompt = (
            "Generate an executive summary of this analytics data.\n\n"
            f"Analytics: {analytics_data}\n"
            f"Trends: {trend_data}\n\n"
            "Return: summary (2-3 paragraphs), key_insights (list), recommendations (list)."
        )
        
        return self._request(
            prompt=prompt,
            system_prompt=system,
            context=context,
            max_tokens=600,
            temperature=0.5,
        )

    def response_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["summary", "key_insights"],
            "properties": {
                "summary": {"type": "string"},
                "key_insights": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "recommendations": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
        }
