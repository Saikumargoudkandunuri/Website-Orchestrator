"""FAQ generator prompt (§6, capability ``faq_generator``).

Factual capability: answers must be traceable to crawled content — the
hallucination guard enforces this before persistence.
"""

from __future__ import annotations

from typing import Any

from intelligence.ai.provider_interface import AICompletionRequest
from intelligence.prompts._context import JSON_ONLY_INSTRUCTION, render_context
from intelligence.prompts.base_prompt_template import BasePromptTemplate, PromptContext

__all__ = ["FaqGeneratorPrompt"]


class FaqGeneratorPrompt(BasePromptTemplate):
    capability = "faq_generator"
    version = "1.0.0"

    def build(self, context: PromptContext) -> AICompletionRequest:
        system = (
            "You write FAQ entries whose answers are fully supported by the page "
            "content. Do not introduce claims not present in the page. "
            + JSON_ONLY_INSTRUCTION
        )
        prompt = (
            "Write FAQs for this page.\n\n"
            f"{render_context(context)}\n\n"
            "Return: faqs [{question, answer}]."
        )
        return self._request(
            prompt=prompt, system_prompt=system, context=context, max_tokens=900
        )

    def response_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["faqs"],
            "properties": {
                "faqs": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["question", "answer"],
                        "properties": {
                            "question": {"type": "string"},
                            "answer": {"type": "string"},
                        },
                    },
                }
            },
        }
