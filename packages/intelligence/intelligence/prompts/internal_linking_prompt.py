"""Internal + external linking prompt (§6, capability ``internal_linking``).

Also produces external authoritative-citation suggestions (§13.2); external URLs
are validated/downgraded by ``external_link_validator`` before persistence.
"""

from __future__ import annotations

from typing import Any

from intelligence.ai.provider_interface import AICompletionRequest
from intelligence.prompts._context import JSON_ONLY_INSTRUCTION, render_context
from intelligence.prompts.base_prompt_template import BasePromptTemplate, PromptContext

__all__ = ["InternalLinkingPrompt"]


class InternalLinkingPrompt(BasePromptTemplate):
    capability = "internal_linking"
    version = "1.0.0"

    def build(self, context: PromptContext) -> AICompletionRequest:
        system = (
            "You suggest relevant internal links (only to the site's known URLs) "
            "and authoritative external citations. Prefer describing an external "
            "source over inventing a URL. " + JSON_ONLY_INSTRUCTION
        )
        known = "\n".join(f"- {u}" for u in context.known_internal_urls[:50]) or "(none)"
        prompt = (
            "Suggest internal and external links for this page.\n\n"
            f"{render_context(context)}\n"
            f"Known internal URLs:\n{known}\n\n"
            "Return: suggested_internal_links [{target_url, suggested_anchor_text, "
            "reasoning, confidence}], suggested_external_links "
            "[{anchor_text_context, suggested_target_url, "
            "suggested_target_description, reasoning, authority_rationale, "
            "confidence}]."
        )
        return self._request(prompt=prompt, system_prompt=system, context=context)

    def response_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "suggested_internal_links": {"type": "array"},
                "suggested_external_links": {"type": "array"},
            },
        }
