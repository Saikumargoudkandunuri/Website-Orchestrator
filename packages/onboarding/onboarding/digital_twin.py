"""DigitalTwinBuilder — bootstrap the digital twin after the initial crawl.

Reuses the existing :class:`~digital_twin.repository.DigitalTwinRepository` and
the existing Check_Engine/Fix_Generator pipeline (via the orchestrator's
``run_crawl``-style flow) rather than duplicating logic. It builds the
enterprise digital-twin artifacts (architecture review #10):

* page graph / navigation graph (internal links)
* metadata, structured data, canonical map, image graph
* baselines: performance / accessibility / SEO / AI
* issues + suggestions (delegated to Check_Engine + Fix_Generator)

The builder is injectable: the check engine and fix generator are supplied so
tests can use fakes. It returns a :class:`TwinBuildResult` summary.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.interfaces import CheckEnginePort, FixGeneratorPort
from core.types import CrawledPage, IssueCandidate

from digital_twin.repository import DigitalTwinRepository

__all__ = ["TwinBuildResult", "DigitalTwinBuilder"]


@dataclass
class TwinBuildResult:
    """Summary of a digital-twin build."""

    website_id: str
    pages: int = 0
    internal_links: int = 0
    issues: int = 0
    suggestions: int = 0
    structured_data_pages: int = 0
    canonical_pages: int = 0
    image_count: int = 0
    performance_baseline: dict = field(default_factory=dict)
    accessibility_baseline: dict = field(default_factory=dict)
    seo_baseline: dict = field(default_factory=dict)
    ai_baseline: dict = field(default_factory=dict)


class DigitalTwinBuilder:
    """Build the digital twin from crawled pages using existing subsystems."""

    def __init__(
        self,
        digital_twin: DigitalTwinRepository,
        check_engine: CheckEnginePort,
        fix_generator: FixGeneratorPort,
        *,
        tenant_id: str,
    ) -> None:
        self._digital_twin = digital_twin
        self._check_engine = check_engine
        self._fix_generator = fix_generator
        self._tenant_id = tenant_id

    def build(self, website_id: str, pages: list[CrawledPage]) -> TwinBuildResult:
        """Analyze crawled pages, persist issues/fixes, and compute baselines."""
        result = TwinBuildResult(website_id=website_id)
        result.pages = len(pages)

        internal_links = 0
        structured = 0
        canonical = 0
        images = 0
        all_issues: list[IssueCandidate] = []

        for page in pages:
            internal_links += sum(
                1 for link in page.links if _same_host(link.url, page.url)
            )
            if page.has_schema:
                structured += 1
            if page.meta_description:
                canonical += 1
            images += len(page.images)

            # Delegate issue detection to the existing Check_Engine.
            candidates = self._check_engine.check_page(page)
            for candidate in candidates:
                all_issues.append((candidate, page))

        result.internal_links = internal_links
        result.structured_data_pages = structured
        result.canonical_pages = canonical
        result.image_count = images
        result.issues = len(all_issues)

        # Delegate fix generation to the existing Fix_Generator. The contract is
        # one fix per (issue, page) pair, so we call it for every detected issue.
        suggestions: list = []
        for candidate, page in all_issues:
            fix = self._fix_generator.generate_fix(candidate, page)
            if fix is not None:
                suggestions.append(fix)
        result.suggestions = len(suggestions)

        # Persist issues + fixes through the existing repository. The
        # Digital_Twin persists issues keyed by their source page url, so we
        # persist the aggregated candidates (each carries detail.page_url) and
        # then the generated fixes.
        if all_issues:
            self._digital_twin.persist_issues(
                self._tenant_id, [candidate for candidate, _ in all_issues]
            )
        if suggestions:
            self._digital_twin.persist_fixes(self._tenant_id, suggestions)

        # Baselines (deterministic aggregates; no external calls).
        result.performance_baseline = {
            "pages": result.pages,
            "images": result.image_count,
            "avg_word_count": (
                round(sum(p.word_count for p in pages) / max(len(pages), 1), 1)
                if pages
                else 0
            ),
        }
        result.accessibility_baseline = {
            "pages_missing_alt": sum(
                1 for p in pages for img in p.images if not img.alt_text
            ),
        }
        result.seo_baseline = {
            "pages_with_schema": structured,
            "pages_with_canonical": canonical,
            "issues": result.issues,
        }
        result.ai_baseline = {
            "auto_applicable_fixes": sum(
                1 for s in suggestions if getattr(s, "auto_applicable", 0)
            ),
        }
        return result


def _same_host(a: str, b: str) -> bool:
    from urllib.parse import urlsplit

    try:
        return urlsplit(a).hostname == urlsplit(b).hostname
    except Exception:  # noqa: BLE001
        return False
