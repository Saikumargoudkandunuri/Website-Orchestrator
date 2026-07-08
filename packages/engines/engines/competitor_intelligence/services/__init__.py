from __future__ import annotations
from typing import Any
from core.results import is_ok
from engines.competitor_intelligence.models import CompetitorIntelligenceReport, ContentGap, KeywordGap, PageGap
__all__ = ["CompetitorIntelligenceService"]
class CompetitorIntelligenceService:
    def __init__(self, provider=None, competitor_domain=""):
        from engines.shared.provider_abstraction.fake_seo_data_provider import FakeCompetitorDataProvider
        self._provider = provider or FakeCompetitorDataProvider()
        self._domain = competitor_domain
    def analyze(self, site_id, *, site_context=None, options=None):
        domain=(options or {}).get("competitor_domain",self._domain) or "competitor.example"
        tenant_id=getattr(site_context,"tenant_id","") if site_context else ""
        src=self._provider.name(); comp=0.0 if src in ("fake_competitor","fake") else 1.0
        kw_gaps=[]; page_gaps=[]
        r=self._provider.fetch_competitor_keywords(domain)
        if is_ok(r):
            for kw in r.unwrap():
                if kw.our_position is None: kw_gaps.append(KeywordGap(keyword=kw.keyword,competitor_position=kw.competitor_position,estimated_volume=kw.estimated_volume))
        pr=self._provider.fetch_competitor_pages(domain,"general")
        if is_ok(pr):
            for cp in pr.unwrap(): page_gaps.append(PageGap(topic=cp.topic or cp.title or "unknown",competitor_url=cp.url,estimated_traffic=cp.estimated_traffic))
        return CompetitorIntelligenceReport(site_id=site_id,tenant_id=tenant_id,competitor_domain=domain,keyword_gaps=kw_gaps,page_gaps=page_gaps,data_source=src,data_completeness=comp)
