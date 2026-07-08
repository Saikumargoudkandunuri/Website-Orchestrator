"""Image alt-text generator prompt (§6, capability ``image_alt``)."""

from __future__ import annotations

from typing import Any

from intelligence.ai.provider_interface import AICompletionRequest
from intelligence.prompts._context import JSON_ONLY_INSTRUCTION, render_context
from intelligence.prompts.base_prompt_template import BasePromptTemplate, PromptContext

__all__ = ["ImageAltPrompt"]


class ImageAltPrompt(BasePromptTemplate):
    capability = "image_alt"
    version = "1.0.0"

    def build(self, context: PromptContext) -> AICompletionRequest:
        system = (
            "You write concise, descriptive, accessibility-first alt text (<=125 "
            "chars). Never start with 'image of'/'picture of'. "
            + JSON_ONLY_INSTRUCTION
        )
        images = "\n".join(
            f"- element_id={img.get('element_id','')} filename={img.get('filename','')}"
            for img in context.images
        ) or "(none)"
        prompt = (
            "Write alt text for each image missing it.\n\n"
            f"{render_context(context, include_content=False)}\n"
            f"Images:\n{images}\n\n"
            "Return: alt_texts [{element_id, alt_text}]."
        )
        return self._request(prompt=prompt, system_prompt=system, context=context)

    def response_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["alt_texts"],
            "properties": {
                "alt_texts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["alt_text"],
                        "properties": {
                            "element_id": {"type": "string"},
                            "alt_text": {"type": "string"},
                        },
                    },
                }
            },
        }
