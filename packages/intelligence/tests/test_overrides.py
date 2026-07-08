"""Editor-override semantics tests (§13.5)."""

from __future__ import annotations

from datetime import datetime, timezone

from intelligence.ai.providers.fake_provider import FakeProvider
from intelligence.models.knowledge_object import FieldOverride
from intelligence.models.metadata_intelligence import OverrideSource
from intelligence.repositories import (
    AIInvocationRepository,
    KnowledgeObjectRepository,
    PageSnapshotRepository,
)
from intelligence.services.analysis_orchestrator import AnalysisOrchestrator

TENANT = "tenant-test"  # matches the conftest fixtures


def _orch(sf):
    return AnalysisOrchestrator(
        knowledge_repo=KnowledgeObjectRepository(sf, tenant_id=TENANT),
        invocation_repo=AIInvocationRepository(sf, tenant_id=TENANT),
        snapshot_repo=PageSnapshotRepository(sf, tenant_id=TENANT),
        provider=FakeProvider(),
        tenant_id=TENANT,
    )


def _apply_human_override(repo, ko, path, value):
    """Simulate a human override on an existing version (as the PATCH endpoint does)."""
    from intelligence.field_paths import set_by_path

    set_by_path(ko, path, value)
    ko.overrides[path] = FieldOverride(
        source="human", overridden_at=datetime.now(timezone.utc), overridden_by="alice"
    )
    ko.metadata.meta_description.override_source = OverrideSource.HUMAN
    repo.save(TENANT, ko.model_copy(update={"id": "override", "version": ko.version + 100}))


def test_human_override_survives_reanalysis(session_factory, sample_page):
    orch = _orch(session_factory)
    repo = KnowledgeObjectRepository(session_factory, tenant_id=TENANT)
    ko1 = orch.run(sample_page)
    _apply_human_override(
        repo, ko1, "metadata.meta_description.proposed_value", "HUMAN META"
    )

    ko2 = orch.run(sample_page)
    # Human override carried forward unchanged...
    assert ko2.metadata.meta_description.proposed_value == "HUMAN META"
    assert ko2.metadata.meta_description.override_source == OverrideSource.HUMAN
    # ...while unrelated fields still regenerate normally.
    assert ko2.content_intelligence.content_score.breakdown
    assert ko2.keyword_intelligence.primary_focus_keyphrase


def test_force_regenerate_replaces_override(session_factory, sample_page):
    orch = _orch(session_factory)
    repo = KnowledgeObjectRepository(session_factory, tenant_id=TENANT)
    ko1 = orch.run(sample_page)
    _apply_human_override(
        repo, ko1, "metadata.meta_description.proposed_value", "HUMAN META"
    )

    ko2 = orch.run(sample_page, force_regenerate_overrides=True)
    assert ko2.metadata.meta_description.proposed_value != "HUMAN META"
    assert ko2.metadata.meta_description.override_source == OverrideSource.SYSTEM
