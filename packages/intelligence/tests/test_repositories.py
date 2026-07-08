"""Repository tests (§9): append-only versioning, invocation audit, snapshots."""

from __future__ import annotations

from intelligence.models.ai_invocation import AIInvocation, ValidationOutcome
from intelligence.models.identity import IdentitySection
from intelligence.models.knowledge_object import KnowledgeObject
from intelligence.repositories import (
    AIInvocationRepository,
    KnowledgeObjectRepository,
    PageSnapshotRepository,
)

TENANT = "tenant-test"  # matches the conftest container/page_id fixtures


def _ko(pid: str, version: int, slug: str = "") -> KnowledgeObject:
    ident = IdentitySection(url="https://x/p", slug=slug)
    return KnowledgeObject(
        id=f"k{version}", page_id=pid, tenant_id=TENANT, version=version, identity=ident
    )


def test_append_only_versioning(session_factory):
    repo = KnowledgeObjectRepository(session_factory, tenant_id=TENANT)
    pid = "page-1"
    assert repo.next_version(TENANT, pid) == 1
    repo.save(TENANT, _ko(pid, 1, "v1"))
    assert repo.next_version(TENANT, pid) == 2
    repo.save(TENANT, _ko(pid, 2, "v2"))

    assert repo.get_latest(TENANT, pid).version == 2
    assert repo.get_latest(TENANT, pid).identity.slug == "v2"
    assert repo.get_version(TENANT, pid, 1).identity.slug == "v1"  # prior preserved
    assert [v.version for v in repo.list_versions(TENANT, pid)] == [2, 1]


def test_get_latest_none_when_absent(session_factory):
    repo = KnowledgeObjectRepository(session_factory, tenant_id=TENANT)
    assert repo.get_latest(TENANT, "missing") is None


def test_ai_invocation_audit(session_factory):
    repo = AIInvocationRepository(session_factory, tenant_id=TENANT)
    repo.save(TENANT, AIInvocation(
        id="i1", tenant_id=TENANT, page_id="page-1", capability="meta_generator",
        prompt_version="1.0.0", provider="fake", model="fake-model-1",
        raw_response='{"meta_description":"x"}', validation_result=ValidationOutcome.PASSED,
    ))
    got = repo.list_for_page(TENANT, "page-1")
    assert len(got) == 1 and got[0].capability == "meta_generator"
    assert got[0].raw_response  # raw retained


def test_page_snapshot_roundtrip(session_factory, sample_page):
    repo = PageSnapshotRepository(session_factory, tenant_id=TENANT)
    repo.upsert(TENANT, "page-1", sample_page, crawl_id="c1")
    got = repo.get(TENANT, "page-1")
    assert got is not None and got.url == sample_page.url
    assert repo.known_urls(TENANT) == [sample_page.url]
