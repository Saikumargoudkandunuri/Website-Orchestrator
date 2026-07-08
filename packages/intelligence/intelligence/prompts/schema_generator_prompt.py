"""Schema.org JSON-LD generator prompt (§6, capability ``schema_generator``)."""

from __future__ import annotations

from typing import Any

from intelligence.ai.provider_interface import AICompletionRequest
from intelligence.prompts._context import JSON_ONLY_INSTRUCTION, render_context
from intelligence.prompts.base_prompt_template import BasePromptTemplate, PromptContext

__all__ = ["SchemaGeneratorPrompt"]


class SchemaGeneratorPrompt(BasePromptTemplate):
    capability = "schema_generator"
    version = "1.0.0"

    def build(self, context: PromptContext) -> AICompletionRequest:
        system = (
            "You generate valid schema.org JSON-LD appropriate to the page type, "
            "using only facts present in the page. " + JSON_ONLY_INSTRUCTION
        )
        existing = ", ".join(context.existing_schema_types) or "none"
        prompt = (
            "Generate the most valuable missing schema.org markup for this page.\n\n"
            f"{render_context(context)}\n"
            f"Existing schema types: {existing}\n\n"
            "Return: type (schema.org @type), jsonld (a JSON-LD document as a "
            "STRING), reasoning."
        )
        return self._request(prompt=prompt, system_prompt=system, context=context)

    def response_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["type", "jsonld"],
            "properties": {
                "type": {"type": "string"},
                "jsonld": {"type": "string"},
                "reasoning": {"type": "string"},
            },
        }
