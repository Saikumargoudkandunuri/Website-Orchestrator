"""Content score tests (§13.5): deterministic, versioned, transparent."""

from __future__ import annotations

from intelligence.ai.providers.fake_provider import FakeProvider
from intelligence.repositories import (
    AIInvocationRepository,
    KnowledgeObjectRepository,
    PageSnapshotRepository,
)
from intelligence.services.analysis_orchestrator import AnalysisOrchestrator
from intelligence.services.content_score_service import SCORING_VERSION

TENANT = "tenant-test"  # matches the conftest fixtures


def _orch(sf, provider=None):
    return AnalysisOrchestrator(
        knowledge_repo=KnowledgeObjectRepository(sf, tenant_id=TENANT),
        invocation_repo=AIInvocationRepository(sf, tenant_id=TENANT),
        snapshot_repo=PageSnapshotRepository(sf, tenant_id=TENANT),
        provider=provider,
        tenant_id=TENANT,
    )


def test_content_score_is_deterministic(session_factory, sample_page):
    # Same input, no provider -> identical score across runs (pure computation).
    s1 = _orch(session_factory).run(sample_page).content_intelligence.content_score
    s2 = _orch(session_factory).run(sample_page).content_intelligence.content_score
    assert s1.score == s2.score
    assert [f.factor_name for f in s1.breakdown] == [f.factor_name for f in s2.breakdown]


def test_content_score_is_transparent_and_versioned(session_factory, sample_page):
    score = _orch(session_factory, FakeProvider()).run(sample_page).content_intelligence.content_score
    assert 0 <= score.score <= 100
    assert score.scoring_version == SCORING_VERSION
    assert len(score.breakdown) >= 8
    for factor in score.breakdown:
        assert factor.factor_name and factor.explanation
        assert 0.0 <= factor.weight <= 1.0
        assert isinstance(factor.passed, bool)
    assert score.computed_at is not None


def test_content_score_not_an_ai_call(session_factory, sample_page):
    # Even with no provider (no AI at all) the score is still computed.
    score = _orch(session_factory).run(sample_page).content_intelligence.content_score
    assert score.breakdown  # produced deterministically
