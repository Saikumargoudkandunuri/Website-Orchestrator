"""Orchestrator integration tests (§9) + multi-provider equivalence (§11.4)."""

from __future__ import annotations

import httpx

from intelligence.ai.providers.fake_provider import DEFAULT_FAKE_RESPONSES, FakeProvider
from intelligence.ai.providers.openai_provider import OpenAIProvider
from intelligence.api.wiring import build_intelligence_container
from intelligence.models.ai_invocation import ValidationOutcome
from intelligence.repositories import (
    AIInvocationRepository,
    KnowledgeObjectRepository,
    PageSnapshotRepository,
)
from intelligence.services.analysis_orchestrator import AnalysisOrchestrator

TENANT = "tenant-test"  # matches the conftest container/page_id fixtures

_NINE_SECTIONS = (
    "identity", "keyword_intelligence", "metadata", "content_intelligence",
    "internal_seo", "image_intelligence", "schema_intelligence", "technical_seo",
    "eeat",
)

# Distinctive prompt phrases -> capability, for the OpenAI mock handler.
_PHRASES = [
    ("keyword targeting", "keyword_analysis"),
    ("content quality and coverage", "content_analysis"),
    ("Write one meta description", "meta_generator"),
    ("Write one SEO title", "title_generator"),
    ("SEO-friendly slug", "slug_generator"),
    ("schema.org markup", "schema_generator"),
    ("alt text for each image", "image_alt"),
    ("internal and external links", "internal_linking"),
    ("holistic SEO summary", "seo_audit"),
]


def _orchestrator(session_factory, provider) -> AnalysisOrchestrator:
    return AnalysisOrchestrator(
        knowledge_repo=KnowledgeObjectRepository(session_factory, tenant_id=TENANT),
        invocation_repo=AIInvocationRepository(session_factory, tenant_id=TENANT),
        snapshot_repo=PageSnapshotRepository(session_factory, tenant_id=TENANT),
        provider=provider,
        tenant_id=TENANT,
    )


def _openai_over_mock() -> OpenAIProvider:
    def handler(request: httpx.Request) -> httpx.Response:
        import json

        body = json.loads(request.content.decode())
        user = body["messages"][-1]["content"]
        capability = next((cap for phrase, cap in _PHRASES if phrase in user), None)
        content = DEFAULT_FAKE_RESPONSES.get(capability, "{}")
        return httpx.Response(200, json={
            "model": "gpt-4o-mini",
            "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
        })

    return OpenAIProvider("k", client=httpx.Client(transport=httpx.MockTransport(handler)))


# --- Full integration ---------------------------------------------------------


def test_full_run_produces_complete_versioned_knowledge_object(session_factory, sample_page):
    orch = _orchestrator(session_factory, FakeProvider())
    ko = orch.run(sample_page, crawl_id="c1")

    assert ko.version == 1
    for section in _NINE_SECTIONS:
        assert getattr(ko, section) is not None
    # Observed (deterministic) ground truth is present.
    assert ko.keyword_intelligence.keyword_density  # computed from text
    assert ko.content_intelligence.word_count > 0
    assert ko.content_intelligence.h1_analysis.count == 1
    # Inferred / proposed (AI) present.
    assert ko.keyword_intelligence.primary_focus_keyphrase
    assert ko.metadata.meta_description.proposed_value
    assert ko.ai_summary.page_purpose
    # Deterministic content score with transparent factors (§13.2).
    assert ko.content_intelligence.content_score.breakdown


def test_version_increments(session_factory, sample_page):
    orch = _orchestrator(session_factory, FakeProvider())
    assert orch.run(sample_page).version == 1
    assert orch.run(sample_page).version == 2


def test_every_ai_call_recorded_as_invocation(session_factory, sample_page):
    orch = _orchestrator(session_factory, FakeProvider())
    ko = orch.run(sample_page)
    repo = AIInvocationRepository(session_factory, tenant_id=TENANT)
    invs = repo.list_for_page(TENANT, ko.page_id)
    assert len(invs) >= 8
    assert all(i.raw_response for i in invs)  # raw retained
    assert {"keyword_analysis", "meta_generator", "seo_audit"} <= {i.capability for i in invs}


def test_provider_none_still_produces_deterministic_sections(session_factory, sample_page):
    orch = _orchestrator(session_factory, provider=None)
    ko = orch.run(sample_page)
    # Deterministic sections populated; AI-only fields stay empty (graceful).
    assert ko.content_intelligence.word_count > 0
    assert ko.technical_seo.broken is False
    assert ko.keyword_intelligence.primary_focus_keyphrase is None


def test_subset_capabilities(session_factory, sample_page):
    orch = _orchestrator(session_factory, FakeProvider())
    ko = orch.run(sample_page, capabilities=["technical_seo", "content_intelligence"])
    assert ko.content_intelligence.word_count > 0
    # keyword AI section not requested -> focus keyphrase not generated
    assert ko.keyword_intelligence.primary_focus_keyphrase is None


# --- Retry + graceful degradation ---------------------------------------------


def test_retry_then_success_recorded(session_factory, sample_page):
    # keyword_analysis: attempt 1 malformed, attempt 2 valid.
    provider = FakeProvider(responses={
        "keyword_analysis": ["not json", DEFAULT_FAKE_RESPONSES["keyword_analysis"]],
    })
    orch = _orchestrator(session_factory, provider)
    ko = orch.run(sample_page)
    assert ko.keyword_intelligence.primary_focus_keyphrase  # corrected on retry
    invs = AIInvocationRepository(session_factory, tenant_id=TENANT).list_for_page(TENANT, ko.page_id)
    kw = [i for i in invs if i.capability == "keyword_analysis"]
    assert any(i.validation_result == ValidationOutcome.FAILED for i in kw)
    assert any(i.validation_result == ValidationOutcome.PASSED for i in kw)


def test_persistent_validation_failure_degrades_to_null(session_factory, sample_page):
    provider = FakeProvider(responses={"keyword_analysis": "not json ever"})
    orch = _orchestrator(session_factory, provider)
    ko = orch.run(sample_page)  # must not crash
    assert ko.keyword_intelligence.primary_focus_keyphrase is None  # left null, not invalid


def test_provider_failure_does_not_crash(session_factory, sample_page):
    orch = _orchestrator(session_factory, FakeProvider(fail=True))
    ko = orch.run(sample_page)  # graceful
    assert ko.version == 1
    assert ko.content_intelligence.word_count > 0  # deterministic still works


# --- Multi-provider structural equivalence (acceptance #4) --------------------


def test_two_providers_produce_structurally_valid_output(session_factory, sample_page):
    orch_fake = _orchestrator(session_factory, FakeProvider())
    ko_fake = orch_fake.run(sample_page)

    # Fresh store for the second provider (a real adapter over mocked HTTP).
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from intelligence.repositories import create_intelligence_tables

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    create_intelligence_tables(engine)
    sf2 = sessionmaker(bind=engine, expire_on_commit=False)
    orch_openai = _orchestrator(sf2, _openai_over_mock())
    ko_openai = orch_openai.run(sample_page)

    # Same structural shape from both configured providers.
    assert ko_fake.model_dump().keys() == ko_openai.model_dump().keys()
    assert ko_openai.keyword_intelligence.primary_focus_keyphrase
    assert ko_openai.metadata.meta_description.proposed_value
    assert ko_openai.ai_summary.page_purpose
