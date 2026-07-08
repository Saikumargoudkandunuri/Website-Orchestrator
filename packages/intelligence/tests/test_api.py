"""API contract tests (§9, §10, §13.6). Additive router mounted alongside M1."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api import create_app

TENANT = "tenant-test"  # matches the conftest fixtures


@pytest.fixture()
def client(container, sample_page, page_id):
    # Seed the crawl snapshot the analyze endpoint runs against.
    container.snapshot_repo.upsert(TENANT, page_id, sample_page, crawl_id="c1")
    app = create_app(intelligence=container)
    return TestClient(app)


def test_openapi_advertises_intelligence_and_keeps_m1_routes(client):
    paths = client.get("/openapi.json").json()["paths"]
    for expected in (
        "/intelligence/pages/{page_id}/analyze",
        "/intelligence/pages/{page_id}",
        "/intelligence/pages/{page_id}/versions",
        "/intelligence/pages/{page_id}/versions/{version}",
        "/intelligence/pages/{page_id}/ai-invocations",
        "/intelligence/pages/{page_id}/content-score",
        "/intelligence/pages/{page_id}/fields",
    ):
        assert expected in paths, expected
    # Milestone 1 routes still present (additive, not replacing).
    assert "/crawl" in paths and "/fixes" in paths


def test_analyze_then_read(client, page_id):
    r = client.post(f"/intelligence/pages/{page_id}/analyze", json={})
    assert r.status_code == 200
    assert r.json()["version"] == 1

    ko = client.get(f"/intelligence/pages/{page_id}").json()
    assert ko["keyword_intelligence"]["primary_focus_keyphrase"]
    assert ko["content_intelligence"]["content_score"]["breakdown"]


def test_versions_and_history(client, page_id):
    client.post(f"/intelligence/pages/{page_id}/analyze", json={})
    client.post(f"/intelligence/pages/{page_id}/analyze", json={})
    versions = client.get(f"/intelligence/pages/{page_id}/versions").json()
    assert [v["version"] for v in versions] == [2, 1]
    assert client.get(f"/intelligence/pages/{page_id}/versions/1").json()["version"] == 1


def test_ai_invocations_endpoint(client, page_id):
    client.post(f"/intelligence/pages/{page_id}/analyze", json={})
    invs = client.get(f"/intelligence/pages/{page_id}/ai-invocations").json()
    assert len(invs) >= 8
    assert all("capability" in i and "validation_result" in i for i in invs)


def test_content_score_endpoint(client, page_id):
    client.post(f"/intelligence/pages/{page_id}/analyze", json={})
    cs = client.get(f"/intelligence/pages/{page_id}/content-score").json()
    assert 0 <= cs["score"] <= 100 and cs["breakdown"]


def test_patch_human_override_survives_and_immutable_rejected(client, page_id):
    client.post(f"/intelligence/pages/{page_id}/analyze", json={})

    # Human override on an allowed field.
    r = client.patch(
        f"/intelligence/pages/{page_id}/fields",
        json={"actor": "alice", "fields": {"metadata.meta_description.proposed_value": "Human meta"}},
    )
    assert r.status_code == 200
    assert r.json()["metadata"]["meta_description"]["override_source"] == "human"

    # Re-analyze: override survives.
    r = client.post(f"/intelligence/pages/{page_id}/analyze", json={})
    assert r.json()["knowledge_object"]["metadata"]["meta_description"]["proposed_value"] == "Human meta"

    # Immutable field rejected (409).
    r = client.patch(
        f"/intelligence/pages/{page_id}/fields",
        json={"actor": "alice", "fields": {"identity.canonical_url": "https://evil"}},
    )
    assert r.status_code == 409


def test_analyze_unknown_page_404(client):
    assert client.post("/intelligence/pages/unknown/analyze", json={}).status_code == 404


def test_get_unknown_page_404(client):
    assert client.get("/intelligence/pages/unknown").status_code == 404
