"""Property 45 — Crawl summary counts match persisted data.

Feature: website-orchestrator-milestone-0, Property 45: Crawl summary counts
match persisted data

For any set of :class:`~core.types.CrawledPage` records the Crawler returns,
``POST /crawl`` returns a :class:`~core.types.CrawlSummary` whose counts are a
faithful summary of what was actually persisted to the Digital_Twin (Req 10.1):

* ``pages_crawled`` equals the number of pages crawled (and, since every
  generated page has a unique URL, the number of page rows persisted);
* ``issues_by_type`` equals the persisted issues grouped by issue type, as
  reported by ``GET /issues``;
* ``auto_applicable_count`` and ``report_only_count`` equal the persisted
  suggested fixes split by ``auto_applicable``, as reported by ``GET /fixes``,
  and together they equal the total number of fixes persisted.

The test is network-free: a :class:`FakeCrawler` returns the generated pages, a
fresh in-memory SQLite :class:`~digital_twin.repository.DigitalTwinRepository`
backs each example, and the real Check_Engine and Fix_Generator run the
detection/fix logic. The pages are generated with a varied mix of triggering
conditions (missing title/meta, thin content, missing schema, redirect chains,
missing alt text with and without a resolvable media id, and broken links) so
different issue types and both auto-applicable and report-only fixes arise.

The invariant asserted is *consistency*: whatever the Check_Engine and
Fix_Generator produce, the summary must agree with what the Digital_Twin
persisted and the read endpoints report.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

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

from core.results import NotFound
from core.types import CrawledPage, ImageRef, LinkStatus, RedirectChain

from api import create_app

TENANT = "tenant-a"

#: A fixed crawl timestamp; passing this same instant as ``now`` to
#: ``get_page`` keeps every persisted page fresh (age 0) when we verify it.
NOW = datetime(2024, 1, 1, tzinfo=timezone.utc)


# --- Fakes --------------------------------------------------------------------


class FakeCrawler:
    """A CrawlerPort fake returning the generated pages verbatim."""

    def __init__(self, pages: list[CrawledPage]) -> None:
        self._pages = pages

    def crawl_site(self, start_url: str, max_pages: int) -> list[CrawledPage]:
        return list(self._pages)

    def check_link_status(self, url: str):  # pragma: no cover - unused here
        raise NotImplementedError


class FakePublishingAdapter:
    """Minimal PublishingAdapterPort so the Governance_Layer can be built.

    ``POST /crawl`` never writes to the live site, so these are never invoked.
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


def _build_app(pages: list[CrawledPage]):
    """Build an app wired to a fresh in-memory repo and a FakeCrawler."""
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
        crawler=FakeCrawler(pages),
        digital_twin=repo,
        check_engine=CheckEngine(),
        fix_generator=FixGenerator(),
        governance=governance,
        tenant_id=TENANT,
    )
    return app, repo


# --- Strategies ---------------------------------------------------------------

# A small readable alphabet keeps titles/filenames legible without changing the
# logic under test.
_TEXT = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz ABCDEFGHIJKLMNOPQRSTUVWXYZ-_.0123456789",
    min_size=0,
    max_size=20,
)

# Titles chosen from a tiny pool so duplicates occasionally arise (exercising the
# cross-page duplicate-title check), alongside blank/None titles.
_titles = st.one_of(
    st.none(),
    st.just(""),
    st.sampled_from(["Home", "About", "Contact", "Home", "Products"]),
)

_meta = st.one_of(st.none(), st.just(""), _TEXT.filter(lambda s: s.strip() != ""))

# Word counts straddle the thin-content threshold (300 words).
_word_counts = st.integers(min_value=0, max_value=600)

# Alt text is present, blank, or absent so both missing-alt and complete images
# are generated.
_alt_text = st.one_of(st.none(), st.just(""), _TEXT.filter(lambda s: s.strip() != ""))

# A media id may be resolvable (an int) or unknown (None). A resolvable id on an
# image missing alt text is what makes the alt-text fix auto-applicable.
_media_ids = st.one_of(st.none(), st.integers(min_value=1, max_value=9999))


@st.composite
def _images(draw) -> list[ImageRef]:
    count = draw(st.integers(min_value=0, max_value=3))
    return [
        ImageRef(
            media_id=draw(_media_ids),
            filename=draw(_TEXT),
            alt_text=draw(_alt_text),
        )
        for _ in range(count)
    ]


# Link status codes span healthy (2xx/3xx) and broken (4xx/5xx) ranges.
_status_codes = st.one_of(
    st.sampled_from([200, 301, 302]),
    st.sampled_from([400, 404, 410, 500, 503]),
)


@st.composite
def _links(draw) -> list[LinkStatus]:
    count = draw(st.integers(min_value=0, max_value=3))
    links = []
    for i in range(count):
        status = draw(_status_codes)
        links.append(
            LinkStatus(
                url=f"https://example.com/link-{i}",
                status_code=status,
                reachable=status < 400,
            )
        )
    return links


@st.composite
def _redirect_chain(draw) -> RedirectChain:
    # Chains of length 0..5 straddle the redirect-chain threshold (3 hops).
    hop_count = draw(st.integers(min_value=0, max_value=5))
    hops = [f"https://example.com/hop-{i}" for i in range(hop_count)]
    return RedirectChain(hops=hops, truncated=False)


@st.composite
def _crawled_pages(draw) -> list[CrawledPage]:
    """Generate a list of pages with unique URLs and a varied issue mix."""
    count = draw(st.integers(min_value=0, max_value=5))
    pages: list[CrawledPage] = []
    for i in range(count):
        pages.append(
            CrawledPage(
                # Unique URL per page so upsert persists one row each and the
                # crawled count equals the persisted-page count.
                url=f"https://example.com/page-{i}",
                final_url=f"https://example.com/page-{i}",
                status_code=200,
                title=draw(_titles),
                meta_description=draw(_meta),
                word_count=draw(_word_counts),
                has_schema=draw(st.booleans()),
                images=draw(_images()),
                links=draw(_links()),
                redirect_chain=draw(_redirect_chain()),
                crawled_at=NOW,
            )
        )
    return pages


# --- Property 45 --------------------------------------------------------------


@settings(max_examples=100)
@given(pages=_crawled_pages())
def test_property_45_crawl_summary_counts_match_persisted_data(
    pages: list[CrawledPage],
) -> None:
    """The ``POST /crawl`` summary agrees with the persisted data (Req 10.1).

    Feature: website-orchestrator-milestone-0, Property 45: Crawl summary counts
    match persisted data
    """
    app, repo = _build_app(pages)
    client = TestClient(app)

    response = client.post(
        "/crawl", json={"start_url": "https://example.com/", "max_pages": 50}
    )
    assert response.status_code == 200
    summary = response.json()

    # --- pages_crawled matches the crawl and the persisted page rows ----------
    assert summary["pages_crawled"] == len(pages)
    # Every generated page (unique URL) was actually persisted.
    for page in pages:
        result = repo.get_page(TENANT, page.url, NOW)
        assert not isinstance(result, NotFound)

    # --- issues_by_type matches the persisted issues (GET /issues) ------------
    issues_response = client.get("/issues")
    assert issues_response.status_code == 200
    persisted_issues = issues_response.json()

    expected_by_type = Counter(issue["issue_type"] for issue in persisted_issues)
    # Summary keys are the IssueType enum values serialized as strings.
    assert summary["issues_by_type"] == dict(expected_by_type)
    # The per-type counts also sum to the total number of persisted issues.
    assert sum(summary["issues_by_type"].values()) == len(persisted_issues)

    # --- fix counts match the persisted fixes (GET /fixes) --------------------
    fixes_response = client.get("/fixes")
    assert fixes_response.status_code == 200
    persisted_fixes = fixes_response.json()

    expected_auto = sum(1 for f in persisted_fixes if f["auto_applicable"] == 1)
    expected_report = sum(1 for f in persisted_fixes if f["auto_applicable"] == 0)

    assert summary["auto_applicable_count"] == expected_auto
    assert summary["report_only_count"] == expected_report
    # Auto-applicable + report-only accounts for exactly every persisted fix.
    assert (
        summary["auto_applicable_count"] + summary["report_only_count"]
        == len(persisted_fixes)
    )
