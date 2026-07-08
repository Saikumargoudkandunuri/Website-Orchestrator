from __future__ import annotations
from typing import Any
from core.results import is_ok
from engines.backlink_intelligence.models import BacklinkIntelligenceReport, BrokenBacklink, ToxicLinkFlag
__all__ = ["BacklinkIntelligenceService"]
_TOXIC_TLDS = (".xyz",".top",".click",".loan",".bid")
class BacklinkIntelligenceService:
    def __init__(self, provider=None):
        from engines.shared.provider_abstraction.fake_seo_data_provider import FakeBacklinkDataProvider
        self._provider = provider or FakeBacklinkDataProvider()
    def analyze(self, site_id, *, site_context=None, options=None):
        domain=(options or {}).get("domain","")
        tenant_id=getattr(site_context,"tenant_id","") if site_context else ""
        src=self._provider.name(); comp=0.0 if src in ("fake_backlink","fake") else 1.0
        from engines.shared.provider_abstraction.seo_data_provider_interface import BacklinkRecord, ReferringDomain
        bls=[]; rds=[]; anchor={}; toxic=[]; broken=[]
        r=self._provider.fetch_backlinks(domain)
        if is_ok(r):
            bls=r.unwrap()
            for bl in bls:
                a=(bl.anchor_text or "").strip().lower()[:50]; anchor[a]=anchor.get(a,0)+1
        r2=self._provider.fetch_referring_domains(domain)
        if is_ok(r2): rds=r2.unwrap()
        for bl in bls:
            if any(t in bl.source_url.lower() for t in _TOXIC_TLDS):
                toxic.append(ToxicLinkFlag(source_url=bl.source_url,reason="Suspicious TLD.",data_source=src))
        if site_context:
            broken_urls={p.url for p in site_context.pages if p.broken}
            for bl in bls:
                if bl.target_url in broken_urls:
                    broken.append(BrokenBacklink(source_url=bl.source_url,target_url=bl.target_url,anchor_text=bl.anchor_text,last_seen=bl.last_seen))
        auth=None
        if rds:
            scores=[rd.authority_score for rd in rds if rd.authority_score is not None]
            if scores: auth=round(sum(scores)/len(scores),2)
        return BacklinkIntelligenceReport(site_id=site_id,tenant_id=tenant_id,backlinks=bls,referring_domains=rds,anchor_text_distribution=anchor,authority_score=auth,toxic_links=toxic,broken_backlinks=broken,data_source=src,data_completeness=comp)
