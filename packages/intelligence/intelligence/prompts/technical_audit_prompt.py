"""Technical SEO audit prompt (§6, capability ``technical_audit``).

Most technical signals are computed deterministically; this capability only
supplies inferential commentary (e.g. canonical-issue interpretation) on top of
the observed facts.
"""

from __future__ import annotations

from typing import Any

from intelligence.ai.provider_interface import AICompletionRequest
from intelligence.prompts._context import JSON_ONLY_INSTRUCTION, render_context
from intelligence.prompts.base_prompt_template import BasePromptTemplate, PromptContext

__all__ = ["TechnicalAuditPrompt"]


class TechnicalAuditPrompt(BasePromptTemplate):
    capability = "technical_audit"
    version = "1.0.0"

    def build(self, context: PromptContext) -> AICompletionRequest:
        system = (
            "You interpret technical SEO signals already measured for a page and "
            "flag likely canonical/indexation issues. " + JSON_ONLY_INSTRUCTION
        )
        prompt = (
            "Interpret the technical signals for this page.\n\n"
            f"{render_context(context, include_content=False)}\n"
            f"Observed signals: {context.extra.get('technical_signals', {})}\n\n"
            "Return: canonical_issues[], notes[]."
        )
        return self._request(
            prompt=prompt, system_prompt=system, context=context, max_tokens=400
        )

    def response_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "canonical_issues": {"type": "array", "items": {"type": "string"}},
                "notes": {"type": "array", "items": {"type": "string"}},
            },
        }
