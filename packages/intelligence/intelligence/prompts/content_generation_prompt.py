"""Content generation prompt (§4.1, capability ``content_generation``)."""

from __future__ import annotations

from typing import Any

from intelligence.ai.provider_interface import AICompletionRequest
from intelligence.prompts._context import JSON_ONLY_INSTRUCTION, render_context
from intelligence.prompts.base_prompt_template import BasePromptTemplate, PromptContext

__all__ = ["ContentGenerationPrompt"]


class ContentGenerationPrompt(BasePromptTemplate):
    """
    Content generation prompt for full-asset creation (§4.1).
    
    Parameterized per asset_type via context.extra['asset_type'].
    Uses brand_voice from context.extra['brand_voice'] if present.
    """
    
    capability = "content_generation"
    version = "1.0.0"

    def build(self, context: PromptContext) -> AICompletionRequest:
        asset_type = context.extra.get("asset_type", "blog_post")
        brand_voice = context.extra.get("brand_voice", "")
        language = context.language or "en"
        
        system = (
            f"You generate high-quality, SEO-optimized {asset_type} content. "
            "Never invent facts not present in the provided context. "
            "Include the focus keyphrase naturally. "
            "Maintain consistent brand voice. " + JSON_ONLY_INSTRUCTION
        )
        
        prompt_parts = [
            f"Generate a complete {asset_type} for this page.\n"
        ]
        
        if brand_voice:
            prompt_parts.append(f"Brand voice: {brand_voice}\n")
        
        prompt_parts.extend([
            f"Language: {language}\n",
            f"{render_context(context)}\n\n",
            "Return: title, sections (list of {heading, content}), meta_title, meta_description, reasoning."
        ])
        
        prompt = "\n".join(prompt_parts)
        
        return self._request(
            prompt=prompt,
            system_prompt=system,
            context=context,
            max_tokens=2000,
            temperature=0.7,
        )

    def response_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["title", "sections"],
            "properties": {
                "title": {"type": "string"},
                "sections": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["heading", "content"],
                        "properties": {
                            "heading": {"type": "string"},
                            "content": {"type": "string"},
                        },
                    },
                },
                "meta_title": {"type": "string"},
                "meta_description": {"type": "string"},
                "reasoning": {"type": "string"},
            },
        }
