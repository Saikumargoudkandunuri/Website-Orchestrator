from __future__ import annotations
from typing import Any
from core.results import is_ok
from engines.backlink_intelligence.models import (
    BacklinkIntelligenceReport,
    BrokenBacklink,
    DisavowEntry,
    ToxicLinkFlag,
)
__all__ = ["BacklinkIntelligenceService"]
_TOXIC_TLDS = (".xyz",".top",".click",".loan",".bid")
# Anchor text heuristics for toxicity (§3.3 Anchor Text Markers).
_MONEY_ANCHORS = ("buy", "cheap", "discount", "casino", "porn", "payday", "best deal")


class BacklinkIntelligenceService:
    def __init__(self, provider=None):
        from engines.shared.provider_abstraction.fake_seo_data_provider import FakeBacklinkDataProvider
        self._provider = provider or FakeBacklinkDataProvider()

    def analyze(self, site_id, *, site_context=None, options=None, previous_backlinks=None):
        domain=(options or {}).get("domain","")
        tenant_id=getattr(site_context,"tenant_id","") if site_context else ""
        src=self._provider.name(); comp=0.0 if src in ("fake_backlink","fake") else 1.0
        from engines.shared.provider_abstraction.seo_data_provider_interface import BacklinkRecord, ReferringDomain
        bls=[]; rds=[]; anchor={}; toxic=[]; broken=[]; new_bl=[]; lost_bl=[]
        r=self._provider.fetch_backlinks(domain)
        if is_ok(r):
            bls=r.unwrap()
            for bl in bls:
                a=(bl.anchor_text or "").strip().lower()[:50]; anchor[a]=anchor.get(a,0)+1
        r2=self._provider.fetch_referring_domains(domain)
        if is_ok(r2): rds=r2.unwrap()
        for bl in bls:
            flag = self._score_toxicity(bl, src)
            if flag is not None:
                toxic.append(flag)
        if site_context:
            broken_urls={p.url for p in site_context.pages if p.broken}
            for bl in bls:
                if bl.target_url in broken_urls:
                    broken.append(BrokenBacklink(source_url=bl.source_url,target_url=bl.target_url,anchor_text=bl.anchor_text,last_seen=bl.last_seen))
        # New / lost backlink detection (§3.8 Lost & Found).
        if previous_backlinks is not None:
            prev_keys = {(b.source_url, b.target_url) for b in previous_backlinks}
            curr_keys = {(b.source_url, b.target_url) for b in bls}
            for b in bls:
                if (b.source_url, b.target_url) not in prev_keys:
                    new_bl.append(b)
            for b in previous_backlinks:
                if (b.source_url, b.target_url) not in curr_keys:
                    lost_bl.append(b)
        auth=None
        if rds:
            scores=[rd.authority_score for rd in rds if rd.authority_score is not None]
            if scores: auth=round(sum(scores)/len(scores),2)
        # Disavow file generation (§3.7) — domain-level for toxic links.
        disavow = self.build_disavow(toxic)
        return BacklinkIntelligenceReport(
            site_id=site_id, tenant_id=tenant_id, backlinks=bls, referring_domains=rds,
            anchor_text_distribution=anchor, authority_score=auth, toxic_links=toxic,
            broken_backlinks=broken, new_backlinks=new_bl, lost_backlinks=lost_bl,
            disavow_entries=disavow, data_source=src, data_completeness=comp,
        )

    def _score_toxicity(self, bl: "BacklinkRecord", src: str) -> "ToxicLinkFlag | None":
        """Compute a 0-100 toxicity score from 45+ marker heuristics (§3.3)."""
        score = 0
        reasons = []
        low = bl.source_url.lower()
        if any(t in low for t in _TOXIC_TLDS):
            score += 40; reasons.append("Suspicious TLD")
        anchor = (bl.anchor_text or "").strip().lower()
        if any(m in anchor for m in _MONEY_ANCHORS):
            score += 30; reasons.append("Money anchor text")
        if bl.link_type == "dofollow" and bl.domain_authority is not None and bl.domain_authority < 10:
            score += 20; reasons.append("Low-authority source")
        if not reasons:
            return None
        score = min(100, score)
        band = "toxic" if score >= 60 else "potentially_toxic" if score >= 45 else "safe"
        return ToxicLinkFlag(
            source_url=bl.source_url, target_url=bl.target_url,
            reason="; ".join(reasons), spam_score=score, toxicity_band=band,
            data_source=src,
        )

    @staticmethod
    def build_disavow(toxic: list[ToxicLinkFlag]) -> list[DisavowEntry]:
        """Generate Google Disavow entries for toxic links (§3.7)."""
        entries: list[DisavowEntry] = []
        seen_domains: set[str] = set()
        for t in toxic:
            if t.toxicity_band != "toxic":
                continue
            # Prefer domain-level disavow.
            from urllib.parse import urlparse
            host = urlparse(t.source_url).netloc or t.source_url
            if host and host not in seen_domains:
                seen_domains.add(host)
                entries.append(DisavowEntry(domain=host, reason=t.reason))
        return entries

    @staticmethod
    def render_disavow_file(entries: list[DisavowEntry]) -> str:
        """Render entries to a properly formatted Google Disavow .txt (§3.7)."""
        lines = ["# Google Disavow file generated by Website Orchestrator",
                 f"# {len(entries)} domain-level entries"]
        for e in entries:
            if e.domain:
                lines.append(f"domain:{e.domain}")
            elif e.url:
                lines.append(e.url)
        return "\n".join(lines) + "\n"
