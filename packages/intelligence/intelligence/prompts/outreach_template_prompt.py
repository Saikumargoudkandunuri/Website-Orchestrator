"""Outreach template generation prompt (§4.9, capability ``outreach_template``)."""

from __future__ import annotations

from typing import Any

from intelligence.ai.provider_interface import AICompletionRequest
from intelligence.prompts._context import JSON_ONLY_INSTRUCTION
from intelligence.prompts.base_prompt_template import BasePromptTemplate, PromptContext

__all__ = ["OutreachTemplatePrompt"]


class OutreachTemplatePrompt(BasePromptTemplate):
    """AI-assisted outreach email template drafting (§4.9)."""
    
    capability = "outreach_template"
    version = "1.0.0"

    def build(self, context: PromptContext) -> AICompletionRequest:
        campaign_type = context.extra.get("campaign_type", "guest_post")
        prospect_domain = context.extra.get("prospect_domain", "")
        brand_voice = context.extra.get("brand_voice", "")
        
        system = (
            "You draft professional, personalized outreach emails for link building campaigns. "
            "Be concise, respectful, and value-focused. Never use generic templates. "
            "Maintain brand voice while being authentic. " +
            JSON_ONLY_INSTRUCTION
        )
        
        prompt_parts = [
            f"Draft an outreach email for a {campaign_type} campaign.\n"
        ]
        
        if brand_voice:
            prompt_parts.append(f"Brand voice: {brand_voice}\n")
        
        prompt_parts.extend([
            f"\nProspect domain: {prospect_domain}\n",
            f"Your site: {context.page_url}\n\n",
            "Return: subject_line, body, personalization_placeholders (list of {placeholder, description})."
        ])
        
        prompt = "\n".join(prompt_parts)
        
        return self._request(
            prompt=prompt,
            system_prompt=system,
            context=context,
            max_tokens=400,
            temperature=0.7,
        )

    def response_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["subject_line", "body"],
            "properties": {
                "subject_line": {"type": "string"},
                "body": {"type": "string"},
                "personalization_placeholders": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["placeholder", "description"],
                        "properties": {
                            "placeholder": {"type": "string"},
                            "description": {"type": "string"},
                        },
                    },
                },
            },
        }
