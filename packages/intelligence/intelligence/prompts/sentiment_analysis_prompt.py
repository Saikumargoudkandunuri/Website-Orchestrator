"""Sentiment analysis prompt (§4.4, capability ``sentiment_analysis``)."""

from __future__ import annotations

from typing import Any

from intelligence.ai.provider_interface import AICompletionRequest
from intelligence.prompts._context import JSON_ONLY_INSTRUCTION
from intelligence.prompts.base_prompt_template import BasePromptTemplate, PromptContext

__all__ = ["SentimentAnalysisPrompt"]


class SentimentAnalysisPrompt(BasePromptTemplate):
    """Customer review sentiment analysis (§4.4)."""
    
    capability = "sentiment_analysis"
    version = "1.0.0"

    def build(self, context: PromptContext) -> AICompletionRequest:
        review_text = context.extra.get("review_text", "")
        
        system = (
            "You analyze customer review sentiment. "
            "Classify sentiment as positive, neutral, or negative, "
            "and provide a score from -1.0 (very negative) to 1.0 (very positive). " +
            JSON_ONLY_INSTRUCTION
        )
        
        prompt = (
            f"Analyze the sentiment of this customer review.\n\n"
            f"Review: \"{review_text}\"\n\n"
            "Return: score (float -1.0 to 1.0), label (positive/neutral/negative), reasoning."
        )
        
        return self._request(
            prompt=prompt,
            system_prompt=system,
            context=context,
            max_tokens=150,
            temperature=0.0,  # Deterministic for classification
        )

    def response_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["score", "label"],
            "properties": {
                "score": {"type": "number", "minimum": -1.0, "maximum": 1.0},
                "label": {"type": "string", "enum": ["positive", "neutral", "negative"]},
                "reasoning": {"type": "string"},
            },
        }
