"""Sanity tests for the end-to-end harness (task 15.1).

These verify the building blocks the Requirement 11 end-to-end proof (task 15.2)
depends on, without yet driving the full API loop:

* the Fixture_Site + in-memory Crawler seams crawl locally and the Check_Engine
  detects **at least one Issue of each seeded type** — missing title, missing
  meta description, missing alt text, broken link, redirect chain (Req 11.3);
* the harness resolves **exactly one** auto-applicable missing-alt-text image, so
  the Fix_Generator produces **exactly one** Auto_Applicable_Fix (Req 11.4);
* the :class:`~e2e.mock_wordpress.MockWordPressClient` records reads and writes
  and reads back written values (Req 11.2, 11.6), standing in for the live
  Publishing_Adapter target;
* a fix's ``target_ref`` survives a Digital_Twin persist/reload round-trip — the
  gap fixed so the Governance_Layer can locate the live target end-to-end
  (Req 5.3, 11.5-11.8).

Everything runs against local fixtures and an in-memory SQLite datastore, so no
request leaves localhost and no real credential is used (Req 11.1, 11.2).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from check_engine.checks import CheckEngine
from core.types import (
    CrawledPage,
    FixStatus,
    FixType,
    Issue,
    IssueCandidate,
    SuggestedFix,
    TargetRef,
)
from digital_twin.models import Base
from digital_twin.repository import DigitalTwinRepository
from fix_generator.generator import FixGenerator

from e2e.fetcher import InMemoryFetcher
from e2e.fixtures import (
    BASE_URL,
    BROKEN_LINK_URL,
    RESOLVABLE_IMAGE_FILENAME,
    RESOLVABLE_MEDIA_ID,
    SEEDED_ISSUE_TYPES,
    build_fixture_site,
    crawl_fixture,
    make_mock_wordpress,
)

TENANT = "tenant-e2e"


def _issue_from(candidate: IssueCandidate, index: int) -> Issue:
    """Promote an :class:`IssueCandidate` to a persisted-shape :class:`Issue`."""
    return Issue(
        id=f"issue-{index}",
        tenant_id=TENANT,
        ignored=False,
        issue_type=candidate.issue_type,
        severity=candidate.severity,
        description=candidate.description,
        detail=candidate.detail,
    )


def _generate_all_fixes(
    candidates: list[IssueCandidate], pages: list[CrawledPage]
) -> list[SuggestedFix]:
    """Run the Fix_Generator over every detected issue against its page."""
    page_by_url = {page.url: page for page in pages}
    generator = FixGenerator()
    fixes: list[SuggestedFix] = []
    for index, candidate in enumerate(candidates):
        issue = _issue_from(candidate, index)
        page = page_by_url.get(candidate.detail.page_url, pages[0])
        fix = generator.generate_fix(issue, page)
        if fix is not None:
            fixes.append(fix)
    return fixes


# --- Crawl + detection (Req 11.1, 11.3) --------------------------------------


def test_fixture_crawl_stays_local_and_detects_each_seeded_issue_type() -> None:
    pages, crawler, site = crawl_fixture()

    # Req 11.1 — every retrieval and probe targeted a fixture URL; nothing left
    # the local fixture set (all requests are under BASE_URL, the broken link is
    # the only off-domain URL and it is probed, never fetched).
    fetcher = crawler._fetcher  # type: ignore[attr-defined]
    assert isinstance(fetcher, InMemoryFetcher)
    assert fetcher.requests, "the crawl should have fetched fixture pages"
    assert all(url.startswith(BASE_URL) for url in fetcher.requests)

    detected = {c.issue_type for c in CheckEngine().run_all_checks(pages)}
    missing = SEEDED_ISSUE_TYPES - detected
    assert not missing, f"seeded issue types not detected: {sorted(t.value for t in missing)}"


def test_broken_link_is_probed_offdomain_and_flagged() -> None:
    pages, crawler, _site = crawl_fixture()
    prober = crawler._link_prober  # type: ignore[attr-defined]
    assert BROKEN_LINK_URL in prober.probes  # type: ignore[attr-defined]

    broken = [
        c
        for c in CheckEngine().run_all_checks(pages)
        if c.issue_type.value == "broken_links"
    ]
    assert broken and BROKEN_LINK_URL in broken[0].detail.element


# --- Exactly one Auto_Applicable_Fix (Req 11.4) ------------------------------


def test_exactly_one_resolvable_auto_applicable_alt_text_fix() -> None:
    pages, _crawler, _site = crawl_fixture()

    # Exactly one image on the whole site is resolvable to a media id.
    resolved = [
        img for page in pages for img in page.images if img.media_id is not None
    ]
    assert len(resolved) == 1
    assert resolved[0].filename == RESOLVABLE_IMAGE_FILENAME
    assert resolved[0].media_id == RESOLVABLE_MEDIA_ID

    candidates = CheckEngine().run_all_checks(pages)
    fixes = _generate_all_fixes(candidates, pages)

    auto = [f for f in fixes if f.auto_applicable == 1]
    assert len(auto) == 1, "exactly one Auto_Applicable_Fix must be produced"
    fix = auto[0]
    assert fix.fix_type is FixType.UPDATE_ALT_TEXT
    assert fix.target_ref is not None
    assert fix.target_ref.media_id == RESOLVABLE_MEDIA_ID
    assert fix.proposed_value  # non-empty heuristic alt text

    # Every other produced fix is report-only.
    assert all(f.auto_applicable == 0 for f in fixes if f is not fix)


# --- Mocked WordPress client spy (Req 11.2, 11.6) ----------------------------


def test_mock_wordpress_client_records_reads_and_writes() -> None:
    site = build_fixture_site()
    wp = make_mock_wordpress(site)

    before = wp.get_media(RESOLVABLE_MEDIA_ID)
    assert before.alt_text == ""  # seeded with missing alt text
    assert wp.read_count == 1 and wp.write_count == 0

    updated = wp.update_media_alt_text(RESOLVABLE_MEDIA_ID, "Hero banner")
    assert updated.alt_text == "Hero banner"
    assert wp.write_count == 1
    assert wp.writes[0].op == "update_media_alt_text"
    assert wp.writes[0].target_id == RESOLVABLE_MEDIA_ID
    assert wp.writes[0].value == "Hero banner"

    # Reading back returns the written value (Req 11.6).
    assert wp.get_media(RESOLVABLE_MEDIA_ID).alt_text == "Hero banner"


def test_mock_wordpress_unknown_target_raises_typed_not_found() -> None:
    from core.exceptions import WPNotFoundError

    wp = make_mock_wordpress(build_fixture_site())
    with pytest.raises(WPNotFoundError):
        wp.get_media(9999)
    with pytest.raises(WPNotFoundError):
        wp.get_page(9999)


# --- target_ref persistence gap (Req 5.3, 11.5-11.8) -------------------------


def test_suggested_fix_target_ref_survives_persist_reload() -> None:
    """The Digital_Twin must persist and reconstruct a fix's target_ref so the
    Governance_Layer can locate its live target after a reload (the gap fixed as
    part of this task)."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    repo = DigitalTwinRepository(
        sessionmaker(bind=engine, expire_on_commit=False), tenant_id=TENANT
    )

    # A page + issue must exist for the fix's FK to resolve.
    page = CrawledPage(
        url=f"{BASE_URL}/gallery",
        final_url=f"{BASE_URL}/gallery",
        status_code=200,
        title="Gallery",
        crawled_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    repo.upsert_pages(TENANT, [page])
    issue = repo.persist_issues(
        TENANT,
        [
            IssueCandidate(
                issue_type=next(iter(SEEDED_ISSUE_TYPES)),  # any seeded type
                severity="low",
                description="seeded",
                detail={"page_url": f"{BASE_URL}/gallery"},
            )
        ],
    )[0]

    fix = SuggestedFix(
        id="fix-auto",
        tenant_id=TENANT,
        issue_id=issue.id,
        fix_type=FixType.UPDATE_ALT_TEXT,
        auto_applicable=1,
        target_ref=TargetRef(media_id=RESOLVABLE_MEDIA_ID),
        proposed_value="Hero banner",
        status=FixStatus.PENDING,
    )
    repo.persist_fixes(TENANT, [fix])

    reloaded = repo.get_fix(TENANT, "fix-auto")
    assert reloaded is not None
    assert reloaded.target_ref is not None
    assert reloaded.target_ref.media_id == RESOLVABLE_MEDIA_ID
    assert reloaded.target_ref.page_id is None
    assert reloaded.proposed_value == "Hero banner"
