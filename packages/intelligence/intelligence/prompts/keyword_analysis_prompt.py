"""Keyword analysis prompt (§6, capability ``keyword_analysis``)."""

from __future__ import annotations

from typing import Any

from intelligence.ai.provider_interface import AICompletionRequest
from intelligence.prompts._context import JSON_ONLY_INSTRUCTION, render_context
from intelligence.prompts.base_prompt_template import BasePromptTemplate, PromptContext

__all__ = ["KeywordAnalysisPrompt"]


class KeywordAnalysisPrompt(BasePromptTemplate):
    capability = "keyword_analysis"
    version = "1.0.0"

    def build(self, context: PromptContext) -> AICompletionRequest:
        system = (
            "You are a senior technical SEO analyst. Infer the search-intent and "
            "keyword targeting of a web page from its extracted content. Base your "
            "answer only on the provided context. " + JSON_ONLY_INSTRUCTION
        )
        prompt = (
            "Analyze the page's keyword targeting.\n\n"
            f"{render_context(context)}\n\n"
            "Return: primary_focus_keyphrase (single best phrase), "
            "secondary_keyphrases (4-10), related_semantic_keywords, "
            "search_intent (informational|navigational|transactional|"
            "commercial_investigation), named_entities [{text,type,confidence}], "
            "keyword_variations, missing_important_keywords."
        )
        return self._request(prompt=prompt, system_prompt=system, context=context)

    def response_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["primary_focus_keyphrase", "secondary_keyphrases"],
            "properties": {
                "primary_focus_keyphrase": {"type": "string"},
                "secondary_keyphrases": {"type": "array", "items": {"type": "string"}},
                "related_semantic_keywords": {"type": "array", "items": {"type": "string"}},
                "search_intent": {"type": "string"},
                "named_entities": {"type": "array"},
                "keyword_variations": {"type": "array", "items": {"type": "string"}},
                "missing_important_keywords": {"type": "array", "items": {"type": "string"}},
            },
        }
