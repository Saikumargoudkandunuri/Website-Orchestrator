"""Milestone 5 — Automatic Page Refresh (item 5): Content Refresh Engine.

Covers thin/duplicate-title/duplicate-heading/outdated (pre-existing) plus the
real bug fix in this change: ``missing_faq`` detection was documented in the
module docstring but never implemented — the loop over pages never ran.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.types import CrawledPage, HeadingRef
from engines.content_refresh.service import ContentRefreshService

NOW = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _page(url: str, *, word_count: int = 500, title: str = "Title", headings: list | None = None,
          crawled_at: datetime = NOW) -> CrawledPage:
    return CrawledPage(
        url=url, final_url=url, status_code=200, title=title, word_count=word_count,
        headings=headings or [], crawled_at=crawled_at,
    )


def test_missing_faq_detected_on_faq_intent_page_with_no_question_headings() -> None:
    page = _page(
        "https://example.com/faq",
        headings=[HeadingRef(level=1, text="Frequently Asked Questions")],
    )
    report = ContentRefreshService().analyze("site-1", [page], now=NOW)
    faq_findings = [f for f in report.findings if f.finding_type == "missing_faq"]
    assert len(faq_findings) == 1
    assert faq_findings[0].page_url == page.url
    faq_proposals = [p for p in report.proposals if p.finding_type == "missing_faq"]
    assert len(faq_proposals) == 1


def test_missing_faq_not_flagged_when_questions_already_present() -> None:
    page = _page(
        "https://example.com/faq",
        headings=[
            HeadingRef(level=1, text="Frequently Asked Questions"),
            HeadingRef(level=2, text="What is SEO?"),
            HeadingRef(level=2, text="How does crawling work?"),
        ],
    )
    report = ContentRefreshService().analyze("site-1", [page], now=NOW)
    assert not any(f.finding_type == "missing_faq" for f in report.findings)


def test_missing_faq_not_flagged_on_page_with_no_faq_intent() -> None:
    page = _page("https://example.com/about", headings=[HeadingRef(level=1, text="About Us")])
    report = ContentRefreshService().analyze("site-1", [page], now=NOW)
    assert not any(f.finding_type == "missing_faq" for f in report.findings)


def test_how_to_guide_page_without_questions_flagged_missing_faq() -> None:
    page = _page(
        "https://example.com/guide",
        headings=[HeadingRef(level=1, text="How to Fix Broken Links")],
    )
    report = ContentRefreshService().analyze("site-1", [page], now=NOW)
    assert any(f.finding_type == "missing_faq" for f in report.findings)


def test_thin_content_and_duplicate_title_still_detected() -> None:
    pages = [
        _page("https://example.com/a", word_count=50, title="Same Title"),
        _page("https://example.com/b", word_count=500, title="Same Title"),
    ]
    report = ContentRefreshService().analyze("site-1", pages, now=NOW)
    types = {f.finding_type for f in report.findings}
    assert "thin_content" in types
    assert "duplicate_title" in types


def test_outdated_detected_for_stale_pages() -> None:
    old_page = _page("https://example.com/old", crawled_at=NOW - timedelta(days=400))
    report = ContentRefreshService().analyze("site-1", [old_page], now=NOW)
    assert any(f.finding_type == "outdated" for f in report.findings)


def test_no_pages_returns_honest_empty_report() -> None:
    report = ContentRefreshService().analyze("site-1", [], now=NOW)
    assert report.findings == []
    assert report.provenance == "no_data"
