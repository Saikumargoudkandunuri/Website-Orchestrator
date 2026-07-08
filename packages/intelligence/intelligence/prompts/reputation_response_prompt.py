"""Reputation response generation prompt (§4.4, capability ``reputation_response``)."""

from __future__ import annotations

from typing import Any

from intelligence.ai.provider_interface import AICompletionRequest
from intelligence.prompts._context import JSON_ONLY_INSTRUCTION
from intelligence.prompts.base_prompt_template import BasePromptTemplate, PromptContext

__all__ = ["ReputationResponsePrompt"]


class ReputationResponsePrompt(BasePromptTemplate):
    """AI-generated response suggestions for negative reviews (§4.4)."""
    
    capability = "reputation_response"
    version = "1.0.0"

    def build(self, context: PromptContext) -> AICompletionRequest:
        review_text = context.extra.get("review_text", "")
        rating = context.extra.get("rating", 1.0)
        brand_voice = context.extra.get("brand_voice", "")
        
        system = (
            "You generate professional, empathetic responses to customer reviews. "
            "Address concerns directly, offer solutions, and maintain brand voice. "
            "Never promise specific outcomes or admit fault without approval. " +
            JSON_ONLY_INSTRUCTION
        )
        
        prompt_parts = [
            "Generate a professional response to this customer review.\n"
        ]
        
        if brand_voice:
            prompt_parts.append(f"Brand voice: {brand_voice}\n")
        
        prompt_parts.extend([
            f"\nReview ({rating:.1f} stars): \"{review_text}\"\n\n",
            "Return: response_text, tone_used, key_points_addressed (list)."
        ])
        
        prompt = "\n".join(prompt_parts)
        
        return self._request(
            prompt=prompt,
            system_prompt=system,
            context=context,
            max_tokens=250,
            temperature=0.7,
        )

    def response_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["response_text", "tone_used"],
            "properties": {
                "response_text": {"type": "string"},
                "tone_used": {"type": "string"},
                "key_points_addressed": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
        }
