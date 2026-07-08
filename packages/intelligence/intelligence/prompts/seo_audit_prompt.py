"""Holistic SEO audit prompt (§6, capability ``seo_audit``).

Produces the AI Intelligence Summary (§4.12) plus the Rank-Math-style per-factor
SEO recommendations checklist (§13.2).
"""

from __future__ import annotations

from typing import Any

from intelligence.ai.provider_interface import AICompletionRequest
from intelligence.prompts._context import JSON_ONLY_INSTRUCTION, render_context
from intelligence.prompts.base_prompt_template import BasePromptTemplate, PromptContext

__all__ = ["SeoAuditPrompt"]


class SeoAuditPrompt(BasePromptTemplate):
    capability = "seo_audit"
    version = "1.0.0"

    def build(self, context: PromptContext) -> AICompletionRequest:
        system = (
            "You are a senior SEO auditor producing a holistic read of a page: "
            "what it is, who it serves, why it exists, its gaps, and what must "
            "never be changed. " + JSON_ONLY_INSTRUCTION
        )
        prompt = (
            "Produce a holistic SEO summary of this page.\n\n"
            f"{render_context(context)}\n\n"
            "Return: page_purpose, target_audience, business_goal, "
            "user_expectations, search_engine_expectations, key_gaps[], "
            "improvement_priorities [{title, rationale, priority, capability}], "
            "do_not_change[] (human-readable reasons), seo_recommendations "
            "[{factor, status(pass|warning|fail), recommendation_text, "
            "priority(critical|high|medium|low), related_fix_type}]."
        )
        return self._request(
            prompt=prompt, system_prompt=system, context=context, max_tokens=1200
        )

    def response_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["page_purpose", "key_gaps"],
            "properties": {
                "page_purpose": {"type": "string"},
                "target_audience": {"type": "string"},
                "business_goal": {"type": "string"},
                "user_expectations": {"type": "string"},
                "search_engine_expectations": {"type": "string"},
                "key_gaps": {"type": "array", "items": {"type": "string"}},
                "improvement_priorities": {"type": "array"},
                "do_not_change": {"type": "array", "items": {"type": "string"}},
                "seo_recommendations": {"type": "array"},
            },
        }
