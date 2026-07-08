"""Technical SEO explanation prompt (engine capability ``technical_seo_explanation``)."""

from __future__ import annotations

from typing import Any

from intelligence.ai.provider_interface import AICompletionRequest
from intelligence.prompts._context import JSON_ONLY_INSTRUCTION, render_context
from intelligence.prompts.base_prompt_template import BasePromptTemplate, PromptContext

__all__ = ["TechnicalSeoExplanationPrompt"]


class TechnicalSeoExplanationPrompt(BasePromptTemplate):
    capability = "technical_seo_explanation"
    version = "1.0.0"

    def build(self, context: PromptContext) -> AICompletionRequest:
        system = (
            "You explain technical SEO findings in plain language for site owners "
            "who are not technical SEO experts. Be concise and actionable. "
            + JSON_ONLY_INSTRUCTION
        )
        findings = context.extra.get("findings", [])
        findings_text = "\n".join(f"- {f}" for f in findings[:10]) if findings else "(none provided)"
        prompt = (
            f"Explain the following technical SEO findings for this page.\n\n"
            f"{render_context(context, include_content=False)}\n\n"
            f"Findings:\n{findings_text}\n\n"
            "Return: explanations [{check_name, plain_language_explanation, recommended_action}], "
            "overall_severity (critical|high|medium|low), summary."
        )
        return self._request(prompt=prompt, system_prompt=system, context=context, max_tokens=800)

    def response_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "explanations": {"type": "array"},
                "overall_severity": {"type": "string"},
                "summary": {"type": "string"},
            },
        }
