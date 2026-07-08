"""Content optimization snippet opportunity prompt (§4.2, capability ``content_optimization_snippet``)."""

from __future__ import annotations

from typing import Any

from intelligence.ai.provider_interface import AICompletionRequest
from intelligence.prompts._context import JSON_ONLY_INSTRUCTION, render_context
from intelligence.prompts.base_prompt_template import BasePromptTemplate, PromptContext

__all__ = ["ContentOptimizationSnippetPrompt"]


class ContentOptimizationSnippetPrompt(BasePromptTemplate):
    """Featured snippet + PAA opportunity detection (§4.2)."""
    
    capability = "content_optimization_snippet"
    version = "1.0.0"

    def build(self, context: PromptContext) -> AICompletionRequest:
        system = (
            "You identify featured snippet and People Also Ask (PAA) opportunities. "
            "Analyze the page structure and content to determine if it's formatted "
            "for featured snippets and what PAA questions could be addressed. " + 
            JSON_ONLY_INSTRUCTION
        )
        
        prompt = (
            "Analyze this page for featured snippet and PAA opportunities.\n\n"
            f"{render_context(context)}\n\n"
            "Return: has_snippet_format (bool), snippet_recommendations (list), "
            "paa_opportunities (list of {question, is_covered, recommendation})."
        )
        
        return self._request(
            prompt=prompt,
            system_prompt=system,
            context=context,
            max_tokens=1000,
            temperature=0.3,
        )

    def response_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["has_snippet_format", "snippet_recommendations", "paa_opportunities"],
            "properties": {
                "has_snippet_format": {"type": "boolean"},
                "snippet_recommendations": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "paa_opportunities": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["question", "is_covered", "recommendation"],
                        "properties": {
                            "question": {"type": "string"},
                            "is_covered": {"type": "boolean"},
                            "recommendation": {"type": "string"},
                        },
                    },
                },
            },
        }
