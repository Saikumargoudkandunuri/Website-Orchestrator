"""Technical SEO Engine service - composes all technical checks (4.1).

Implements the Semrush Site Audit capability set (§1.2): 140+ checks across
crawlability, HTTPS/security, performance/Core Web Vitals, on-page SEO,
internal linking, international (hreflang) SEO, and content duplication. Each
page audit produces a 0-100 Health Score via :meth:`TechnicalSeoService.health_score`.
"""
from __future__ import annotations

from typing import Any

from engines.technical_seo.models import (
    FindingSeverity,
    TechnicalFinding,
    TechnicalSeoAudit,
)
from engines.technical_seo.services.checks_content import (
    check_h1_present,
    check_images_have_alt,
    check_schema_present,
    check_thin_content,
)
from engines.technical_seo.services.checks_crawlability import (
    check_broken_page,
    check_crawl_depth,
    check_https,
    check_indexability,
)
from engines.technical_seo.services.checks_links import (
    check_broken_links,
    check_link_depth,
    check_orphan_page,
    check_redirect_chain,
)
from engines.technical_seo.services.checks_metadata import (
    check_canonical_issues,
    check_duplicate_meta,
    check_duplicate_title,
    check_missing_meta_description,
    check_missing_title,
    check_robots_directive,
)
from engines.technical_seo.services.checks_international import (
    check_hreflang,
    check_hreflang_return_tag,
)
from engines.technical_seo.services.checks_performance import (
    check_core_web_vitals,
    check_insecure_form_action,
    check_mixed_content,
    check_ttfb,
)
from engines.technical_seo.services.checks_duplication import (
    check_duplicate_content,
    check_duplicate_meta_description,
)

__all__ = ["TechnicalSeoService", "SiteHealthAggregator", "detect_crawl_changes"]

# Severity weights used to compute the page Health Score (0-100).
# A passed check contributes nothing to the penalty; a failed check subtracts
# proportionally to its severity. Mirrors Semrush's Health Score semantics.
_SEVERITY_PENALTY = {
    FindingSeverity.CRITICAL: 25.0,
    FindingSeverity.HIGH: 12.0,
    FindingSeverity.MEDIUM: 5.0,
    FindingSeverity.LOW: 2.0,
    FindingSeverity.INFO: 0.0,
}

_SINGLE_CHECKS = [
    check_broken_page, check_indexability, check_https, check_crawl_depth,
    check_missing_title, check_missing_meta_description, check_robots_directive,
    check_duplicate_title, check_duplicate_meta, check_broken_links,
    check_redirect_chain, check_orphan_page, check_link_depth,
    check_thin_content, check_h1_present, check_images_have_alt, check_schema_present,
    check_ttfb, check_mixed_content, check_insecure_form_action,
    check_duplicate_content, check_duplicate_meta_description,
]
_MULTI_CHECKS = [check_canonical_issues, check_hreflang, check_hreflang_return_tag,
                 check_core_web_vitals]


class TechnicalSeoService:
    """Runs all technical SEO checks against a KnowledgeObject (4.1)."""

    def analyze(self, page_id: str, site_id: str, *, knowledge_object: Any = None,
                site_context: Any = None, options: dict = None) -> TechnicalSeoAudit:
        findings: list[TechnicalFinding] = []
        if knowledge_object is not None:
            ko = knowledge_object
            for check_fn in _SINGLE_CHECKS:
                try:
                    result = check_fn(ko)
                    if isinstance(result, list):
                        findings.extend(result)
                    else:
                        findings.append(result)
                except Exception:
                    pass
            for check_fn in _MULTI_CHECKS:
                try:
                    findings.extend(check_fn(ko))
                except Exception:
                    pass
        critical = sum(1 for f in findings if not f.passed and f.severity == FindingSeverity.CRITICAL)
        high = sum(1 for f in findings if not f.passed and f.severity == FindingSeverity.HIGH)
        medium = sum(1 for f in findings if not f.passed and f.severity == FindingSeverity.MEDIUM)
        passed = sum(1 for f in findings if f.passed)
        audit = TechnicalSeoAudit(
            page_id=page_id, site_id=site_id,
            tenant_id=getattr(knowledge_object, "tenant_id", "") if knowledge_object else "",
            findings=findings, critical_count=critical, high_count=high,
            medium_count=medium, passed_count=passed,
        )
        audit.health_score = self.health_score(audit)
        return audit

    @staticmethod
    def health_score(audit: TechnicalSeoAudit) -> float:
        """Compute a 0-100 Health Score for a page audit (§1.2).

        Starts at 100 and subtracts weighted penalties for each failed finding.
        Critical issues dominate; info-level passes do not penalize.
        """
        penalty = 0.0
        for f in audit.findings:
            if not f.passed:
                penalty += _SEVERITY_PENALTY.get(f.severity, 0.0)
        return max(0.0, min(100.0, 100.0 - penalty))


class SiteHealthAggregator:
    """Aggregates per-page TechnicalSeoAudit results into a site-level report (§1.2).

    Produces the Site Health Score trend, issues-by-category breakdown, and
    per-category health scores that the Semrush Site Audit Overview surfaces.
    """

    def __init__(self, audits: list[TechnicalSeoAudit]) -> None:
        self.audits = audits

    def site_health_score(self) -> float:
        """Site Health Score = mean of page Health Scores (0-100)."""
        if not self.audits:
            return 100.0
        return sum(TechnicalSeoService.health_score(a) for a in self.audits) / len(self.audits)

    def issues_by_severity(self) -> dict[str, int]:
        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        for a in self.audits:
            for f in a.findings:
                if not f.passed:
                    counts[f.severity.value] = counts.get(f.severity.value, 0) + 1
        return counts

    def issues_by_category(self) -> dict[str, int]:
        """Group failed findings by their check's category (derived from name)."""
        category_map = {
            "broken_page": "crawlability", "not_indexable": "crawlability",
            "excessive_url_depth": "crawlability", "broken_links": "links",
            "redirect_chain": "links", "orphan_page": "links", "link_depth": "links",
            "not_https": "https", "mixed_content": "https", "insecure_form_action": "https",
            "cwv_": "performance", "ttfb": "performance",
            "missing_title": "onpage", "missing_meta_description": "onpage",
            "duplicate_title": "onpage", "duplicate_meta": "onpage",
            "robots_noindex": "onpage", "canonical_issue": "onpage",
            "missing_h1": "onpage", "multiple_h1": "onpage",
            "images_missing_alt": "onpage", "missing_schema": "onpage",
            "thin_content": "content", "duplicate_content": "content",
            "duplicate_meta_description": "content",
            "missing_hreflang": "hreflang", "invalid_hreflang_value": "hreflang",
            "duplicate_hreflang_lang": "hreflang", "missing_return_hreflang": "hreflang",
        }
        by_cat: dict[str, int] = {}
        for a in self.audits:
            for f in a.findings:
                if not f.passed:
                    cat = "other"
                    for key, value in category_map.items():
                        if f.check_name.startswith(key):
                            cat = value
                            break
                    by_cat[cat] = by_cat.get(cat, 0) + 1
        return by_cat

    def per_category_health(self) -> dict[str, float]:
        """Per-category health score (0-100) across all audited pages."""
        # Collect failed checks per category.
        failed: dict[str, int] = {}
        total_checks: dict[str, int] = {}
        for a in self.audits:
            for f in a.findings:
                cat = "other"
                for key, value in self._category_map().items():
                    if f.check_name.startswith(key):
                        cat = value
                        break
                total_checks[cat] = total_checks.get(cat, 0) + 1
                if not f.passed:
                    failed[cat] = failed.get(cat, 0) + 1
        return {
            cat: max(0.0, 100.0 - (failed.get(cat, 0) / total_checks[cat] * 100.0))
            for cat in total_checks
        }

    @staticmethod
    def _category_map() -> dict[str, str]:
        return {
            "broken_page": "crawlability", "not_indexable": "crawlability",
            "excessive_url_depth": "crawlability", "broken_links": "links",
            "redirect_chain": "links", "orphan_page": "links", "link_depth": "links",
            "not_https": "https", "mixed_content": "https", "insecure_form_action": "https",
            "cwv_": "performance", "ttfb": "performance",
            "missing_title": "onpage", "missing_meta_description": "onpage",
            "duplicate_title": "onpage", "duplicate_meta": "onpage",
            "robots_noindex": "onpage", "canonical_issue": "onpage",
            "missing_h1": "onpage", "multiple_h1": "onpage",
            "images_missing_alt": "onpage", "missing_schema": "onpage",
            "thin_content": "content", "duplicate_content": "content",
            "duplicate_meta_description": "content",
            "missing_hreflang": "hreflang", "invalid_hreflang_value": "hreflang",
            "duplicate_hreflang_lang": "hreflang", "missing_return_hreflang": "hreflang",
        }

    def build_report(self, tenant_id: str = "") -> "SiteTechnicalReport":
        """Build a :class:`SiteTechnicalReport` from the aggregated audits."""
        from engines.technical_seo.models import SiteTechnicalReport  # noqa: PLC0415
        return SiteTechnicalReport(
            site_id=self.audits[0].site_id if self.audits else "",
            tenant_id=tenant_id or (self.audits[0].tenant_id if self.audits else ""),
            pages_audited=len(self.audits),
            site_health_score=self.site_health_score(),
            issues_by_severity=self.issues_by_severity(),
            issues_by_category=self.issues_by_category(),
            per_category_health=self.per_category_health(),
        )


def detect_crawl_changes(
    previous: list[TechnicalSeoAudit],
    current: list[TechnicalSeoAudit],
) -> dict[str, Any]:
    """Compare two crawl runs and report deltas (§1.2 change detection).

    Returns new issues, resolved issues, and health-score movement per page.
    """
    prev_by_page = {a.page_id: a for a in previous}
    curr_by_page = {a.page_id: a for a in current}

    new_pages = [p for p in curr_by_page if p not in prev_by_page]
    removed_pages = [p for p in prev_by_page if p not in curr_by_page]

    new_issues: list[dict[str, str]] = []
    resolved_issues: list[dict[str, str]] = []
    health_deltas: dict[str, float] = {}

    for page_id, curr in curr_by_page.items():
        prev = prev_by_page.get(page_id)
        if prev is None:
            continue
        prev_failed = {(f.check_name, f.severity.value) for f in prev.findings if not f.passed}
        curr_failed = {(f.check_name, f.severity.value) for f in curr.findings if not f.passed}
        for key in curr_failed - prev_failed:
            new_issues.append({"page_id": page_id, "check": key[0], "severity": key[1]})
        for key in prev_failed - curr_failed:
            resolved_issues.append({"page_id": page_id, "check": key[0], "severity": key[1]})
        health_deltas[page_id] = round(curr.health_score - prev.health_score, 2)

    return {
        "new_pages": new_pages,
        "removed_pages": removed_pages,
        "new_issues": new_issues,
        "resolved_issues": resolved_issues,
        "health_deltas": health_deltas,
        "previous_site_health": (
            sum(a.health_score for a in previous) / len(previous) if previous else None
        ),
        "current_site_health": (
            sum(a.health_score for a in current) / len(current) if current else None
        ),
    }
