from __future__ import annotations
from typing import Any
from core.results import is_ok
from engines.competitor_intelligence.models import (
    BacklinkGapItem,
    CompetitorComparison,
    CompetitorIntelligenceReport,
    ContentGap,
    KeywordGap,
    PageGap,
)
__all__ = ["CompetitorIntelligenceService"]
class CompetitorIntelligenceService:
    def __init__(self, provider=None, competitor_domain=""):
        from engines.shared.provider_abstraction.fake_seo_data_provider import FakeCompetitorDataProvider
        self._provider = provider or FakeCompetitorDataProvider()
        self._domain = competitor_domain
    def analyze(self, site_id, *, site_context=None, options=None, compare_domains=None):
        domain=(options or {}).get("competitor_domain",self._domain) or "competitor.example"
        tenant_id=getattr(site_context,"tenant_id","") if site_context else ""
        src=self._provider.name(); comp=0.0 if src in ("fake_competitor","fake") else 1.0
        kw_gaps=[]; page_gaps=[]; comparison=[]; backlink_gaps=[]
        r=self._provider.fetch_competitor_keywords(domain)
        if is_ok(r):
            for kw in r.unwrap():
                if kw.our_position is None: kw_gaps.append(KeywordGap(keyword=kw.keyword,competitor_position=kw.competitor_position,estimated_volume=kw.estimated_volume))
        pr=self._provider.fetch_competitor_pages(domain,"general")
        if is_ok(pr):
            for cp in pr.unwrap(): page_gaps.append(PageGap(topic=cp.topic or cp.title or "unknown",competitor_url=cp.url,estimated_traffic=cp.estimated_traffic))
        # Side-by-side comparison (§1.4.4) — uses provider pages for each domain.
        compare_domains = compare_domains or []
        for d in compare_domains:
            comparison.append(self._compare_domain(d))
        # Backlink gap finder (§1.4.6) — domains linking to competitors but not us.
        backlink_gaps = self._backlink_gap(compare_domains)
        return CompetitorIntelligenceReport(
            site_id=site_id, tenant_id=tenant_id, competitor_domain=domain,
            keyword_gaps=kw_gaps, page_gaps=page_gaps, comparison=comparison,
            backlink_gaps=backlink_gaps, data_source=src, data_completeness=comp,
        )

    def _compare_domain(self, domain: str) -> CompetitorComparison:
        """Build a single-domain comparison row (§1.4.4)."""
        est_traffic = None
        r = self._provider.fetch_competitor_pages(domain, "general")
        if is_ok(r):
            pages = r.unwrap()
            if pages:
                est_traffic = sum(p.estimated_traffic or 0 for p in pages)
        return CompetitorComparison(domain=domain, estimated_traffic=est_traffic)

    def _backlink_gap(self, competitor_domains: list[str]) -> list[BacklinkGapItem]:
        """Find referring domains linking to competitors but not us (§1.4.6)."""
        items: list[BacklinkGapItem] = []
        # Use the backlink provider to find competitor backlinks.
        from engines.shared.provider_abstraction.seo_data_provider_interface import CompetitorBacklink
        for d in competitor_domains:
            rb = self._provider.fetch_competitor_backlinks(d)
            if not is_ok(rb):
                continue
            for cb in rb.unwrap():
                if isinstance(cb, CompetitorBacklink):
                    host = cb.source_url.split("/")[2] if "://" in cb.source_url else cb.source_url
                    items.append(BacklinkGapItem(
                        referring_domain=host,
                        links_to=[d],
                        authority_score=cb.domain_authority,
                        priority="high" if (cb.domain_authority or 0) >= 50 else "medium",
                    ))
        return items
