"""Opportunity justification prompt (engine capability ``opportunity_justification``)."""

from __future__ import annotations

from typing import Any

from intelligence.ai.provider_interface import AICompletionRequest
from intelligence.prompts._context import JSON_ONLY_INSTRUCTION, render_context
from intelligence.prompts.base_prompt_template import BasePromptTemplate, PromptContext

__all__ = ["OpportunityJustificationPrompt"]


class OpportunityJustificationPrompt(BasePromptTemplate):
    capability = "opportunity_justification"
    version = "1.0.0"

    def build(self, context: PromptContext) -> AICompletionRequest:
        system = (
            "You explain in plain language why a specific SEO opportunity is "
            "prioritized and what the expected business benefit is. "
            "The priority score itself is computed deterministically; your job "
            "is to produce the human-readable narrative justification only. "
            + JSON_ONLY_INSTRUCTION
        )
        opportunity = context.extra.get("opportunity", {})
        prompt = (
            "Justify the prioritization of this SEO opportunity.\n\n"
            f"{render_context(context, include_content=False)}\n"
            f"Opportunity: {opportunity}\n\n"
            "Return: justification (1-2 sentences), expected_benefit, confidence (0-1)."
        )
        return self._request(prompt=prompt, system_prompt=system, context=context, max_tokens=300)

    def response_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["justification"],
            "properties": {
                "justification": {"type": "string"},
                "expected_benefit": {"type": "string"},
                "confidence": {"type": "number"},
            },
        }
