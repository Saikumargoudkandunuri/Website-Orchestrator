"""Milestone 4 — governed executable-engine integration tests.

These prove the seven Milestone-4 engines actually *execute* through the real
governed pipeline (never a shortcut): a real
:class:`~digital_twin.repository.DigitalTwinRepository` (in-memory SQLite), the
real :class:`~governance.service.GovernanceService`, and a spy
Publishing_Adapter that implements the full port (including ``create_page`` /
``delete_page``). Each test asserts the live write actually happened and, for
page creation, that rollback deletes the created page.

Network-free and deterministic. No fixtures stand in for the governance/publish
path — that path is the real one.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.exceptions import WPNotFoundError
from core.interfaces import WPMedia, WPPage
from core.types import CrawledPage, FixStatus
from digital_twin.models import Base
from digital_twin.repository import DigitalTwinRepository
from editing.editor import UpdateHeading
from governance.service import GovernanceService

from api.container import Subsystems
from api.engine_execution import (
    execute_ai_writer_draft,
    execute_ai_writer_seo_meta,
    execute_content_refresh_proposal,
    execute_image_seo_proposal,
    execute_internal_link_proposal,
    execute_page_delete,
    execute_page_merge,
    execute_programmatic_page_plan,
    execute_schema_proposal,
)

TENANT = "tenant-a"
NOW = datetime(2024, 1, 1, tzinfo=timezone.utc)


class SpyPublishingAdapter:
    """Full PublishingAdapterPort in-memory spy (records every write)."""

    def __init__(self, pages: dict[int, WPPage]) -> None:
        self._pages = dict(pages)
        self._next_id = (max(pages, default=0) or 0) + 1000
        self.writes: list[tuple[int, str]] = []
        self.created: list[dict] = []
        self.deleted: list[int] = []
        self._meta: dict[int, dict[str, str]] = {}
        self.meta_writes: list[tuple[int, dict[str, str]]] = []

    def list_pages(self) -> list[WPPage]:
        return list(self._pages.values())

    def get_page(self, page_id: int) -> WPPage:
        page = self._pages.get(page_id)
        if page is None:
            raise WPNotFoundError(f"no page {page_id}")
        return page

    def update_page_content(self, page_id: int, content: str) -> WPPage:
        updated = self._pages[page_id].model_copy(update={"content": content})
        self._pages[page_id] = updated
        self.writes.append((page_id, content))
        return updated

    def create_page(self, *, title: str, content: str, slug: str | None = None,
                    status: str = "draft") -> WPPage:
        pid = self._next_id
        self._next_id += 1
        page = WPPage(id=pid, content=content, title=title, slug=slug, status=status)
        self._pages[pid] = page
        self.created.append({"id": pid, "title": title, "status": status, "slug": slug})
        return page

    def delete_page(self, page_id: int) -> None:
        self._pages.pop(page_id, None)
        self.deleted.append(page_id)

    def get_media(self, media_id: int) -> WPMedia:  # pragma: no cover - unused
        raise NotImplementedError

    def update_media_alt_text(self, media_id: int, alt_text: str) -> WPMedia:  # pragma: no cover
        raise NotImplementedError

    def get_page_meta(self, page_id: int) -> dict[str, str]:
        return dict(self._meta.get(page_id, {}))

    def update_page_meta(self, page_id: int, meta: dict[str, str]) -> dict[str, str]:
        current = dict(self._meta.get(page_id, {}))
        current.update(meta)
        self._meta[page_id] = current
        self.meta_writes.append((page_id, dict(meta)))
        return dict(current)


def _build(*, page_url: str = "https://example.com/", live_content: str = "<h1>Home</h1><p>Welcome.</p>",
           extra_pages: dict[int, WPPage] | None = None):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    repo = DigitalTwinRepository(factory, tenant_id=TENANT)

    # Seed a crawled page and resolve its WordPress identity to id 1.
    repo.upsert_pages(TENANT, [CrawledPage(
        url=page_url, final_url=page_url, status_code=200, title="Home", crawled_at=NOW,
    )])
    repo.resolve_wp_identities(TENANT, [(page_url, 1, "page")])

    pages = {1: WPPage(id=1, content=live_content, title="Home", link=page_url)}
    pages.update(extra_pages or {})
    pa = SpyPublishingAdapter(pages)
    governance = GovernanceService(repo, pa)
    subs = Subsystems(
        crawler=object(), digital_twin=repo, check_engine=object(),
        fix_generator=object(), governance=governance, tenant_id=TENANT,
        publishing_adapter=pa,
    )
    return subs, repo, pa, governance


def test_internal_link_execute_writes_governed_fix() -> None:
    subs, repo, pa, _ = _build()
    outcome = execute_internal_link_proposal(
        subsystems=subs, tenant_id=TENANT,
        proposal={
            "source_url": "https://example.com/", "target_url": "https://example.com/services",
            "suggested_anchor": "Our Services", "reason": "orphan needs equity",
        },
    )
    assert outcome.executed is True
    assert outcome.status == FixStatus.APPLIED.value
    assert outcome.wp_page_id == 1
    assert len(pa.writes) == 1
    written = pa.writes[0][1]
    assert "https://example.com/services" in written and "Our Services" in written


def test_schema_execute_inserts_jsonld_governed() -> None:
    subs, repo, pa, _ = _build()
    outcome = execute_schema_proposal(
        subsystems=subs, tenant_id=TENANT, page_url="https://example.com/",
        schema_type="Organization", data={"name": "Acme"},
    )
    assert outcome.executed is True
    assert len(pa.writes) == 1
    written = pa.writes[0][1]
    assert "application/ld+json" in written and "Organization" in written


def test_content_refresh_execute_updates_heading_governed() -> None:
    subs, repo, pa, _ = _build(live_content="<h1>Old Title</h1><p>body</p>")
    outcome = execute_content_refresh_proposal(
        subsystems=subs, tenant_id=TENANT, page_url="https://example.com/",
        edit=UpdateHeading(level=1, new_text="Fresh Unique Title", index=0),
        description="duplicate H1 differentiation",
    )
    assert outcome.executed is True
    assert "Fresh Unique Title" in pa.writes[0][1]


def test_ai_writer_draft_publishes_governed() -> None:
    subs, repo, pa, _ = _build()
    outcome = execute_ai_writer_draft(
        subsystems=subs, tenant_id=TENANT, page_url="https://example.com/",
        generated_html="<h1>Generated</h1><p>AI content.</p>",
    )
    assert outcome.executed is True
    assert pa.writes[0][1] == "<h1>Generated</h1><p>AI content.</p>"


def test_ai_writer_seo_meta_publishes_governed_and_rollback_restores_before_value() -> None:
    subs, repo, pa, governance = _build()
    pa._meta[1] = {"rank_math_title": "Old Title", "rank_math_description": "Old description"}
    outcome = execute_ai_writer_seo_meta(
        subsystems=subs, tenant_id=TENANT, page_url="https://example.com/",
        seo_meta={"rank_math_title": "New Title", "rank_math_description": "New description",
                  "rank_math_canonical_url": "https://example.com/"},
    )
    assert outcome.executed is True
    assert pa.get_page_meta(1)["rank_math_title"] == "New Title"
    assert len(pa.meta_writes) == 1

    governance.rollback_fix(TENANT, outcome.fix_id, actor="tester", rationale="revert")
    restored = pa.get_page_meta(1)
    assert restored["rank_math_title"] == "Old Title"
    assert restored["rank_math_description"] == "Old description"
    # A key with no prior value rolls back to empty, not left at the new value.
    assert restored.get("rank_math_canonical_url", "") == ""


def test_dispatch_specialist_action_executes_ai_writer_seo_meta() -> None:
    from types import SimpleNamespace

    from api.agent_router import _dispatch_specialist_action

    subs, repo, pa, _ = _build()
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(subsystems=subs)))
    action = {
        "id": "act3", "title": "Publish SEO metadata", "source": "ai_writer_seo_meta_agent",
        "page_url": "https://example.com/",
        "seo_meta": {"rank_math_title": "AI Title", "rank_math_description": "AI description"},
        "status": "proposed",
    }
    run = {"log": []}
    handled = _dispatch_specialist_action(request, run, action)
    assert handled is True
    assert action["status"] == "applied"
    assert pa.get_page_meta(1)["rank_math_title"] == "AI Title"


def test_programmatic_page_created_as_draft_and_rollback_deletes() -> None:
    subs, repo, pa, governance = _build()
    outcome = execute_programmatic_page_plan(
        subsystems=subs, tenant_id=TENANT, title="SEO Services",
        content="<h1>SEO Services</h1>", slug="seo-services",
        reason="real service has no page", planned_url="https://example.com/seo-services",
    )
    assert outcome.executed is True
    assert len(pa.created) == 1
    created = pa.created[0]
    assert created["status"] == "draft"          # never live/public on creation
    assert created["title"] == "SEO Services"
    assert outcome.wp_page_id == created["id"]

    # Rollback deletes the created page (reversible), same governance instance.
    governance.rollback_fix(TENANT, outcome.fix_id, actor="tester", rationale="revert")
    assert pa.deleted == [created["id"]]


def test_page_merge_writes_redirect_notice_governed() -> None:
    subs, repo, pa, _ = _build(live_content="<h1>Duplicate</h1><p>content</p>",
                                extra_pages={2: WPPage(id=2, content="<h1>Canonical</h1>", link="https://example.com/canonical")})
    outcome = execute_page_merge(
        subsystems=subs, tenant_id=TENANT, page_url="https://example.com/",
        merge_into_url="https://example.com/canonical", reason="duplicate title",
    )
    assert outcome.executed is True
    assert "https://example.com/canonical" in pa.writes[0][1]


def test_page_delete_writes_retirement_notice_governed_and_rollback() -> None:
    subs, repo, pa, governance = _build(live_content="<h1>Thin</h1><p>x</p>")
    outcome = execute_page_delete(
        subsystems=subs, tenant_id=TENANT, page_url="https://example.com/", reason="thin isolated page",
    )
    assert outcome.executed is True
    assert "retired" in pa.writes[0][1]
    governance.rollback_fix(TENANT, outcome.fix_id, actor="tester", rationale="revert")
    assert pa._pages[1].content == "<h1>Thin</h1><p>x</p>"


def test_dispatch_specialist_action_executes_page_lifecycle_merge() -> None:
    from types import SimpleNamespace
    from api.agent_router import _dispatch_specialist_action

    subs, repo, pa, _ = _build(extra_pages={2: WPPage(id=2, content="<h1>Canon</h1>", link="https://example.com/canonical")})
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(subsystems=subs)))
    action = {
        "id": "act2", "title": "Merge: https://example.com/", "source": "page_lifecycle_agent",
        "decision": {"action": "merge", "page_url": "https://example.com/",
                     "merge_into_url": "https://example.com/canonical", "reason": "dup"},
        "status": "proposed",
    }
    run = {"log": []}
    handled = _dispatch_specialist_action(request, run, action)
    assert handled is True
    assert action["status"] == "applied"
    assert len(pa.writes) == 1


def test_dispatch_specialist_action_executes_internal_link(monkeypatch) -> None:
    """The run-loop's approval dispatch (agent_router._dispatch_specialist_action)
    turns a real specialist action with no fix_id into a governed execution."""
    from types import SimpleNamespace
    from api.agent_router import _dispatch_specialist_action

    subs, repo, pa, _ = _build()
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(subsystems=subs)))
    action = {
        "id": "act1", "title": "Link 'Our Services' -> https://example.com/services",
        "source": "internal_link_agent", "target": "https://example.com/",
        "proposal": {
            "source_url": "https://example.com/", "target_url": "https://example.com/services",
            "suggested_anchor": "Our Services", "reason": "orphan needs equity",
        },
        "status": "proposed",
    }
    run = {"log": []}
    handled = _dispatch_specialist_action(request, run, action)
    assert handled is True
    assert action["status"] == "applied"
    assert action["fix_id"]
    assert len(pa.writes) == 1


def test_image_seo_execute_applies_lazy_loading_governed() -> None:
    subs, repo, pa, _ = _build(live_content='<img src="https://cdn.example.com/a.jpg" alt="a">'
                                             '<img src="https://cdn.example.com/b.jpg" alt="b">')
    outcome = execute_image_seo_proposal(
        subsystems=subs, tenant_id=TENANT, page_url="https://example.com/",
        proposal={"finding_type": "missing_lazy_loading", "src": "https://cdn.example.com/b.jpg",
                  "loading": "lazy", "reason": "below the fold"},
    )
    assert outcome.executed is True
    assert 'loading="lazy"' in pa.writes[0][1]


def test_image_seo_execute_applies_caption_governed() -> None:
    subs, repo, pa, _ = _build(live_content='<img src="https://cdn.example.com/a.jpg" alt="a">')
    outcome = execute_image_seo_proposal(
        subsystems=subs, tenant_id=TENANT, page_url="https://example.com/",
        proposal={"finding_type": "missing_caption", "src": "https://cdn.example.com/a.jpg",
                  "caption": "A real caption", "reason": "no caption"},
    )
    assert outcome.executed is True
    assert "<figcaption>A real caption</figcaption>" in pa.writes[0][1]


def test_image_seo_execute_rejects_missing_alt_type() -> None:
    subs, repo, pa, _ = _build()
    outcome = execute_image_seo_proposal(
        subsystems=subs, tenant_id=TENANT, page_url="https://example.com/",
        proposal={"finding_type": "missing_alt", "src": "https://cdn.example.com/a.jpg"},
    )
    assert outcome.executed is False
    assert pa.writes == []


def test_execution_skips_page_without_resolved_wp_id() -> None:
    subs, repo, pa, _ = _build()
    # A page that exists in the twin but has no wp_page_id must be skipped, not guessed.
    repo.upsert_pages(TENANT, [CrawledPage(
        url="https://example.com/unmapped", final_url="https://example.com/unmapped",
        status_code=200, title="Unmapped", crawled_at=NOW,
    )])
    outcome = execute_schema_proposal(
        subsystems=subs, tenant_id=TENANT, page_url="https://example.com/unmapped",
        schema_type="Article", data={"headline": "x"},
    )
    assert outcome.executed is False
    assert "wp_page_id" in (outcome.reason or "")
    assert pa.writes == []


# --------------------------------------------------------------------------- #
# Milestone 5 — Notification Center
# --------------------------------------------------------------------------- #


def test_notification_center_reports_real_governed_fix_actions() -> None:
    """GET /v1/analytics/notifications aggregates real Governance audit-trail
    entries (apply + rollback) into the Notification Center feed — no
    fabricated/simulated entries.
    """
    from api import create_app

    subs, repo, pa, governance = _build()
    outcome = execute_ai_writer_seo_meta(
        subsystems=subs, tenant_id=TENANT, page_url="https://example.com/",
        seo_meta={"rank_math_title": "New Title"},
    )
    assert outcome.executed is True

    app = create_app(subsystems=subs)
    from fastapi.testclient import TestClient

    client = TestClient(app)
    resp = client.get("/v1/analytics/notifications")
    assert resp.status_code == 200
    feed = resp.json()
    assert len(feed) >= 1
    applied = next(n for n in feed if n["action_taken"].startswith("AI applied"))
    assert applied["category"] == "SEO Metadata"
    assert applied["rollback_available"] is True
    assert applied["source"] == "governance_audit_trail"

    governance.rollback_fix(TENANT, outcome.fix_id, actor="tester", rationale="revert")
    feed_after = client.get("/v1/analytics/notifications").json()
    rolled_back = next(n for n in feed_after if "rolled back" in n["action_taken"].lower())
    assert rolled_back["category"] == "SEO Metadata"


def test_notification_center_empty_when_no_actions_taken() -> None:
    """An account with no governed actions yet gets an honest empty feed, not
    a placeholder/fixture entry."""
    from api import create_app
    from fastapi.testclient import TestClient

    subs, repo, pa, governance = _build()
    app = create_app(subsystems=subs)
    client = TestClient(app)
    resp = client.get("/v1/analytics/notifications")
    assert resp.status_code == 200
    assert resp.json() == []
