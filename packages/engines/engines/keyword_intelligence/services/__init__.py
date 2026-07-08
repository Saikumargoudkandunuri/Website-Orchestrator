"""Keyword Intelligence Engine service (4.3)."""
from __future__ import annotations
import hashlib, re
from typing import Any
from engines.keyword_intelligence.models import CannibalizationFlag, DifficultyEstimate, KeywordCluster, KeywordEngineReport, LongTailOpportunity

__all__ = ["KeywordIntelligenceService"]

class KeywordIntelligenceService:
    def analyze(self, page_id, site_id, *, knowledge_object=None, site_context=None, options=None):
        tenant_id = getattr(knowledge_object,"tenant_id","") if knowledge_object else ""
        clusters=[]; difficulty=[]; cann=[]; lt=[]; gaps=[]
        if knowledge_object is not None:
            kw = getattr(knowledge_object,"keyword_intelligence",None)
            if kw: clusters=self._clusters(kw,page_id); difficulty=self._difficulty(kw); lt=self._lt(kw)
        if site_context: cann=self._cann(site_context,page_id,knowledge_object); gaps=self._gaps(site_context)
        return KeywordEngineReport(page_id=page_id,site_id=site_id,tenant_id=tenant_id,clusters=clusters,difficulty_estimates=difficulty,cannibalization_flags=cann,long_tail_opportunities=lt,keyword_gap_summary=gaps)

    def _clusters(self,kw,page_id):
        def tok(t): return frozenset(w for w in re.split(r"\W+",t.lower()) if len(w)>2)
        all_kws=list(getattr(kw,"secondary_keyphrases",[])+getattr(kw,"related_semantic_keywords",[]))
        used=set(); clusters=[]
        for kw_text in all_kws:
            if kw_text in used: continue
            toks=tok(kw_text); group=[kw_text]; used.add(kw_text)
            for o in all_kws:
                if o in used: continue
                if tok(o)&toks: group.append(o); used.add(o)
            cid="kc_"+hashlib.sha256(f"{page_id}:{kw_text}".encode()).hexdigest()[:10]
            clusters.append(KeywordCluster(cluster_id=cid,label=kw_text,keywords=group,primary_keyword=kw_text))
        return clusters

    def _difficulty(self,kw):
        focus=getattr(kw,"primary_focus_keyphrase",None)
        if not focus: return []
        d=max(0.1,1.0-min(0.8,len(focus.split())*0.15))
        return [DifficultyEstimate(keyword=focus,difficulty=round(d,2),opportunity_score=round(1-d,2),data_source="heuristic",confidence=0.3)]

    def _lt(self,kw):
        focus=getattr(kw,"primary_focus_keyphrase","") or ""
        variants=getattr(kw,"keyword_variations",[]) or []
        return [LongTailOpportunity(keyword=v,data_source="heuristic") for v in variants[:5]]

    def _cann(self,ctx,page_id,ko):
        my_focus=""
        if ko:
            kw=getattr(ko,"keyword_intelligence",None)
            my_focus=(getattr(kw,"primary_focus_keyphrase","") or "") if kw else ""
        if not my_focus: return []
        mt=frozenset(t for t in re.split(r"\W+",my_focus.lower()) if len(t)>2)
        comp=[]
        for p in ctx.pages:
            if p.page_id==page_id or not p.focus_keyphrase: continue
            ot=frozenset(t for t in re.split(r"\W+",p.focus_keyphrase.lower()) if len(t)>2)
            if mt and ot and len(mt&ot)/max(len(mt),1)>=0.6: comp.append(p.page_id)
        if comp: return [CannibalizationFlag(keyphrase=my_focus,competing_page_ids=[page_id]+comp)]
        return []

    def _gaps(self,ctx):
        no_kp=sum(1 for p in ctx.pages if not p.focus_keyphrase)
        return [f"{no_kp} page(s) have no focus keyphrase"] if no_kp else []
