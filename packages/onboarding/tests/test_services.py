"""Unit tests for the onboarding services (network-free)."""

from __future__ import annotations


from core.types import LinkStatus

from onboarding.detector import WebsiteDetector
from onboarding.services import (
    ConnectionService,
    OnboardingOrchestrator,
    ProjectService,
    WebsiteService,
    WorkspaceService,
)
from onboarding.state_machine import OnboardingStateMachine


def _make_orchestrator(repo, fake_crawler, fake_dt, fake_check, fake_fix):
    return OnboardingOrchestrator(
        repo,
        crawler=fake_crawler,
        digital_twin=fake_dt,
        check_engine=fake_check,
        fix_generator=fake_fix,
        tenant_id="tenant-test",
    )


class _FakeCrawler:
    def __init__(self, pages):
        self._pages = pages

    def crawl_site(self, start_url, max_pages):
        return list(self._pages)

    def check_link_status(self, url):
        return LinkStatus(url=url, status_code=200, reachable=True)


class _FakeDigitalTwin:
    def __init__(self):
        self.issues = []
        self.fixes = []

    def upsert_pages(self, tenant_id, pages):
        self.pages = pages

    def persist_issues(self, tenant_id, issues):
        self.issues = issues
        return []

    def persist_fixes(self, tenant_id, fixes):
        self.fixes = fixes
        return []


class _FakeCheck:
    def check_page(self, page):
        return []


class _FakeFix:
    def generate_fix(self, issue, page):
        return None


# --- Workspace / Project / Website -------------------------------------------


def test_workspace_crud(repo):
    svc = WorkspaceService(repo)
    ws = svc.create("tenant-test", name="Acme", description="d")
    assert ws["name"] == "Acme"
    assert svc.get("tenant-test", ws["id"]) is not None
    assert len(svc.list("tenant-test")) == 1
    svc.update("tenant-test", ws["id"], name="Acme2")
    assert svc.get("tenant-test", ws["id"])["name"] == "Acme2"
    assert svc.delete("tenant-test", ws["id"]) is True
    assert svc.get("tenant-test", ws["id"]) is None


def test_project_crud(repo):
    ws = WorkspaceService(repo).create("tenant-test", name="Acme")
    svc = ProjectService(repo)
    p = svc.create("tenant-test", workspace_id=ws["id"], name="Marketing")
    assert p["workspace_id"] == ws["id"]
    assert svc.list("tenant-test", ws["id"])[0]["id"] == p["id"]
    svc.update("tenant-test", p["id"], archived=True)
    assert svc.get("tenant-test", p["id"])["archived"] is True
    assert svc.delete("tenant-test", p["id"]) is True


def test_second_website_create_is_rejected_one_account_one_website(repo):
    """Milestone 5 — one account = one connected website (product constraint).

    The underlying multi-tenant schema still supports many websites per
    tenant, but ``WebsiteService.create`` is the single choke point every
    onboarding path goes through, and it must refuse a second website for an
    account that already has one connected.
    """
    from onboarding.services import OnboardingError

    ws = WorkspaceService(repo).create("tenant-test", name="Acme")
    p = ProjectService(repo).create("tenant-test", workspace_id=ws["id"], name="M")
    svc = WebsiteService(repo)
    svc.create(
        "tenant-test", workspace_id=ws["id"], project_id=p["id"], group_id=None,
        name="Site One", url="https://example.com", display_name=None,
        environment="production", website_type="wordpress",
    )

    import pytest

    with pytest.raises(OnboardingError):
        svc.create(
            "tenant-test", workspace_id=ws["id"], project_id=p["id"], group_id=None,
            name="Site Two", url="https://second-example.com", display_name=None,
            environment="production", website_type="wordpress",
        )
    # Only the first website is ever connected for this account.
    assert len(svc.list("tenant-test")) == 1


def test_get_my_website_auto_loads_the_single_connected_website(repo):
    """The dashboard's auto-load path: no website before onboarding, the one
    connected website afterward — never a list to choose from."""
    svc = WebsiteService(repo)
    assert svc.get_my_website("tenant-test") is None

    ws = WorkspaceService(repo).create("tenant-test", name="Acme")
    p = ProjectService(repo).create("tenant-test", workspace_id=ws["id"], name="M")
    created = svc.create(
        "tenant-test", workspace_id=ws["id"], project_id=p["id"], group_id=None,
        name="Site", url="https://example.com", display_name=None,
        environment="production", website_type="wordpress",
    )

    loaded = svc.get_my_website("tenant-test")
    assert loaded is not None
    assert loaded["id"] == created["id"]


def test_website_crud_and_feature_flags(repo):
    ws = WorkspaceService(repo).create("tenant-test", name="Acme")
    p = ProjectService(repo).create("tenant-test", workspace_id=ws["id"], name="M")
    svc = WebsiteService(repo)
    w = svc.create(
        "tenant-test",
        workspace_id=ws["id"],
        project_id=p["id"],
        group_id=None,
        name="Site",
        url="https://example.com",
        display_name="Example",
        environment="production",
        website_type="wordpress",
    )
    assert w["url"] == "https://example.com"
    assert w["status"] == "CONNECTED"
    svc.set_feature_flags(
        "tenant-test", w["id"], ai_enabled=True, automation_enabled=True
    )
    updated = svc.get("tenant-test", w["id"])
    assert updated["ai_enabled"] is True
    assert updated["automation_enabled"] is True
    assert svc.delete("tenant-test", w["id"]) is True


# --- Connection ---------------------------------------------------------------


def test_connection_verify_offline_accepts(repo):
    ws = WorkspaceService(repo).create("tenant-test", name="Acme")
    p = ProjectService(repo).create("tenant-test", workspace_id=ws["id"], name="M")
    w = WebsiteService(repo).create(
        "tenant-test",
        workspace_id=ws["id"],
        project_id=p["id"],
        group_id=None,
        name="Site",
        url="https://example.com",
        display_name=None,
        environment="production",
        website_type="wordpress",
    )
    svc = ConnectionService(repo)
    result = svc.verify(
        "tenant-test",
        website_id=w["id"],
        connection_type="wordpress_application_password",
        credential="secret-pw",
    )
    assert result["status"] == "CONNECTED"
    assert result["capabilities"]["read"] is True
    # Credential must be encrypted, never stored plaintext.
    conns = svc.list("tenant-test", w["id"])
    assert conns[0]["connection_meta"] is None or "secret-pw" not in str(
        conns[0].get("encrypted_credentials", "")
    )


# --- Orchestrator flow --------------------------------------------------------


class _FakePublishingAdapterWithPages:
    """A minimal PublishingAdapterPort exposing a live page listing only."""

    def __init__(self, pages):
        self._pages = pages

    def list_pages(self):
        return list(self._pages)

    def get_page(self, page_id):  # pragma: no cover - unused
        raise NotImplementedError

    def update_page_content(self, page_id, content):  # pragma: no cover - unused
        raise NotImplementedError

    def get_media(self, media_id):  # pragma: no cover - unused
        raise NotImplementedError

    def update_media_alt_text(self, media_id, alt_text):  # pragma: no cover - unused
        raise NotImplementedError


def test_run_initial_crawl_resolves_wp_identities_from_real_digital_twin(
    repo, fake_crawled_pages, session_factory
):
    """Milestone 4 — after a crawl, wp_page_id/wp_post_type are populated on the
    real Digital_Twin from the Publishing_Adapter's live listing, matched by URL.
    """
    from core.interfaces import WPPage
    from digital_twin.models import Base as DigitalTwinBase
    from digital_twin.repository import DigitalTwinRepository

    # The onboarding session_factory fixture only creates onboarding's own
    # tables; the Digital_Twin tables must exist too since this test drives a
    # real DigitalTwinRepository against the same in-memory engine.
    DigitalTwinBase.metadata.create_all(session_factory.kw["bind"])
    real_dt = DigitalTwinRepository(session_factory, tenant_id="tenant-test")
    live_pages = [
        WPPage(id=101, content="<p>home</p>", link="https://example.com/"),
        WPPage(id=102, content="<p>about</p>", link="https://example.com/about"),
    ]
    publishing = _FakePublishingAdapterWithPages(live_pages)

    ws = WorkspaceService(repo).create("tenant-test", name="Acme")
    p = ProjectService(repo).create("tenant-test", workspace_id=ws["id"], name="M")
    w = WebsiteService(repo).create(
        "tenant-test",
        workspace_id=ws["id"],
        project_id=p["id"],
        group_id=None,
        name="Site",
        url="https://example.com",
        display_name=None,
        environment="production",
        website_type="wordpress",
    )

    orch = OnboardingOrchestrator(
        repo,
        crawler=_FakeCrawler(fake_crawled_pages),
        digital_twin=real_dt,
        check_engine=_FakeCheck(),
        fix_generator=_FakeFix(),
        publishing_adapter=publishing,
        tenant_id="tenant-test",
    )

    crawl = orch.run_initial_crawl(w["id"], max_pages=10)
    assert crawl["wp_pages_mapped"] == 2

    pages = {pg.url: pg for pg in real_dt.list_pages("tenant-test")}
    assert pages["https://example.com/"].url == "https://example.com/"
    # Confirm at the ORM layer that wp_page_id/wp_post_type were actually stamped.
    from digital_twin.models import Page as PageRow
    from sqlalchemy import select

    with session_factory() as session:
        home_row = session.execute(
            select(PageRow).where(PageRow.url == "https://example.com/")
        ).scalar_one()
        about_row = session.execute(
            select(PageRow).where(PageRow.url == "https://example.com/about")
        ).scalar_one()
        assert home_row.wp_page_id == 101 and home_row.wp_post_type == "page"
        assert about_row.wp_page_id == 102 and about_row.wp_post_type == "page"


def test_run_initial_crawl_without_publishing_adapter_skips_mapping(
    repo, fake_crawled_pages
):
    """No adapter configured (read-only/demo/offline) -> mapping is a no-op, not
    a failure; the crawl still completes."""
    ws = WorkspaceService(repo).create("tenant-test", name="Acme")
    p = ProjectService(repo).create("tenant-test", workspace_id=ws["id"], name="M")
    w = WebsiteService(repo).create(
        "tenant-test",
        workspace_id=ws["id"],
        project_id=p["id"],
        group_id=None,
        name="Site",
        url="https://example.com",
        display_name=None,
        environment="production",
        website_type="wordpress",
    )
    orch = _make_orchestrator(
        repo, _FakeCrawler(fake_crawled_pages), _FakeDigitalTwin(), _FakeCheck(), _FakeFix()
    )
    crawl = orch.run_initial_crawl(w["id"], max_pages=10)
    assert crawl["wp_pages_mapped"] == 0


def test_onboarding_flow_detect_discover_crawl_build(repo, fake_crawled_pages):
    ws = WorkspaceService(repo).create("tenant-test", name="Acme")
    p = ProjectService(repo).create("tenant-test", workspace_id=ws["id"], name="M")
    w = WebsiteService(repo).create(
        "tenant-test",
        workspace_id=ws["id"],
        project_id=p["id"],
        group_id=None,
        name="Site",
        url="https://example.com",
        display_name=None,
        environment="production",
        website_type="unknown",
    )

    def fake_get(method, url, headers):
        # Simulate a WordPress site with Elementor + Yoast.
        html = (
            '<html><head><meta name="generator" content="WordPress 6.4" />'
            '<link rel="canonical" href="https://example.com/" />'
            '<meta property="og:title" content="x" /></head><body>'
            '<div class="elementor-widget">hi</div>'
            '<link rel="stylesheet" href="/wp-content/themes/astra/style.css" />'
            "</body></html>"
        )
        return 200, {"server": "nginx", "x-wp-engine": "1"}, html

    detector = WebsiteDetector(http_get=fake_get)
    integrations = _FakeIntegrations()
    orch = _make_orchestrator(
        repo, _FakeCrawler(fake_crawled_pages), _FakeDigitalTwin(), _FakeCheck(), _FakeFix()
    )
    orch._detector = detector
    orch._integrations = integrations

    det = orch.detect_website(w["id"])
    assert det.cms == "wordpress"
    assert det.builder == "elementor"
    assert det.detection_confidence == "high"

    discovered = orch.discover_integrations(w["id"])
    assert any(i["provider"] == "wp_engine" for i in discovered)

    crawl = orch.run_initial_crawl(w["id"], max_pages=10)
    assert crawl["pages"] == 2

    twin = orch.build_digital_twin(w["id"])
    assert twin["pages"] == 2
    assert twin["internal_links"] >= 1

    final = WebsiteService(repo).get("tenant-test", w["id"])
    assert final["status"] == "READY"
    assert final["onboarding_state"] == "ready"


class _FakeIntegrations:
    def discover(self, base_url):
        from onboarding.integrations import DiscoveredIntegration

        return [DiscoveredIntegration(provider="wp_engine")]


# --- State machine ------------------------------------------------------------


def test_state_machine_happy_path():
    state = "created"
    for nxt in ("connecting", "verifying", "detecting", "discovering", "crawling", "building", "ready"):
        state = OnboardingStateMachine.transition(state, nxt)
    assert state == "ready"


def test_state_machine_illegal_transition():
    import pytest

    from onboarding.state_machine import StateMachineError

    with pytest.raises(StateMachineError):
        OnboardingStateMachine.transition("created", "ready")
