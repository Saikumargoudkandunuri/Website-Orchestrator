"""API tests for the onboarding REST endpoints (network-free)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.types import CrawledPage, ImageRef, LinkStatus

from onboarding.models import Base
from onboarding.repository import OnboardingRepository
from onboarding.routes import build_onboarding_router
from onboarding.services import (
    ConnectionService,
    OnboardingOrchestrator,
    ProjectService,
    WebsiteService,
    WorkspaceService,
)
from onboarding.detector import WebsiteDetector
from onboarding.integrations import IntegrationDiscoveryService


TENANT = "tenant-api"


class _FakeCrawler:
    def __init__(self, pages):
        self._pages = pages

    def crawl_site(self, start_url, max_pages):
        return list(self._pages)

    def check_link_status(self, url):
        return LinkStatus(url=url, status_code=200, reachable=True)


class _FakeDigitalTwin:
    def upsert_pages(self, tenant_id, pages):
        self.pages = pages

    def persist_issues(self, tenant_id, issues):
        return []

    def persist_fixes(self, tenant_id, fixes):
        return []


class _FakeCheck:
    def check_page(self, page):
        return []


class _FakeFix:
    def generate_fix(self, issue, page):
        return None


def _crawled_pages():
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return [
        CrawledPage(
            url="https://example.com/",
            final_url="https://example.com/",
            status_code=200,
            title="Home",
            meta_description="Welcome",
            word_count=500,
            has_schema=True,
            images=[ImageRef(media_id=1, filename="hero.jpg", alt_text=None)],
            links=[LinkStatus(url="https://example.com/about", status_code=200, reachable=True)],
            crawled_at=now,
        )
    ]


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    repo = OnboardingRepository(session_factory, tenant_id=TENANT)

    ws = WorkspaceService(repo)
    ps = ProjectService(repo)
    ws_site = WebsiteService(repo)
    cs = ConnectionService(repo)
    orch = OnboardingOrchestrator(
        repo,
        crawler=_FakeCrawler(_crawled_pages()),
        digital_twin=_FakeDigitalTwin(),
        check_engine=_FakeCheck(),
        fix_generator=_FakeFix(),
        detector=WebsiteDetector(http_get=_fake_get),
        integration_discovery=IntegrationDiscoveryService(http_get=_fake_get),
        tenant_id=TENANT,
    )
    router = build_onboarding_router(
        workspace_service=ws,
        project_service=ps,
        website_service=ws_site,
        connection_service=cs,
        orchestrator=orch,
        tenant_id=TENANT,
    )
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _fake_get(method, url, headers):
    if url.endswith("/robots.txt") or url.endswith("/sitemap.xml") or url.endswith("/feed/"):
        return 200, {}, "x"
    html = (
        '<html><head><meta name="generator" content="WordPress 6.4" />'
        '<link rel="canonical" href="https://example.com/" /></head><body>'
        '<div class="elementor-widget">hi</div></body></html>'
    )
    return 200, {"server": "nginx"}, html


def test_workspace_crud_endpoints(client):
    r = client.post("/v1/workspaces", json={"name": "Acme", "description": "d"})
    assert r.status_code == 201, r.text
    ws_id = r.json()["id"]
    assert client.get("/v1/workspaces").json()[0]["name"] == "Acme"
    r = client.put(f"/v1/workspaces/{ws_id}", json={"name": "Acme2"})
    assert r.status_code == 200 and r.json()["name"] == "Acme2"
    assert client.delete(f"/v1/workspaces/{ws_id}").status_code == 204


def test_full_onboarding_flow_endpoints(client):
    ws = client.post("/v1/workspaces", json={"name": "Acme"}).json()
    proj = client.post(
        "/v1/projects", json={"workspace_id": ws["id"], "name": "M"}
    ).json()
    site = client.post(
        "/v1/websites",
        json={
            "workspace_id": ws["id"],
            "project_id": proj["id"],
            "name": "Site",
            "url": "https://example.com",
            "environment": "production",
            "website_type": "unknown",
        },
    ).json()
    site_id = site["id"]

    # Verify connection (offline mode accepts).
    v = client.post(
        "/v1/connections/verify",
        json={
            "website_id": site_id,
            "connection_type": "wordpress_application_password",
            "credential": "pw",
        },
    )
    assert v.status_code == 200 and v.json()["status"] == "CONNECTED"

    # Detect.
    d = client.post(f"/v1/websites/{site_id}/detect")
    assert d.status_code == 200
    assert d.json()["cms"] == "wordpress"

    # Discover integrations.
    disc = client.post(f"/v1/websites/{site_id}/discover-integrations")
    assert disc.status_code == 200

    # Crawl.
    c = client.post("/v1/crawl", json={"website_id": site_id, "max_pages": 10})
    assert c.status_code == 200 and c.json()["pages"] == 1

    # Build digital twin.
    t = client.post("/v1/build-digital-twin", json={"website_id": site_id})
    assert t.status_code == 200 and t.json()["pages"] == 1

    # Dashboard live.
    dash = client.get("/v1/dashboard/live", params={"website_id": site_id})
    assert dash.status_code == 200
    assert dash.json()["status"] == "READY"
    assert dash.json()["pages"] == 1


def test_website_not_found_returns_404(client):
    r = client.get("/v1/dashboard/live", params={"website_id": "nope"})
    assert r.status_code == 404


def test_my_website_auto_loads_and_second_website_is_rejected(client):
    """Milestone 5 — one account = one connected website: the API never lets a
    tenant connect a second website, and the dashboard auto-loads the single
    connected website via GET /v1/websites/my-website (no list/switcher)."""
    assert client.get("/v1/websites/my-website").json() is None

    ws = client.post("/v1/workspaces", json={"name": "Acme"}).json()
    proj = client.post("/v1/projects", json={"workspace_id": ws["id"], "name": "M"}).json()
    site = client.post(
        "/v1/websites",
        json={
            "workspace_id": ws["id"], "project_id": proj["id"], "name": "Site",
            "url": "https://example.com", "environment": "production", "website_type": "unknown",
        },
    ).json()

    my_site = client.get("/v1/websites/my-website").json()
    assert my_site["id"] == site["id"]

    second = client.post(
        "/v1/websites",
        json={
            "workspace_id": ws["id"], "project_id": proj["id"], "name": "Site Two",
            "url": "https://second.example.com", "environment": "production", "website_type": "unknown",
        },
    )
    assert second.status_code == 400
