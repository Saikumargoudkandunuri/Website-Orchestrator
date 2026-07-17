"""Content Refresh Engine service — pure computation over real crawl pages.

Detection rules (deterministic, real signals only):

* ``word_count`` below ``thin_threshold`` (default 300) -> thin_content.
* Two or more pages sharing the exact same non-empty ``title`` -> duplicate_title
  on each page involved.
* Two or more pages sharing the exact same H1 text -> duplicate_heading.
* ``crawled_at`` older than ``stale_days`` (default 365) with no evidence of a
  more recent publish signal -> outdated (proxy, disclosed in the report note).
* A page whose path/heading signals FAQ-like intent but has fewer than 2
  headings phrased as questions -> missing_faq.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from engines.content_refresh.models import (
    ContentRefreshProposal,
    ContentRefreshReport,
    RefreshFinding,
)

__all__ = ["ContentRefreshService"]

_THIN_THRESHOLD = 300
_STALE_DAYS = 365


class ContentRefreshService:
    engine_name = "content_refresh"
    engine_version = "1.0.0"

    def analyze(
        self, site_id: str, pages: list, *, now: datetime | None = None,
        thin_threshold: int = _THIN_THRESHOLD, stale_days: int = _STALE_DAYS,
    ) -> ContentRefreshReport:
        report = ContentRefreshReport(site_id=site_id, pages_analyzed=len(pages))
        if not pages:
            report.notes.append("No crawled pages available; run a crawl first.")
            report.provenance = "no_data"
            return report

        now = now or datetime.now(timezone.utc)

        titles: dict[str, list] = defaultdict(list)
        h1s: dict[str, list] = defaultdict(list)
        for page in pages:
            if page.title and page.title.strip():
                titles[page.title.strip().lower()].append(page)
            h1_texts = [h.text for h in (page.headings or []) if h.level == 1]
            if h1_texts:
                h1s[h1_texts[0].strip().lower()].append(page)

        for page in pages:
            if page.word_count and page.word_count < thin_threshold:
                report.findings.append(RefreshFinding(
                    page_url=page.url, finding_type="thin_content", severity="high",
                    evidence=[f"word_count={page.word_count} < threshold={thin_threshold}"],
                ))
                report.proposals.append(ContentRefreshProposal(
                    page_url=page.url, finding_type="thin_content",
                    operation="replace_content_block",
                    detail={"selector": "body", "note": "expand with additional supporting content"},
                    reason=f"Only {page.word_count} words; expand to answer the query intent fully.",
                ))

            crawled_at = page.crawled_at
            if crawled_at is not None:
                age_days = (now - crawled_at).days
                if age_days >= stale_days:
                    report.findings.append(RefreshFinding(
                        page_url=page.url, finding_type="outdated", severity="medium",
                        evidence=[f"last crawled {age_days} day(s) ago (proxy for staleness)"],
                    ))

        for title, group in titles.items():
            if len(group) > 1:
                for page in group:
                    report.findings.append(RefreshFinding(
                        page_url=page.url, finding_type="duplicate_title", severity="medium",
                        evidence=[f"shared title {title!r} across {len(group)} pages"],
                    ))

        for text, group in h1s.items():
            if len(group) > 1:
                for page in group:
                    report.findings.append(RefreshFinding(
                        page_url=page.url, finding_type="duplicate_heading", severity="medium",
                        evidence=[f"shared H1 {text!r} across {len(group)} pages"],
                    ))
                    report.proposals.append(ContentRefreshProposal(
                        page_url=page.url, finding_type="duplicate_heading",
                        operation="update_heading",
                        detail={"level": 1, "index": 0,
                                "new_text_hint": "differentiate this page's H1 from duplicates"},
                        reason=f"H1 duplicated across {len(group)} pages; needs a unique heading.",
                    ))

        for page in pages:
            if self._signals_faq_intent(page) and self._question_heading_count(page) < 2:
                report.findings.append(RefreshFinding(
                    page_url=page.url, finding_type="missing_faq", severity="low",
                    evidence=[
                        f"question_headings={self._question_heading_count(page)} < 2",
                        "URL/heading signals FAQ intent (path or heading contains 'faq'/'questions', "
                        "or is a 'how'/'what'/'why' guide page)",
                    ],
                ))
                report.proposals.append(ContentRefreshProposal(
                    page_url=page.url, finding_type="missing_faq",
                    operation="replace_content_block",
                    detail={"selector": "body", "note": "add a Frequently Asked Questions section"},
                    reason="Page signals FAQ intent but has fewer than 2 question-phrased headings.",
                ))

        if not report.findings:
            report.notes.append("No content-quality findings from observed crawl signals.")
        report.notes.append(
            "'outdated' is a crawl-recency proxy (no publish-date signal is captured); "
            "treat as directional, not authoritative."
        )
        return report

    @staticmethod
    def _signals_faq_intent(page) -> bool:
        """Real, observable FAQ-intent signal from the page's own URL/headings —
        never inferred from anything outside what was actually crawled."""
        from urllib.parse import urlsplit

        path = urlsplit(page.url).path.lower()
        if "faq" in path or "question" in path:
            return True
        headings_text = " ".join(h.text.lower() for h in (page.headings or []))
        if "faq" in headings_text or "frequently asked" in headings_text:
            return True
        guide_markers = ("how to", "how do", "what is", "why does", "why is", "guide")
        return any(marker in headings_text for marker in guide_markers)

    @staticmethod
    def _question_heading_count(page) -> int:
        """Count real headings phrased as a question (ends with '?' or starts
        with a WH-word) — a proxy for existing FAQ coverage on the page."""
        wh_words = ("what", "why", "how", "when", "where", "who", "which", "can", "does", "is", "are")
        count = 0
        for heading in page.headings or []:
            text = heading.text.strip().lower()
            if not text:
                continue
            if text.endswith("?") or text.split(" ", 1)[0] in wh_words:
                count += 1
        return count
