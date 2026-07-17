"""Keyword Intelligence Engine service (4.3).

Implements the Semrush Keyword Research / Gap feature set (§1.5, §1.4.5):
keyword difficulty + volume estimates, SERP feature tracking, keyword gap
analysis (missing/weak/strong/untapped/unique), and pillar/cluster planning.
"""
from __future__ import annotations
import hashlib, re
from typing import Any
from engines.keyword_intelligence.models import (
    CannibalizationFlag,
    DifficultyEstimate,
    KeywordCluster,
    KeywordEngineReport,
    KeywordGapItem,
    LongTailOpportunity,
    PillarClusterPlan,
    SerpFeature,
)

__all__ = ["KeywordIntelligenceService"]

# Known SERP feature types we can detect from provider/observed data.
_SERP_FEATURE_TYPES = (
    "featured_snippet", "ai_overview", "local_pack", "people_also_ask",
    "sitelinks", "reviews", "image_pack", "video_pack", "knowledge_panel",
)


class KeywordIntelligenceService:
    def analyze(self, page_id, site_id, *, knowledge_object=None, site_context=None, options=None):
        tenant_id = getattr(knowledge_object,"tenant_id","") if knowledge_object else ""
        clusters=[]; difficulty=[]; cann=[]; lt=[]; gaps=[]; serp=[]; gap_items=[]; pillar=[]
        if knowledge_object is not None:
            kw = getattr(knowledge_object,"keyword_intelligence",None)
            if kw:
                clusters=self._clusters(kw,page_id)
                difficulty=self._difficulty(kw)
                lt=self._lt(kw)
                serp=self._serp_features(kw)
        if site_context:
            cann=self._cann(site_context,page_id,knowledge_object)
            gaps=self._gaps(site_context)
            gap_items=self._gap_analysis(site_context, knowledge_object)
        # Pillar plan derives from detected clusters (needs no site context).
        pillar=self._pillar_plan(clusters, kw if knowledge_object else None)
        return KeywordEngineReport(
            page_id=page_id, site_id=site_id, tenant_id=tenant_id,
            clusters=clusters, difficulty_estimates=difficulty,
            cannibalization_flags=cann, long_tail_opportunities=lt,
            keyword_gap_summary=gaps, serp_features=serp,
            keyword_gaps=gap_items, pillar_plan=pillar,
        )

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
        vol=getattr(kw,"search_volume",None)
        return [DifficultyEstimate(keyword=focus,difficulty=round(d,2),
                                   estimated_monthly_traffic=vol,
                                   opportunity_score=round(1-d,2),data_source="heuristic",confidence=0.3)]

    def _lt(self,kw):
        focus=getattr(kw,"primary_focus_keyphrase","") or ""
        variants=getattr(kw,"keyword_variations",[]) or []
        return [LongTailOpportunity(keyword=v,data_source="heuristic") for v in variants[:5]]

    def _serp_features(self,kw):
        """Extract SERP features present for the focus keyword (§1.3 / §1.5)."""
        features=getattr(kw,"serp_features",None)
        if not features:
            return []
        out=[]
        for f in features:
            ftype = f if isinstance(f, str) else getattr(f, "feature_type", None)
            if ftype and ftype in _SERP_FEATURE_TYPES:
                owned = getattr(f, "owned_by_us", False) if not isinstance(f, str) else False
                out.append(SerpFeature(feature_type=ftype, owned_by_us=bool(owned)))
        return out

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

    def _gap_analysis(self, ctx, knowledge_object):
        """Keyword gap analysis vs competitor pages (§1.4.5).

        Builds missing/weak/strong/untapped/unique segments from the site
        context's per-page focus keyphrases and any competitor positions.
        """
        items=[]
        # Collect our pages' focus keyphrases.
        our_kps={}
        for p in getattr(ctx,"pages",[]):
            fk=getattr(p,"focus_keyphrase",None)
            if fk: our_kps[fk.lower()]=p.page_id
        # Competitor keyword data, if supplied via site_context.competitor_keywords.
        comp_kws=getattr(ctx,"competitor_keywords",[]) or []
        for ck in comp_kws:
            kw_text=getattr(ck,"keyword",None)
            if not kw_text: continue
            our_pos=getattr(ck,"our_position",None)
            comp_pos=getattr(ck,"competitor_position",None)
            vol=getattr(ck,"estimated_volume",None)
            if our_pos is None and comp_pos is not None:
                segment="missing"
            elif our_pos is not None and comp_pos is not None and our_pos > comp_pos:
                segment="weak"
            elif our_pos is not None and comp_pos is not None and our_pos <= comp_pos:
                segment="strong"
            elif our_pos is None and comp_pos is None:
                segment="untapped"
            else:
                segment="unique"
            items.append(KeywordGapItem(
                keyword=kw_text,
                competitor_positions={"competitor": comp_pos},
                our_position=our_pos, estimated_volume=vol, segment=segment,
            ))
        return items

    def _pillar_plan(self, clusters, kw):
        """Build a pillar/cluster plan from detected clusters (§1.5.3)."""
        if not clusters:
            return []
        plan=[]
        for c in clusters:
            vol=sum(getattr(kw,"search_volume",0) or 0 for _ in c.keywords) if kw else 0.0
            plan.append(PillarClusterPlan(
                pillar_keyword=c.primary_keyword or c.label,
                cluster_ids=[c.cluster_id],
                total_cluster_volume=float(vol),
                intent=getattr(kw,"search_intent",None),
            ))
        return plan
