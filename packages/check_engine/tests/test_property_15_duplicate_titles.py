"""Property 15 — Duplicate-title detection matches repeated titles.

Feature: website-orchestrator-milestone-0, Property 15: Duplicate-title detection
matches repeated titles

Validates: Requirements 4.4

Requirement 4.4: WHEN two or more pages have identical title text, THE Check_Engine
SHALL emit a duplicate-title IssueCandidate.

This property drives :meth:`check_engine.CheckEngine.check_duplicate_titles` with an
arbitrary list of :class:`~core.types.CrawledPage` records and asserts that the set of
page URLs it flags equals *exactly* the set of pages whose non-blank title is shared
by two or more pages.

The expected set is computed independently in the test: pages are grouped by their
exact (non-blank) title text, and every title held by two or more pages contributes
all of its pages to the expected flagged set. Blank (``""``/whitespace-only) and
``None`` titles are never duplicates.

Titles are drawn from a deliberately small pool (plus blanks and ``None``) so that
duplicates are forced frequently, exercising unique-title runs (no candidates),
multiple independent duplicate groups, and pages whose blank/``None`` titles must
never be flagged. Each generated page is given a distinct URL so the flagged-URL set
uniquely identifies the flagged pages.
"""

from __future__ import annotations

from datetime import datetime, timezone

from hypothesis import example, given, settings
from hypothesis import strategies as st

from check_engine import CheckEngine
from core.types import CrawledPage, IssueType, Severity

# --- Strategies ---------------------------------------------------------------

# A small pool of concrete, non-blank titles so duplicates are forced often, mixed
# with blank ("" / whitespace-only) and None titles that must never be flagged.
_TITLE_POOL: list[str | None] = [
    "Home",
    "About",
    "Contact",
    "Blog",  # non-blank titles that will repeat across pages
    "",  # blank: never a duplicate
    "   ",  # whitespace-only: blank, never a duplicate
    None,  # missing: never a duplicate
]

_titles = st.sampled_from(_TITLE_POOL)

# Lists of titles; the index of each entry is used to mint a distinct URL, so the
# flagged-URL set is an injective image of the flagged pages.
_title_lists = st.lists(_titles, min_size=0, max_size=12)


def _is_blank(value: str | None) -> bool:
    """Blank means None or whitespace-only (mirrors the Check_Engine rule)."""

    return value is None or value.strip() == ""


def _pages_from_titles(titles: list[str | None]) -> list[CrawledPage]:
    """Build pages with distinct URLs, one per title in ``titles``."""

    return [
        CrawledPage(
            url=f"https://example.com/page-{index}",
            final_url=f"https://example.com/page-{index}",
            status_code=200,
            title=title,
            crawled_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        for index, title in enumerate(titles)
    ]


def _expected_flagged_urls(pages: list[CrawledPage]) -> set[str]:
    """Independently compute the URLs that SHOULD be flagged as duplicates.

    Group pages by exact non-blank title; any title shared by two or more pages
    contributes all of its pages to the expected set. Blank/None titles never count.
    """

    groups: dict[str, list[str]] = {}
    for page in pages:
        if _is_blank(page.title):
            continue
        title = page.title or ""
        groups.setdefault(title, []).append(page.url)

    expected: set[str] = set()
    for urls in groups.values():
        if len(urls) >= 2:
            expected.update(urls)
    return expected


# --- Property -----------------------------------------------------------------


@settings(max_examples=200)
@given(titles=_title_lists)
# Unique titles → no candidates.
@example(titles=["Home", "About", "Contact"])
# Multiple independent duplicate groups.
@example(titles=["Home", "About", "Home", "About", "Contact"])
# Only blanks / None → never flagged.
@example(titles=["", "   ", None, "", None])
# Blanks mixed with a real duplicate group; blanks stay unflagged.
@example(titles=["", None, "Blog", "Blog", "   "])
def test_property_15_duplicate_title_detection_matches_repeated_titles(
    titles: list[str | None],
) -> None:
    """The URLs flagged by ``check_duplicate_titles`` equal exactly the pages whose
    non-blank title is shared by two or more pages, and every emitted candidate is a
    well-formed DUPLICATE_TITLE candidate.

    Feature: website-orchestrator-milestone-0, Property 15: Duplicate-title detection
    matches repeated titles

    Validates: Requirements 4.4
    """
    pages = _pages_from_titles(titles)
    candidates = CheckEngine().check_duplicate_titles(pages)

    flagged_urls = [candidate.detail.page_url for candidate in candidates]

    # Exactly one candidate per flagged page (no duplicates in the output), and the
    # flagged-URL set matches the independently computed expectation.
    assert len(flagged_urls) == len(set(flagged_urls))
    assert set(flagged_urls) == _expected_flagged_urls(pages)

    # Every emitted candidate is a well-formed DUPLICATE_TITLE candidate.
    valid_severities = set(Severity)
    for candidate in candidates:
        assert candidate.issue_type == IssueType.DUPLICATE_TITLE
        assert candidate.severity in valid_severities
        assert isinstance(candidate.description, str)
        assert candidate.description.strip() != ""
        assert candidate.detail.page_url != ""

    # No blank/None-titled page is ever flagged.
    blank_urls = {page.url for page in pages if _is_blank(page.title)}
    assert blank_urls.isdisjoint(set(flagged_urls))
