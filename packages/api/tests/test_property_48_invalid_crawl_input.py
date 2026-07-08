"""Property 48 — Invalid crawl input is rejected without side effects.

Feature: website-orchestrator-milestone-0, Property 48: Invalid crawl input is
rejected without side effects.

**Validates: Requirements 10.11**

``POST /crawl`` must reject invalid input before anything is crawled or
persisted (Req 10.11). Invalid input comes in three families:

1. A **blank/whitespace/missing** ``start_url`` (with an otherwise valid
   ``max_pages``). Rejected by :class:`~api.schemas.CrawlRequest` body
   validation *before* the handler delegates to any subsystem, so the Crawler
   is never even reached.
2. A **non-positive** ``max_pages`` (with an otherwise valid ``start_url``).
   Also rejected by body validation before the handler runs.
3. A **malformed-but-nonblank** ``start_url`` (a string that is not a valid
   http/https URL) with a valid ``max_pages``. This passes body validation, so
   the handler delegates to the Crawler, which validates the URL and raises
   :class:`~core.exceptions.InvalidCrawlRequest` *before retrieving anything*;
   the app maps that to a ``422`` with no persistence.

This property drives that guarantee network-free: the FastAPI
:class:`~fastapi.testclient.TestClient` is wired to a real
:class:`~digital_twin.repository.DigitalTwinRepository` backed by in-memory
SQLite, the real Check_Engine/Fix_Generator, a minimal Governance_Layer, and a
**spy** Crawler. The spy records every ``crawl_site`` call so the test can
assert:

* for families 1 & 2 the spy is **never called** (body validation rejected the
  request first), and
* for family 3 the spy **is called once** and rejects the malformed URL by
  raising :class:`~core.exceptions.InvalidCrawlRequest`.

For every generated invalid input we assert the response is a non-2xx rejection
(specifically ``422``), and that nothing was persisted — both directly via the
repository and through the ``GET /issues`` and ``GET /fixes`` read endpoints,
which must remain empty.
"""

from __future__ import annotations

from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from check_engine import CheckEngine
from digital_twin.models import Base
from digital_twin.repository import DigitalTwinRepository
from fix_generator import FixGenerator
from governance.service import GovernanceService

from core.exceptions import InvalidCrawlRequest
from core.types import CrawledPage

from api import create_app

TENANT = "tenant-a"


# --- Fakes --------------------------------------------------------------------


def _looks_like_valid_http_url(url: str) -> bool:
    """Mirror the Crawler's ``start_url`` validity check.

    A start URL is valid only when it parses to an ``http``/``https`` scheme
    with a non-empty host (Req 1.1, 1.5). Any other string is malformed.
    """
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    return parts.scheme.lower() in {"http", "https"} and bool(parts.hostname)


class SpyCrawler:
    """A CrawlerPort spy that records calls and faithfully rejects bad URLs.

    ``crawl_site`` records every invocation. For the body-validation families
    the handler never delegates here, so ``calls`` stays empty. For a
    malformed-but-nonblank URL the handler *does* delegate here; the spy
    validates exactly as the real Crawler does and raises
    :class:`~core.exceptions.InvalidCrawlRequest` before retrieving anything
    (Req 10.11). A valid URL reaching the spy would mean the generator produced
    a non-malformed URL; it returns no pages so the test's rejection assertions
    would flag that generator error rather than silently passing.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def crawl_site(self, start_url: str, max_pages: int) -> list[CrawledPage]:
        self.calls.append((start_url, max_pages))
        if not _looks_like_valid_http_url(start_url):
            raise InvalidCrawlRequest(
                f"start_url is not a valid http/https URL: {start_url!r}"
            )
        return []

    def check_link_status(self, url: str):  # pragma: no cover - unused here
        raise NotImplementedError


class FakePublishingAdapter:
    """Minimal PublishingAdapterPort to satisfy the composition root.

    ``POST /crawl`` never writes to the live site, so these are never invoked;
    they exist only so the Governance_Layer can be constructed.
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


# --- App builder --------------------------------------------------------------


def _build_app(crawler):
    """Build a fresh app wired to a real in-memory repo and the given crawler.

    A fresh in-memory SQLite DB per call guarantees a clean persistence slate
    for each generated example. ``StaticPool`` + ``check_same_thread=False``
    keeps a single connection so the tables created here are visible to the
    handler, which the TestClient runs in a worker thread.
    """
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


# --- Generators for the three invalid families -------------------------------

#: ``max_pages`` values the Crawler accepts (its supported range is [1, 10000]).
_VALID_MAX_PAGES = st.integers(min_value=1, max_value=10_000)

#: Blank/whitespace-only start URLs. ``""`` is rejected by ``min_length=1``; the
#: rest are rejected by the non-blank field validator (Req 10.11).
_BLANK_START_URLS = st.sampled_from(
    ["", " ", "   ", "\t", "\n", "\r\n", " \t \n ", "\u00a0", "  \u2003 "]
)

#: Nonblank strings that are not valid http/https URLs. Each passes the body's
#: non-blank check but is rejected by the Crawler (bad scheme or no host).
_MALFORMED_URLS = st.sampled_from(
    [
        "not-a-valid-url",
        "example.com",
        "www.example.com",
        "http://",
        "https://",
        "http:///path",
        "https:///",
        "ftp://example.com",
        "file:///etc/hosts",
        "mailto:a@b.com",
        "tel:+123456",
        "javascript:alert(1)",
        "://noscheme",
        "foo bar",
        "htp://example.com",
        "12345",
    ]
)

#: A few valid start URLs, reused only to isolate the non-positive-max_pages
#: family (so the *only* thing wrong with the request is ``max_pages``).
_VALID_START_URLS = st.sampled_from(
    [
        "https://example.com/",
        "http://example.org",
        "https://foo.example.com/page",
        "http://sub.example.net/a/b",
    ]
)


@st.composite
def _blank_start_url_cases(draw) -> dict:
    """Family 1: blank/whitespace/missing ``start_url`` + valid ``max_pages``."""
    max_pages = draw(_VALID_MAX_PAGES)
    if draw(st.booleans()):
        # Omit start_url entirely (a required field).
        return {"body": {"max_pages": max_pages}, "family": "body"}
    return {
        "body": {"start_url": draw(_BLANK_START_URLS), "max_pages": max_pages},
        "family": "body",
    }


@st.composite
def _non_positive_max_pages_cases(draw) -> dict:
    """Family 2: valid ``start_url`` + non-positive ``max_pages``."""
    return {
        "body": {
            "start_url": draw(_VALID_START_URLS),
            "max_pages": draw(st.integers(max_value=0)),
        },
        "family": "body",
    }


@st.composite
def _malformed_url_cases(draw) -> dict:
    """Family 3: malformed-but-nonblank ``start_url`` + valid ``max_pages``."""
    return {
        "body": {
            "start_url": draw(_MALFORMED_URLS),
            "max_pages": draw(_VALID_MAX_PAGES),
        },
        "family": "malformed",
    }


def _invalid_crawl_cases() -> st.SearchStrategy[dict]:
    """Draw from all three invalid-input families with equal weight."""
    return st.one_of(
        _blank_start_url_cases(),
        _non_positive_max_pages_cases(),
        _malformed_url_cases(),
    )


# --- Property 48 --------------------------------------------------------------


@pytest.mark.property
@settings(max_examples=100, deadline=None)
@given(case=_invalid_crawl_cases())
def test_property_48_invalid_crawl_input_rejected_without_side_effects(
    case: dict,
) -> None:
    """Any invalid crawl input is rejected (422) with no crawl and no persistence.

    **Validates: Requirements 10.11**
    """
    body = case["body"]
    family = case["family"]

    crawler = SpyCrawler()
    app, repo = _build_app(crawler)
    client = TestClient(app)

    response = client.post("/crawl", json=body)

    # Rejected without success: always a non-2xx client error, specifically 422.
    assert response.status_code >= 400
    assert response.status_code == 422

    if family == "body":
        # Body validation rejected the request before the handler delegated to
        # any subsystem: the Crawler was never called.
        assert crawler.calls == []
    else:
        # A malformed-but-nonblank URL passed body validation and reached the
        # Crawler, which rejected it (InvalidCrawlRequest -> 422) before
        # retrieving anything.
        assert len(crawler.calls) == 1

    # No persistence occurred (Req 10.11): issues and fixes remain empty, both
    # directly via the repository and through the read endpoints.
    assert repo.list_active_issues(TENANT) == []
    assert repo.list_pending_fixes(TENANT) == []
    assert client.get("/issues").json() == []
    assert client.get("/fixes").json() == []
