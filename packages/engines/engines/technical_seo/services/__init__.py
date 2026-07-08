"""Technical SEO Engine service - composes all technical checks (4.1)."""
from __future__ import annotations
from typing import Any
from engines.technical_seo.models import FindingSeverity, TechnicalFinding, TechnicalSeoAudit
from engines.technical_seo.services.checks_content import check_h1_present, check_images_have_alt, check_schema_present, check_thin_content
from engines.technical_seo.services.checks_crawlability import check_broken_page, check_crawl_depth, check_https, check_indexability
from engines.technical_seo.services.checks_links import check_broken_links, check_link_depth, check_orphan_page, check_redirect_chain
from engines.technical_seo.services.checks_metadata import check_canonical_issues, check_duplicate_meta, check_duplicate_title, check_missing_meta_description, check_missing_title, check_robots_directive

__all__ = ["TechnicalSeoService"]

_SINGLE_CHECKS = [
    check_broken_page, check_indexability, check_https, check_crawl_depth,
    check_missing_title, check_missing_meta_description, check_robots_directive,
    check_duplicate_title, check_duplicate_meta, check_broken_links,
    check_redirect_chain, check_orphan_page, check_link_depth,
    check_thin_content, check_h1_present, check_images_have_alt, check_schema_present,
]
_MULTI_CHECKS = [check_canonical_issues]


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
        return TechnicalSeoAudit(
            page_id=page_id, site_id=site_id,
            tenant_id=getattr(knowledge_object, "tenant_id", "") if knowledge_object else "",
            findings=findings, critical_count=critical, high_count=high,
            medium_count=medium, passed_count=passed,
        )
