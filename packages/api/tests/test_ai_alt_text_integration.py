"""Milestone 1 integration — the AI alt-text loop through the API_Surface.

Drives the full loop network-free through a FastAPI :class:`TestClient` with a
real in-memory SQLite Digital_Twin, an in-memory WordPress spy, and a
:class:`~fix_generator.FixGenerator` wired to the deterministic
:class:`~ai_generator.DeterministicAltTextGenerationService`:

    POST /crawl  → a ``missing_alt_text`` fix is generated with real
                   (deterministic-AI) alt text + model/confidence provenance and
                   persisted as pending
    GET /fixes   → the typed payload (proposed value + generation metadata) is
                   returned over HTTP
    approve      → Governance publishes the AI alt text to the media target
    verify write → the live value equals the AI-generated alt text
    rollback     → the prior (empty) alt text is restored

It also proves the failure path: when generation fails the crawl still succeeds
and the fix degrades to report-only (no crash).
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from ai_generator import DeterministicAltTextGenerationService
from check_engine import CheckEngine
from digital_twin.models import Base
from digital_twin.repository import DigitalTwinRepository
from fix_generator import FixGenerator
from governance.service import GovernanceService

from core.exceptions import GenerationError
from core.interfaces import WPMedia, WPPage
from core.results import Err
from core.types import CrawledPage, FixStatus, ImageRef

from api import create_app

TENANT = "tenant-ai"
NOW = datetime(2024, 1, 1, tzinfo=timezone.utc)
MEDIA_ID = 42


# --- Fakes --------------------------------------------------------------------


class FakeCrawler:
    def __init__(self, pages: list[CrawledPage]) -> None:
        self._pages = pages

    def crawl_site(self, start_url: str, max_pages: int) -> list[CrawledPage]:
        return list(self._pages)

    def check_link_status(self, url: str):  # pragma: no cover - unused
        raise NotImplementedError


class InMemoryWordPress:
    """A minimal in-memory PublishingAdapterPort spy (media only)."""

    def __init__(self, media: dict[int, WPMedia]) -> None:
        self.media = media
        self.writes: list[tuple[int, str]] = []

    def list_pages(self):  # pragma: no cover - unused
        return []

    def get_page(self, page_id: int) -> WPPage:  # pragma: no cover - unused
        raise NotImplementedError

    def update_page_content(self, page_id: int, content: str):  # pragma: no cover
        raise NotImplementedError

    def get_media(self, media_id: int) -> WPMedia:
        return self.media[media_id]

    def update_media_alt_text(self, media_id: int, alt_text: str) -> WPMedia:
        updated = self.media[media_id].model_copy(update={"alt_text": alt_text})
        self.media[media_id] = updated
        self.writes.append((media_id, alt_text))
        return updated


class FailingAltTextService:
    def generate_alt_text(self, request):
        return Err(GenerationError("model offline"))


# --- Builders -----------------------------------------------------------------


def _page_with_missing_alt() -> CrawledPage:
    return CrawledPage(
        url="https://example.com/gallery",
        final_url="https://example.com/gallery",
        status_code=200,
        title="Product gallery",
        meta_description="Our products",
        word_count=500,
        has_schema=True,
        images=[ImageRef(media_id=MEDIA_ID, filename="green-mountain-bike.jpg", alt_text=None)],
        links=[],
        crawled_at=NOW,
    )


def _build(alt_text_service):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    repo = DigitalTwinRepository(factory, tenant_id=TENANT)
    wp = InMemoryWordPress(
        {MEDIA_ID: WPMedia(id=MEDIA_ID, alt_text="", source_url="https://x/green-mountain-bike.jpg")}
    )
    governance = GovernanceService(repo, wp)
    app = create_app(
        crawler=FakeCrawler([_page_with_missing_alt()]),
        digital_twin=repo,
        check_engine=CheckEngine(),
        fix_generator=FixGenerator(alt_text_service),
        governance=governance,
        tenant_id=TENANT,
    )
    return TestClient(app), wp


# --- Tests --------------------------------------------------------------------


def test_ai_alt_text_generate_approve_publish_rollback() -> None:
    client, wp = _build(DeterministicAltTextGenerationService())

    # Observe: crawl generates a real AI alt-text fix.
    resp = client.post(
        "/crawl", json={"start_url": "https://example.com/gallery", "max_pages": 5}
    )
    assert resp.status_code == 200
    assert resp.json()["auto_applicable_count"] == 1

    # GET /fixes exposes the typed payload including generation provenance.
    fixes = client.get("/fixes").json()
    alt_fixes = [f for f in fixes if f["fix_type"] == "update_alt_text"]
    assert len(alt_fixes) == 1
    fix = alt_fixes[0]
    assert fix["auto_applicable"] == 1
    assert fix["proposed_value"] == "Green mountain bike"
    assert fix["generation_model"] == "deterministic-alttext-v1"
    assert fix["generation_confidence"] == 0.9
    assert fix["target_ref"]["media_id"] == MEDIA_ID
    proposed = fix["proposed_value"]

    # Execute: approve publishes the AI alt text to the media target.
    assert wp.get_media(MEDIA_ID).alt_text == ""  # BEFORE value
    approve = client.post(
        f"/fixes/{fix['id']}/approve",
        json={"actor": "alice", "rationale": "looks accurate"},
    )
    assert approve.status_code == 200
    assert approve.json()["status"] == FixStatus.APPLIED.value
    assert wp.writes == [(MEDIA_ID, proposed)]
    assert wp.get_media(MEDIA_ID).alt_text == proposed

    # Audit trail captured the applied transition with the BEFORE value.
    audit = client.get("/audit-log").json()
    applied = [
        e for e in audit
        if e["fix_id"] == fix["id"] and e["transition"] == "pending->applied"
    ]
    assert len(applied) == 1
    assert applied[0]["before_value"] == ""

    # Verify/rollback: restore the prior empty alt text.
    rollback = client.post(
        f"/fixes/{fix['id']}/rollback",
        json={"actor": "alice", "rationale": "reverting"},
    )
    assert rollback.status_code == 200
    assert rollback.json()["status"] == FixStatus.ROLLED_BACK.value
    assert wp.get_media(MEDIA_ID).alt_text == ""


def test_crawl_survives_ai_generation_failure() -> None:
    client, _wp = _build(FailingAltTextService())

    resp = client.post(
        "/crawl", json={"start_url": "https://example.com/gallery", "max_pages": 5}
    )
    # The crawl still succeeds — a generation failure never crashes the workflow.
    assert resp.status_code == 200
    fixes = client.get("/fixes").json()
    alt_fixes = [
        f for f in fixes
        if f["issue_id"] and f["reason"] and "AI alt-text generation failed" in f["reason"]
    ]
    assert len(alt_fixes) == 1
    # It degraded to a report-only fix (not auto-applicable, no fix type).
    assert alt_fixes[0]["auto_applicable"] == 0
    assert alt_fixes[0]["fix_type"] is None
