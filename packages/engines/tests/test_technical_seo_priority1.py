"""Tests for Priority 1 Technical SEO Automation (§1.2 Site Audit).

Covers Health Score (0-100), hreflang validation, Core Web Vitals, mixed
content, duplicate content, site-level aggregation, and crawl change detection.
"""
from __future__ import annotations

from types import SimpleNamespace

from engines.technical_seo.models import (
    FindingSeverity,
    SiteTechnicalReport,
    TechnicalFinding,
    TechnicalSeoAudit,
)
from engines.technical_seo.services import (
    SiteHealthAggregator,
    TechnicalSeoService,
    detect_crawl_changes,
)


def _ko(**kwargs: object) -> object:
    """Build a minimal fake KnowledgeObject for checks that read attributes."""
    return SimpleNamespace(**kwargs)


def test_health_score_perfect_when_no_failures() -> None:
    audit = TechnicalSeoAudit(
        page_id="p1", site_id="s1", tenant_id="t1",
        findings=[TechnicalFinding(check_name="x", severity=FindingSeverity.INFO,
                                   passed=True, description="ok")],
    )
    assert TechnicalSeoService.health_score(audit) == 100.0


def test_health_score_penalized_for_critical() -> None:
    audit = TechnicalSeoAudit(
        page_id="p1", site_id="s1", tenant_id="t1",
        findings=[TechnicalFinding(check_name="broken_page", severity=FindingSeverity.CRITICAL,
                                   passed=False, description="down")],
    )
    # 100 - 25 (critical) = 75
    assert TechnicalSeoService.health_score(audit) == 75.0


def test_health_score_clamped_at_zero() -> None:
    audit = TechnicalSeoAudit(
        page_id="p1", site_id="s1", tenant_id="t1",
        findings=[TechnicalFinding(check_name=f"c{i}", severity=FindingSeverity.CRITICAL,
                                   passed=False, description="x") for i in range(10)],
    )
    assert TechnicalSeoService.health_score(audit) == 0.0


def test_analyze_populates_health_score() -> None:
    ko = _ko(identity=SimpleNamespace(url="https://example.com/"),
             technical_seo=SimpleNamespace(broken=False, indexable=True, hreflang=[]),
             metadata=SimpleNamespace(seo_title=SimpleNamespace(current_value="Title"),
                                      meta_description=SimpleNamespace(current_value="Desc"),
                                      robots=None),
             content_intelligence=SimpleNamespace(thin_content=False, word_count=500,
                                                  h1_analysis=SimpleNamespace(count=1, issues=[]),
                                                  duplicate_of=[]),
             image_intelligence=SimpleNamespace(images=[]),
             schema_intelligence=SimpleNamespace(existing_schema=[], generated_jsonld=[]),
             internal_seo=SimpleNamespace(broken_links=[], orphan_page=False, link_depth=2),
             performance=SimpleNamespace(mixed_content_urls=[], insecure_form_actions=[],
                                         core_web_vitals=None, ttfb=None))
    service = TechnicalSeoService()
    audit = service.analyze("p1", "s1", knowledge_object=ko)
    # Only the missing_schema LOW check (-2.0) fires for this clean page.
    assert audit.health_score == 98.0
    assert audit.passed_count > 0


def test_hreflang_invalid_value_flagged() -> None:
    ko = _ko(identity=SimpleNamespace(url="https://example.com/"),
             technical_seo=SimpleNamespace(broken=False, indexable=True,
                                           hreflang=["en-USA"], is_multilocale=True,
                                           hreflang_alternates=[]),
             metadata=SimpleNamespace(seo_title=SimpleNamespace(current_value="T"),
                                      meta_description=SimpleNamespace(current_value="M"),
                                      robots=None),
             content_intelligence=SimpleNamespace(thin_content=False, word_count=500,
                                                  h1_analysis=SimpleNamespace(count=1, issues=[]),
                                                  duplicate_of=[]),
             image_intelligence=SimpleNamespace(images=[]),
             schema_intelligence=SimpleNamespace(existing_schema=[], generated_jsonld=[]),
             internal_seo=SimpleNamespace(broken_links=[], orphan_page=False, link_depth=2),
             performance=SimpleNamespace(mixed_content_urls=[], insecure_form_actions=[],
                                         core_web_vitals=None, ttfb=None))
    service = TechnicalSeoService()
    audit = service.analyze("p1", "s1", knowledge_object=ko)
    assert any(f.check_name == "invalid_hreflang_value" and not f.passed for f in audit.findings)


def test_core_web_vitals_poor_lcp_flagged() -> None:
    cwv = SimpleNamespace(lcp=5.0, inp=100.0, cls=0.05)
    ko = _ko(identity=SimpleNamespace(url="https://example.com/"),
             technical_seo=SimpleNamespace(broken=False, indexable=True, hreflang=[]),
             metadata=SimpleNamespace(seo_title=SimpleNamespace(current_value="T"),
                                      meta_description=SimpleNamespace(current_value="M"),
                                      robots=None),
             content_intelligence=SimpleNamespace(thin_content=False, word_count=500,
                                                  h1_analysis=SimpleNamespace(count=1, issues=[]),
                                                  duplicate_of=[]),
             image_intelligence=SimpleNamespace(images=[]),
             schema_intelligence=SimpleNamespace(existing_schema=[], generated_jsonld=[]),
             internal_seo=SimpleNamespace(broken_links=[], orphan_page=False, link_depth=2),
             performance=SimpleNamespace(mixed_content_urls=[], insecure_form_actions=[],
                                         core_web_vitals=cwv, ttfb=0.5))
    service = TechnicalSeoService()
    audit = service.analyze("p1", "s1", knowledge_object=ko)
    assert any(f.check_name == "cwv_lcp_poor" and not f.passed for f in audit.findings)


def test_mixed_content_flagged() -> None:
    ko = _ko(identity=SimpleNamespace(url="https://example.com/"),
             technical_seo=SimpleNamespace(broken=False, indexable=True, hreflang=[]),
             metadata=SimpleNamespace(seo_title=SimpleNamespace(current_value="T"),
                                      meta_description=SimpleNamespace(current_value="M"),
                                      robots=None),
             content_intelligence=SimpleNamespace(thin_content=False, word_count=500,
                                                  h1_analysis=SimpleNamespace(count=1, issues=[]),
                                                  duplicate_of=[]),
             image_intelligence=SimpleNamespace(images=[]),
             schema_intelligence=SimpleNamespace(existing_schema=[], generated_jsonld=[]),
             internal_seo=SimpleNamespace(broken_links=[], orphan_page=False, link_depth=2),
             performance=SimpleNamespace(mixed_content_urls=["http://cdn.example.com/a.png"],
                                         insecure_form_actions=[], core_web_vitals=None, ttfb=None))
    service = TechnicalSeoService()
    audit = service.analyze("p1", "s1", knowledge_object=ko)
    assert any(f.check_name == "mixed_content" and not f.passed for f in audit.findings)


def test_site_aggregator_reports() -> None:
    audits = [
        TechnicalSeoAudit(page_id="p1", site_id="s1", tenant_id="t1",
                          findings=[TechnicalFinding(check_name="broken_page",
                                                    severity=FindingSeverity.CRITICAL,
                                                    passed=False, description="x")]),
        TechnicalSeoAudit(page_id="p2", site_id="s1", tenant_id="t1",
                          findings=[TechnicalFinding(check_name="missing_title",
                                                    severity=FindingSeverity.HIGH,
                                                    passed=False, description="y")]),
    ]
    agg = SiteHealthAggregator(audits)
    report = agg.build_report()
    assert isinstance(report, SiteTechnicalReport)
    assert report.pages_audited == 2
    # p1: CRITICAL (-25) -> 75; p2: HIGH (-12) -> 88; mean = 81.5
    assert report.site_health_score == 81.5
    assert report.issues_by_severity["critical"] == 1
    assert report.issues_by_severity["high"] == 1
    assert "crawlability" in report.issues_by_category
    assert "onpage" in report.per_category_health


def test_crawl_change_detection() -> None:
    prev = TechnicalSeoAudit(page_id="p1", site_id="s1", tenant_id="t1",
                             health_score=88.0,
                             findings=[TechnicalFinding(check_name="missing_title",
                                                       severity=FindingSeverity.HIGH,
                                                       passed=False, description="y")])
    curr = TechnicalSeoAudit(page_id="p1", site_id="s1", tenant_id="t1",
                             health_score=100.0,
                             findings=[TechnicalFinding(check_name="missing_title",
                                                       severity=FindingSeverity.HIGH,
                                                       passed=True, description="fixed")])
    changes = detect_crawl_changes([prev], [curr])
    assert changes["resolved_issues"]
    assert changes["new_issues"] == []
    assert changes["health_deltas"]["p1"] == 12.0  # HIGH penalty recovered
