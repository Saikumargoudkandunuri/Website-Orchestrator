"""Unit/integration tests for the API_Surface app factory and ``POST /crawl``
(task 13.1).

These are network-free: the FastAPI :class:`~fastapi.testclient.TestClient`
drives the app, the Digital_Twin is a real
:class:`~digital_twin.repository.DigitalTwinRepository` backed by in-memory
SQLite, the Check_Engine and Fix_Generator are the real subsystems, and the
Crawler is a fake returning canned :class:`~core.types.CrawledPage` records so
no live site is contacted.

Coverage:

* ``POST /crawl`` returns a correct :class:`~core.types.CrawlSummary` (pages,
  issues-by-type, auto-applicable vs report-only counts) and persists the pages,
  issues, and fixes (Req 10.1).
* Invalid input — a blank ``start_url`` or a non-positive ``max_pages`` — is
  rejected with a ``422`` and triggers no crawl and no persistence (Req 10.11).
* A malformed URL that passes body validation is rejected by the Crawler and
  mapped to a ``422`` with no persistence (Req 10.11).
* ``GET /docs`` returns 200 (automatic OpenAPI, Req 10.9).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from check_engine import CheckEngine
from crawler import Crawler
from digital_twin.models import Base
from digital_twin.repository import DigitalTwinRepository
from fix_generator import FixGenerator
from governance.service import GovernanceService

from core.exceptions import InvalidCrawlRequest
from core.types import CrawledPage, ImageRef, LinkStatus

from api import create_app

TENANT = "tenant-a"


# --- Fakes --------------------------------------------------------------------


class FakeCrawler:
    """A CrawlerPort fake returning canned pages and recording its calls."""

    def __init__(self, pages: list[CrawledPage]) -> None:
        self._pages = pages
        self.calls: list[tuple[str, int]] = []

    def crawl_site(self, start_url: str, max_pages: int) -> list[CrawledPage]:
        self.calls.append((start_url, max_pages))
        return list(self._pages)

    def check_link_status(self, url: str):  # pragma: no cover - unused here
        raise NotImplementedError


class SpyCrawler(FakeCrawler):
    """A crawler whose ``crawl_site`` must never be reached for invalid input."""

    def crawl_site(self, start_url: str, max_pages: int) -> list[CrawledPage]:
        self.calls.append((start_url, max_pages))
        raise AssertionError("crawl_site must not be called for invalid input")


class FakePublishingAdapter:
    """Minimal PublishingAdapterPort so the Governance_Layer can be constructed.

    ``POST /crawl`` never writes to the live site, so these are never invoked in
    these tests; they exist only to satisfy the composition root.
    """

    def list_pages(self):  # pragma: no cover - unused
        return []

    def get_page(self, page_id: int):  # pragma: no cover - unused
        raise NotImplementedError

    def update_page_content(self, page_id: int, content: str):  # pragma: no cover
        raise NotImplementedError

    def get_media(self, media_id: int):  # pragma: no cover - unused
        raise NotImplementedError

    def update_media_alt_text(self, media_id: int, alt_text: str):  # pragma: no cover
        raise NotImplementedError


# --- Canned crawl output ------------------------------------------------------


def _crawled_pages() -> list[CrawledPage]:
    """Two canned pages seeding a known mix of issues.

    Page A (home): missing title, missing meta description, thin content,
    missing schema, and one image missing alt text with a *resolvable* media id
    (the single auto-applicable fix). Page B (about): a complete page with one
    broken link.
    """
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)
    home = CrawledPage(
        url="https://example.com/",
        final_url="https://example.com/",
        status_code=200,
        title=None,
        meta_description=None,
        word_count=0,
        has_schema=False,
        images=[ImageRef(media_id=123, filename="red-bike.jpg", alt_text=None)],
        links=[],
        crawled_at=now,
    )
    about = CrawledPage(
        url="https://example.com/about",
        final_url="https://example.com/about",
        status_code=200,
        title="About Us",
        meta_description="About page",
        word_count=500,
        has_schema=True,
        images=[],
        links=[
            LinkStatus(
                url="https://example.com/dead", status_code=404, reachable=False
            )
        ],
        crawled_at=now,
    )
    return [home, about]


# --- App builder --------------------------------------------------------------


def _build_app(crawler):
    """Build an app wired to a real in-memory repo and the given crawler."""
    # A shared in-memory SQLite DB. StaticPool + check_same_thread=False keeps a
    # single connection so the tables created here are visible to the handler,
    # which the TestClient runs in a worker thread.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    repo = DigitalTwinRepository(session_factory, tenant_id=TENANT)
    governance = GovernanceService(repo, FakePublishingAdapter())

    app = create_app(
        crawler=crawler,
        digital_twin=repo,
        check_engine=CheckEngine(),
        fix_generator=FixGenerator(),
        governance=governance,
        tenant_id=TENANT,
    )
    return app, repo


# --- POST /crawl happy path (Req 10.1) ---------------------------------------


def test_post_crawl_returns_summary_and_persists() -> None:
    crawler = FakeCrawler(_crawled_pages())
    app, repo = _build_app(crawler)
    client = TestClient(app)

    response = client.post(
        "/crawl", json={"start_url": "https://example.com/", "max_pages": 10}
    )

    assert response.status_code == 200
    body = response.json()

    # Pages crawled (Req 10.1).
    assert body["pages_crawled"] == 2

    # Issues grouped by type (Req 10.1). Home seeds 5, about seeds 1.
    assert body["issues_by_type"] == {
        "missing_title": 1,
        "missing_meta_description": 1,
        "thin_content": 1,
        "missing_schema": 1,
        "missing_alt_text": 1,
        "broken_links": 1,
    }

    # Auto-applicable vs report-only counts (Req 10.1). Only the resolvable
    # missing-alt-text fix is auto-applicable; the other five are report-only.
    assert body["auto_applicable_count"] == 1
    assert body["report_only_count"] == 5

    # The crawl was delegated to the Crawler with the requested arguments.
    assert crawler.calls == [("https://example.com/", 10)]

    # Persistence: issues and fixes were written to the Digital_Twin.
    active_issues = repo.list_active_issues(TENANT)
    assert len(active_issues) == 6
    pending_fixes = repo.list_pending_fixes(TENANT)
    assert len(pending_fixes) == 6
    assert sum(f.auto_applicable for f in pending_fixes) == 1


# --- Invalid input: blank start_url (Req 10.11) ------------------------------


def test_post_crawl_blank_start_url_rejected_no_crawl_no_persist() -> None:
    crawler = SpyCrawler(_crawled_pages())
    app, repo = _build_app(crawler)
    client = TestClient(app)

    response = client.post("/crawl", json={"start_url": "   ", "max_pages": 10})

    assert response.status_code == 422
    # No crawl was attempted (the spy would have raised if reached) ...
    assert crawler.calls == []
    # ... and nothing was persisted.
    assert repo.list_active_issues(TENANT) == []
    assert repo.list_pending_fixes(TENANT) == []


def test_post_crawl_missing_start_url_rejected() -> None:
    crawler = SpyCrawler(_crawled_pages())
    app, repo = _build_app(crawler)
    client = TestClient(app)

    response = client.post("/crawl", json={"max_pages": 10})

    assert response.status_code == 422
    assert crawler.calls == []


# --- Invalid input: non-positive max_pages (Req 10.11) -----------------------


@pytest.mark.parametrize("max_pages", [0, -1, -100])
def test_post_crawl_non_positive_max_pages_rejected_no_crawl(max_pages) -> None:
    crawler = SpyCrawler(_crawled_pages())
    app, repo = _build_app(crawler)
    client = TestClient(app)

    response = client.post(
        "/crawl", json={"start_url": "https://example.com/", "max_pages": max_pages}
    )

    assert response.status_code == 422
    assert crawler.calls == []
    assert repo.list_active_issues(TENANT) == []
    assert repo.list_pending_fixes(TENANT) == []


# --- Malformed URL reaches the Crawler and is mapped to 422 (Req 10.11) ------


def test_post_crawl_malformed_url_mapped_to_422_no_persist() -> None:
    # The real Crawler validates start_url and raises InvalidCrawlRequest before
    # retrieving anything; the app maps that to a 422 with no persistence.
    real_crawler = Crawler()
    app, repo = _build_app(real_crawler)
    client = TestClient(app)

    response = client.post(
        "/crawl", json={"start_url": "not-a-valid-url", "max_pages": 10}
    )

    assert response.status_code == 422
    assert "Invalid crawl request" in response.json()["detail"]
    assert repo.list_active_issues(TENANT) == []
    assert repo.list_pending_fixes(TENANT) == []


def test_crawler_rejects_malformed_url_directly() -> None:
    # Sanity check that the mapped exception is the Crawler's typed error.
    with pytest.raises(InvalidCrawlRequest):
        Crawler().crawl_site("not-a-valid-url", 10)


# --- OpenAPI docs (Req 10.9) --------------------------------------------------


def test_docs_endpoint_returns_200() -> None:
    app, _repo = _build_app(FakeCrawler(_crawled_pages()))
    client = TestClient(app)

    response = client.get("/docs")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_openapi_schema_available() -> None:
    app, _repo = _build_app(FakeCrawler(_crawled_pages()))
    client = TestClient(app)

    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/crawl" in response.json()["paths"]
