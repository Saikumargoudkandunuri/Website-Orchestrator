"""API_Surface crawl orchestration — the thin glue that sequences the loop.

Requirement 10.10 requires the FastAPI route handlers to *delegate* crawling,
check execution, fix generation, and governance to their respective subsystems
and to contain no business logic themselves. This module holds the small amount
of *orchestration glue* that wires those subsystems together for
``POST /crawl`` so the route handler stays a thin pass-through:

    Crawler.crawl_site
      -> Digital_Twin.upsert_pages
      -> Check_Engine.run_all_checks
      -> Digital_Twin.persist_issues
      -> Fix_Generator.generate_fix (per persisted issue)
      -> Digital_Twin.persist_fixes
      -> CrawlSummary

The glue itself embeds **no** check or fix business logic — it only sequences
the typed calls and maps each persisted :class:`~core.types.Issue` back to the
:class:`~core.types.CrawledPage` it was raised against (by ``detail.page_url``)
so the Fix_Generator can transform it. Detection lives in the Check_Engine and
fix synthesis in the Fix_Generator; this module never inspects page content or
decides applicability (Req 10.10).

The returned :class:`~core.types.CrawlSummary` reports the number of pages
crawled, the count of issues grouped by issue type, and the counts of
Auto_Applicable_Fix versus Report_Only_Fix records (Req 10.1).

Invalid input (a malformed start URL or a non-positive / out-of-range page
count) is rejected by :meth:`core.interfaces.CrawlerPort.crawl_site`, which
raises :class:`~core.exceptions.InvalidCrawlRequest` **before** retrieving
anything. Because the crawl is the first step, that rejection happens before any
persistence, so no pages, issues, or fixes are written (Req 10.11).
"""

from __future__ import annotations

from core.interfaces import (
    CheckEnginePort,
    CrawlerPort,
    DigitalTwinPort,
    FixGeneratorPort,
)
from core.types import CrawledPage, CrawlSummary, Issue, IssueType, SuggestedFix

__all__ = ["run_crawl"]


def run_crawl(
    start_url: str,
    max_pages: int,
    *,
    tenant_id: str,
    crawler: CrawlerPort,
    digital_twin: DigitalTwinPort,
    check_engine: CheckEnginePort,
    fix_generator: FixGeneratorPort,
) -> CrawlSummary:
    """Drive the full crawl->check->fix loop and return a :class:`CrawlSummary`.

    Delegates each stage to the injected subsystem contract and persists the
    results through the Digital_Twin (Req 10.1). Raises
    :class:`~core.exceptions.InvalidCrawlRequest` (from the Crawler) for invalid
    input before any persistence occurs (Req 10.11).
    """
    # 1. Crawl. The Crawler validates the request first and raises
    #    InvalidCrawlRequest for a malformed start_url / out-of-range max_pages,
    #    retrieving nothing — so nothing below runs and nothing is persisted
    #    (Req 10.11).
    pages: list[CrawledPage] = crawler.crawl_site(start_url, max_pages)

    # 2. Persist the crawled pages so issues can reference them.
    digital_twin.upsert_pages(tenant_id, pages)

    # 3. Run every deterministic check across the crawled pages, then persist the
    #    emitted candidates as Issues.
    candidates = check_engine.run_all_checks(pages)
    issues: list[Issue] = digital_twin.persist_issues(tenant_id, candidates)

    # 4. Generate a SuggestedFix per persisted issue. The Fix_Generator needs the
    #    page each issue was raised against; map issues back to their page by URL
    #    (orchestration glue only — no fix logic here). generate_fix returns at
    #    most one fix, or None when no fix maps to the issue (Req 5.1, 5.2).
    pages_by_url: dict[str, CrawledPage] = {page.url: page for page in pages}
    fixes: list[SuggestedFix] = []
    for issue in issues:
        page = pages_by_url.get(issue.detail.page_url)
        if page is None:
            continue
        fix = fix_generator.generate_fix(issue, page)
        if fix is not None:
            fixes.append(fix)

    # 5. Persist the generated fixes.
    persisted_fixes = digital_twin.persist_fixes(tenant_id, fixes)

    # 6. Assemble the summary (Req 10.1).
    return _summarize(pages, issues, persisted_fixes)


def _summarize(
    pages: list[CrawledPage],
    issues: list[Issue],
    fixes: list[SuggestedFix],
) -> CrawlSummary:
    """Build the :class:`CrawlSummary` from the loop's persisted results.

    Reports the pages-crawled count, the per-issue-type counts, and the
    Auto_Applicable_Fix versus Report_Only_Fix counts (Req 10.1).
    """
    issues_by_type: dict[IssueType, int] = {}
    for issue in issues:
        issues_by_type[issue.issue_type] = issues_by_type.get(issue.issue_type, 0) + 1

    auto_applicable_count = sum(1 for fix in fixes if fix.auto_applicable == 1)
    report_only_count = sum(1 for fix in fixes if fix.auto_applicable == 0)

    return CrawlSummary(
        pages_crawled=len(pages),
        issues_by_type=issues_by_type,
        auto_applicable_count=auto_applicable_count,
        report_only_count=report_only_count,
    )
