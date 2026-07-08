"""Deterministic, network-free AI provider test double (§5.2, §9).

``FakeProvider`` returns canned, per-capability responses with zero network
calls, so every service/prompt/orchestrator test runs against it exclusively.
It is configurable enough to drive the important test scenarios:

* per-capability constant responses, or a *sequence* of responses (for retry
  tests where attempt 1 is malformed and attempt 2 is corrected);
* a forced-failure mode returning a typed :class:`~core.results.Err`;
* a call recorder so tests can assert what was asked of the provider.

Capability is read from ``request.metadata["capability"]``.
"""

from __future__ import annotations

from typing import Sequence

from core.results import Err, Ok, Result
from intelligence.ai.provider_interface import (
    AICompletionRequest,
    AICompletionResponse,
)
from intelligence.errors import AIProviderError
from intelligence.models.ai_invocation import TokenUsage

__all__ = ["FakeProvider", "DEFAULT_FAKE_RESPONSES"]


#: Built-in canned JSON responses per capability, structurally valid against the
#: prompt response schemas. Services and the orchestrator integration tests rely
#: on these to produce a fully-populated KnowledgeObject with zero network.
DEFAULT_FAKE_RESPONSES: dict[str, str] = {
    "keyword_analysis": (
        '{"primary_focus_keyphrase": "modular kitchens hyderabad", '
        '"secondary_keyphrases": ["kitchen design", "modular cabinets", '
        '"kitchen renovation", "interior design"], '
        '"related_semantic_keywords": ["countertops", "cabinetry"], '
        '"search_intent": "commercial_investigation", '
        '"named_entities": [{"text": "Hyderabad", "type": "place", "confidence": 0.9}], '
        '"keyword_variations": ["modular kitchen"], '
        '"missing_important_keywords": ["kitchen cost"]}'
    ),
    "content_analysis": (
        '{"thin_content": false, "missing_topics": ["installation process"], '
        '"topic_coverage_score": 0.72, "semantic_completeness_score": 0.68}'
    ),
    "meta_generator": (
        '{"meta_description": "Custom modular kitchens in Hyderabad, designed '
        'and installed by expert designers for modern homes.", '
        '"reasoning": "Includes focus keyphrase and a clear value proposition."}'
    ),
    "title_generator": (
        '{"seo_title": "Modular Kitchens in Hyderabad | Custom Design & Install", '
        '"reasoning": "Front-loads the focus keyphrase within length limits."}'
    ),
    "slug_generator": (
        '{"slug": "modular-kitchens-hyderabad", '
        '"reasoning": "Short, readable, keyphrase-bearing slug."}'
    ),
    "schema_generator": (
        '{"jsonld": "{\\"@context\\": \\"https://schema.org\\", '
        '\\"@type\\": \\"LocalBusiness\\", \\"name\\": \\"Kitchen Co\\"}", '
        '"type": "LocalBusiness", "reasoning": "Local business page."}'
    ),
    "image_alt": (
        '{"alt_texts": [{"element_id": "", "alt_text": "A modern modular kitchen"}]}'
    ),
    "internal_linking": (
        '{"suggested_internal_links": [{"target_url": "/about", '
        '"suggested_anchor_text": "our design team", '
        '"reasoning": "Relevant supporting page", "confidence": 0.7}], '
        '"suggested_external_links": [{"anchor_text_context": "industry standards", '
        '"suggested_target_url": "https://www.example.org/standards", '
        '"suggested_target_description": "Authoritative standards body", '
        '"reasoning": "Adds authority", "authority_rationale": "Recognized body", '
        '"confidence": 0.6}]}'
    ),
    "seo_audit": (
        '{"page_purpose": "Sell modular kitchen design services in Hyderabad", '
        '"target_audience": "Homeowners in Hyderabad renovating kitchens", '
        '"business_goal": "Generate qualified design consultation leads", '
        '"user_expectations": "See designs, pricing guidance, and how to book", '
        '"search_engine_expectations": "Local commercial-investigation intent", '
        '"key_gaps": ["No FAQ", "No pricing guidance"], '
        '"improvement_priorities": [{"title": "Add FAQ section", '
        '"rationale": "Captures long-tail queries", "priority": 1, '
        '"capability": "faq_generator"}], '
        '"do_not_change": ["The client testimonial wording"], '
        '"seo_recommendations": [{"factor": "meta_description_length", '
        '"status": "warning", "recommendation_text": "Meta description missing", '
        '"priority": "high", "related_fix_type": "update_meta_description"}]}'
    ),
    "technical_audit": (
        '{"canonical_issues": [], "notes": ["No technical blockers detected"]}'
    ),
    "accessibility": (
        '{"issues": ["Image missing alt text"], '
        '"recommendations": ["Add descriptive alt text to all images"]}'
    ),
    "faq_generator": (
        '{"faqs": [{"question": "Do you install in Hyderabad?", '
        '"answer": "Yes, we design and install modular kitchens across Hyderabad."}]}'
    ),
    "content_rewrite": (
        '{"rewritten": "Custom modular kitchens designed and installed for '
        'Hyderabad homes."}'
    ),
    "content_expansion": (
        '{"expansion": "Our process covers measurement, 3D design, manufacturing, '
        'and professional installation."}'
    ),
}


class FakeProvider:
    """A deterministic :class:`~intelligence.ai.provider_interface.AIProvider`."""

    def __init__(
        self,
        responses: dict[str, str | Sequence[str]] | None = None,
        *,
        name: str = "fake",
        model: str = "fake-model-1",
        fail: bool = False,
        supports_json: bool = True,
    ) -> None:
        self._responses = responses or {}
        self._name = name
        self._model = model
        self._fail = fail
        self._supports_json = supports_json
        #: Recorded requests, in call order, for test assertions.
        self.calls: list[AICompletionRequest] = []
        self._cursors: dict[str, int] = {}

    def complete(
        self, request: AICompletionRequest
    ) -> Result[AICompletionResponse, AIProviderError]:
        self.calls.append(request)
        if self._fail:
            return Err(AIProviderError("fake provider forced failure"))

        capability = str(request.metadata.get("capability", ""))
        raw = self._resolve(capability)
        return Ok(
            AICompletionResponse(
                raw_text=raw,
                tokens_used=TokenUsage(
                    prompt_tokens=10, completion_tokens=20, total_tokens=30
                ),
                model=self._model,
                finish_reason="stop",
            )
        )

    def _resolve(self, capability: str) -> str:
        configured = self._responses.get(capability)
        if configured is None:
            return DEFAULT_FAKE_RESPONSES.get(capability, "{}")
        if isinstance(configured, str):
            return configured
        # A sequence: return successive entries, repeating the last one.
        seq = list(configured)
        if not seq:
            return "{}"
        idx = self._cursors.get(capability, 0)
        self._cursors[capability] = min(idx + 1, len(seq) - 1)
        return seq[idx]

    def name(self) -> str:
        return self._name

    def supports_json_mode(self) -> bool:
        return self._supports_json
