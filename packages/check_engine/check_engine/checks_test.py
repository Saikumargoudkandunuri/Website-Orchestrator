"""Unit tests for the Check_Engine page-level checks (task 7.1).

Verify that each check emits a well-formed :class:`IssueCandidate` on a
triggering input (Req 4.8) and returns ``None``/``[]`` otherwise, using
deterministic, rule-based logic (Req 4.1).
"""

from __future__ import annotations

from datetime import datetime, timezone

from core.constants import REDIRECT_CHAIN_THRESHOLD, THIN_CONTENT_MIN_WORDS
from core.interfaces import CheckEnginePort
from core.types import (
    CrawledPage,
    ImageRef,
    IssueCandidate,
    IssueType,
    LinkStatus,
    RedirectChain,
    Severity,
)

from check_engine import CheckEngine

_VALID_SEVERITIES = {
    Severity.CRITICAL,
    Severity.HIGH,
    Severity.MEDIUM,
    Severity.LOW,
}


def _page(**overrides: object) -> CrawledPage:
    """Build a fully-healthy page; override fields to trigger a single check."""

    defaults: dict[str, object] = {
        "url": "https://example.com/page",
        "final_url": "https://example.com/page",
        "status_code": 200,
        "title": "A perfectly good title",
        "meta_description": "A perfectly good meta description.",
        "word_count": THIN_CONTENT_MIN_WORDS,
        "html": "<html></html>",
        "links": [],
        "images": [],
        "redirect_chain": RedirectChain(hops=[], truncated=False),
        "has_schema": True,
        "crawled_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    return CrawledPage(**defaults)


def _assert_well_formed(candidate: IssueCandidate, expected_type: IssueType) -> None:
    assert candidate.issue_type is expected_type
    assert candidate.severity in _VALID_SEVERITIES
    assert candidate.description.strip() != ""
    assert candidate.detail.page_url == "https://example.com/page"
    assert candidate.detail.element is not None
    assert candidate.detail.element.strip() != ""


# --- check_missing_title ------------------------------------------------------


def test_missing_title_flags_none_and_empty() -> None:
    engine = CheckEngine()
    for bad in (None, "", "   "):
        result = engine.check_missing_title(_page(title=bad))
        assert result is not None
        _assert_well_formed(result, IssueType.MISSING_TITLE)


def test_missing_title_passes_when_present() -> None:
    assert CheckEngine().check_missing_title(_page(title="Home")) is None


# --- check_missing_meta_description ------------------------------------------


def test_missing_meta_description_flags_blank() -> None:
    engine = CheckEngine()
    result = engine.check_missing_meta_description(_page(meta_description=None))
    assert result is not None
    _assert_well_formed(result, IssueType.MISSING_META_DESCRIPTION)


def test_missing_meta_description_passes_when_present() -> None:
    assert (
        CheckEngine().check_missing_meta_description(
            _page(meta_description="desc")
        )
        is None
    )


# --- check_thin_content -------------------------------------------------------


def test_thin_content_flags_below_threshold() -> None:
    engine = CheckEngine()
    result = engine.check_thin_content(
        _page(word_count=THIN_CONTENT_MIN_WORDS - 1)
    )
    assert result is not None
    _assert_well_formed(result, IssueType.THIN_CONTENT)


def test_thin_content_passes_at_threshold() -> None:
    engine = CheckEngine()
    assert engine.check_thin_content(_page(word_count=THIN_CONTENT_MIN_WORDS)) is None
    assert (
        engine.check_thin_content(_page(word_count=THIN_CONTENT_MIN_WORDS + 50))
        is None
    )


# --- check_redirect_chains ----------------------------------------------------


def test_redirect_chains_flags_at_threshold() -> None:
    engine = CheckEngine()
    hops = [f"https://example.com/{i}" for i in range(REDIRECT_CHAIN_THRESHOLD)]
    result = engine.check_redirect_chains(
        _page(redirect_chain=RedirectChain(hops=hops))
    )
    assert result is not None
    _assert_well_formed(result, IssueType.REDIRECT_CHAINS)


def test_redirect_chains_passes_below_threshold() -> None:
    engine = CheckEngine()
    hops = [f"https://example.com/{i}" for i in range(REDIRECT_CHAIN_THRESHOLD - 1)]
    assert (
        engine.check_redirect_chains(_page(redirect_chain=RedirectChain(hops=hops)))
        is None
    )


# --- check_missing_schema -----------------------------------------------------


def test_missing_schema_flags_when_absent() -> None:
    engine = CheckEngine()
    result = engine.check_missing_schema(_page(has_schema=False))
    assert result is not None
    _assert_well_formed(result, IssueType.MISSING_SCHEMA)


def test_missing_schema_passes_when_present() -> None:
    assert CheckEngine().check_missing_schema(_page(has_schema=True)) is None


# --- check_missing_alt_text ---------------------------------------------------


def test_missing_alt_text_flags_one_per_image_lacking_alt() -> None:
    engine = CheckEngine()
    images = [
        ImageRef(media_id=1, filename="a.png", alt_text=None),
        ImageRef(media_id=2, filename="b.png", alt_text="   "),
        ImageRef(media_id=3, filename="c.png", alt_text="described"),
    ]
    results = engine.check_missing_alt_text(_page(images=images))
    assert len(results) == 2
    for candidate in results:
        _assert_well_formed(candidate, IssueType.MISSING_ALT_TEXT)


def test_missing_alt_text_empty_when_all_present() -> None:
    engine = CheckEngine()
    images = [ImageRef(media_id=1, filename="a.png", alt_text="ok")]
    assert engine.check_missing_alt_text(_page(images=images)) == []
    assert engine.check_missing_alt_text(_page(images=[])) == []


# --- check_broken_links -------------------------------------------------------


def test_broken_links_flags_client_and_server_errors() -> None:
    engine = CheckEngine()
    links = [
        LinkStatus(url="https://example.com/ok", status_code=200, reachable=True),
        LinkStatus(url="https://example.com/404", status_code=404, reachable=True),
        LinkStatus(url="https://example.com/500", status_code=500, reachable=True),
        LinkStatus(url="https://example.com/dead", status_code=None, reachable=False),
    ]
    results = engine.check_broken_links(_page(links=links))
    assert len(results) == 2
    for candidate in results:
        _assert_well_formed(candidate, IssueType.BROKEN_LINKS)


def test_broken_links_empty_when_all_ok() -> None:
    engine = CheckEngine()
    links = [
        LinkStatus(url="https://example.com/ok", status_code=200, reachable=True),
        LinkStatus(url="https://example.com/redir", status_code=301, reachable=True),
    ]
    assert engine.check_broken_links(_page(links=links)) == []


# --- determinism --------------------------------------------------------------


def test_checks_are_deterministic() -> None:
    engine = CheckEngine()
    page = _page(title=None, word_count=10, has_schema=False)
    first = engine.check_missing_title(page)
    second = engine.check_missing_title(page)
    assert first == second


# --- check_duplicate_titles ---------------------------------------------------


def test_duplicate_titles_flags_each_page_sharing_a_title() -> None:
    engine = CheckEngine()
    pages = [
        _page(url="https://example.com/a", title="Shared Title"),
        _page(url="https://example.com/b", title="Shared Title"),
        _page(url="https://example.com/c", title="Unique Title"),
    ]
    results = engine.check_duplicate_titles(pages)

    assert len(results) == 2
    flagged_urls = {c.detail.page_url for c in results}
    assert flagged_urls == {"https://example.com/a", "https://example.com/b"}
    for candidate in results:
        assert candidate.issue_type is IssueType.DUPLICATE_TITLE
        assert candidate.severity in _VALID_SEVERITIES
        assert candidate.description.strip() != ""
        assert candidate.detail.element is not None
        assert "Shared Title" in candidate.detail.element


def test_duplicate_titles_empty_when_all_unique() -> None:
    engine = CheckEngine()
    pages = [
        _page(url="https://example.com/a", title="Title A"),
        _page(url="https://example.com/b", title="Title B"),
    ]
    assert engine.check_duplicate_titles(pages) == []


def test_duplicate_titles_ignores_blank_and_none_titles() -> None:
    engine = CheckEngine()
    pages = [
        _page(url="https://example.com/a", title=None),
        _page(url="https://example.com/b", title="   "),
        _page(url="https://example.com/c", title=""),
    ]
    assert engine.check_duplicate_titles(pages) == []


def test_duplicate_titles_handles_multiple_groups() -> None:
    engine = CheckEngine()
    pages = [
        _page(url="https://example.com/a", title="Group One"),
        _page(url="https://example.com/b", title="Group Two"),
        _page(url="https://example.com/c", title="Group One"),
        _page(url="https://example.com/d", title="Group Two"),
        _page(url="https://example.com/e", title="Alone"),
    ]
    results = engine.check_duplicate_titles(pages)
    assert len(results) == 4
    flagged_urls = [c.detail.page_url for c in results]
    # Deterministic: preserves input page order.
    assert flagged_urls == [
        "https://example.com/a",
        "https://example.com/b",
        "https://example.com/c",
        "https://example.com/d",
    ]


# --- run_all_checks -----------------------------------------------------------


def test_run_all_checks_aggregates_every_check_type() -> None:
    engine = CheckEngine()
    # Page 1 triggers all page-level checks at once.
    broken = LinkStatus(
        url="https://example.com/404", status_code=404, reachable=True
    )
    no_alt = ImageRef(media_id=1, filename="a.png", alt_text=None)
    hops = [f"https://example.com/{i}" for i in range(REDIRECT_CHAIN_THRESHOLD)]
    page1 = _page(
        url="https://example.com/dup",
        title="Dup Title",
        meta_description=None,
        word_count=THIN_CONTENT_MIN_WORDS - 1,
        has_schema=False,
        links=[broken],
        images=[no_alt],
        redirect_chain=RedirectChain(hops=hops),
    )
    # Page 2 shares the title to trigger the cross-page duplicate check.
    page2 = _page(url="https://example.com/dup2", title="Dup Title")

    results = engine.run_all_checks([page1, page2])
    found_types = {c.issue_type for c in results}

    expected_types = {
        IssueType.MISSING_META_DESCRIPTION,
        IssueType.THIN_CONTENT,
        IssueType.REDIRECT_CHAINS,
        IssueType.MISSING_SCHEMA,
        IssueType.MISSING_ALT_TEXT,
        IssueType.BROKEN_LINKS,
        IssueType.DUPLICATE_TITLE,
    }
    assert expected_types <= found_types


def test_run_all_checks_is_deterministic() -> None:
    engine = CheckEngine()
    pages = [
        _page(url="https://example.com/a", title="Same", has_schema=False),
        _page(url="https://example.com/b", title="Same", word_count=1),
    ]
    assert engine.run_all_checks(pages) == engine.run_all_checks(pages)


def test_run_all_checks_empty_for_healthy_pages() -> None:
    engine = CheckEngine()
    pages = [
        _page(url="https://example.com/a", title="Unique A"),
        _page(url="https://example.com/b", title="Unique B"),
    ]
    assert engine.run_all_checks(pages) == []


# --- Port conformance ---------------------------------------------------------


def test_check_engine_satisfies_port() -> None:
    assert isinstance(CheckEngine(), CheckEnginePort)
