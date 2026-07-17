from __future__ import annotations
import hashlib, re
from datetime import datetime, timezone
from typing import Any
from engines.content_intelligence.models import (
    AiContentScore,
    ContentBrief,
    ContentEngineReport,
    DuplicateFragment,
    EntityCoverageResult,
    FreshnessStatus,
    QuestionCoverageResult,
)
__all__ = ["ContentIntelligenceService"]
_MIN_FRAG_WORDS = 30
class ContentIntelligenceService:
    def __init__(self, capability_runner=None):
        self._runner = capability_runner
    def analyze(self, page_id, site_id, *, knowledge_object=None, site_context=None, options=None):
        tenant_id = getattr(knowledge_object,"tenant_id","") if knowledge_object else ""
        dups=[]; ec=EntityCoverageResult(); qc=QuestionCoverageResult()
        missing=[]; ai=AiContentScore(); rich=None; depth=None; suggestions=[]; m2ref=None; freshness=None
        if knowledge_object is not None:
            ko=knowledge_object; content=getattr(ko,"content_intelligence",None)
            if content: dups=self._dups(ko); ec=self._entity_cov(ko); rich=self._rich(content); depth=self._depth(content)
            m2ref=f"KnowledgeObject/{page_id}/version/{getattr(ko,'version','?')}"
            if self._runner: ai,missing,suggestions=self._ai(ko,page_id)
            freshness=self._freshness(ko)
        return ContentEngineReport(page_id=page_id,site_id=site_id,tenant_id=tenant_id,duplicate_fragments=dups,
            semantic_richness_score=rich,entity_coverage=ec,question_coverage=qc,missing_sections=missing,
            content_depth_score=depth,ai_content_score=ai,optimization_suggestions=suggestions,m2_content_score_ref=m2ref)
    def _dups(self, ko):
        content=getattr(ko,"content_intelligence",None); paras=[]
        if content:
            fp=getattr(content,"first_paragraph",None); lp=getattr(content,"last_paragraph",None)
            if fp: paras.append(fp)
            if lp and lp!=fp: paras.append(lp)
        out=[]
        for p in paras:
            if not p or len(p.split())<_MIN_FRAG_WORDS: continue
            h=hashlib.sha256(re.sub(r"\s+"," ",p.strip().lower()).encode()).hexdigest()
            out.append(DuplicateFragment(fragment_hash=h,fragment_excerpt=p[:200]))
        return out
    def _entity_cov(self, ko):
        kw=getattr(ko,"keyword_intelligence",None)
        present=[e.text for e in (getattr(kw,"named_entities",[]) or []) if (e.confidence is None or e.confidence>=0.5)] if kw else []
        return EntityCoverageResult(entities_present=present,coverage_score=min(1.0,len(present)/max(1,5)))
    def _rich(self, content):
        wc=getattr(content,"word_count",0) or 0; hn=len(getattr(content,"heading_structure",[]) or [])
        r=getattr(content,"readability_score",None)
        if wc==0: return None
        return round(min(1.0,wc/1000)*0.4+min(1.0,hn/5)*0.3+((min(100,max(0,r))/100) if r else 0.5)*0.3,2)
    def _depth(self, content):
        wc=getattr(content,"word_count",0) or 0; ts=getattr(content,"topic_coverage_score",None); ss=getattr(content,"semantic_completeness_score",None)
        vals=[v for v in [ts,ss] if v is not None]
        if not vals and wc==0: return None
        return round(min(1.0,wc/1500)*0.5+(sum(vals)/len(vals) if vals else 0.5)*0.5,2)
    def _ai(self, ko, page_id):
        from intelligence.prompts.base_prompt_template import PromptContext
        content=getattr(ko,"content_intelligence",None)
        ctx=PromptContext(page_url=getattr(getattr(ko,"identity",None),"url",""),word_count=getattr(content,"word_count",0) if content else 0)
        result=self._runner.run("content_analysis",ctx,page_id=page_id)
        payload=result.payload or {}
        missing=payload.get("missing_topics",[])
        suggestions=[f"Cover: {t}" for t in missing[:3]]
        score=AiContentScore(score=float(payload.get("semantic_completeness_score",0) or 0)*100,reasoning="AI-assessed (inferred).",source="inferred")
        return score,missing,suggestions
    def _freshness(self, ko):
        """Content freshness monitoring (§5 P4)."""
        content=getattr(ko,"content_intelligence",None)
        last_updated=getattr(content,"last_updated",None) if content else None
        if last_updated is None:
            return None
        if isinstance(last_updated, str):
            try:
                last_updated=datetime.fromisoformat(last_updated)
            except ValueError:
                return None
        days=(datetime.now(timezone.utc)-last_updated).days
        stale=days>=365
        return FreshnessStatus(
            page_id=getattr(ko,"page_id",""),
            last_updated=last_updated, days_since_update=days, is_stale=stale,
            recommendation="Update content — over 12 months old." if stale else None,
        )
    def generate_brief(self, target_keyword: str, *, top_pages: list[dict] | None = None,
                       semantic_keywords: list[str] | None = None) -> ContentBrief:
        """Generate a pre-writing SEO brief from top-10 SERP analysis (§1.6.3)."""
        top_pages = top_pages or []
        word_counts=[p.get("word_count",0) for p in top_pages if p.get("word_count")]
        recommended_wc = int(sum(word_counts)/len(word_counts)) if word_counts else None
        competitor_urls=[p.get("url","") for p in top_pages if p.get("url")]
        return ContentBrief(
            target_keyword=target_keyword,
            recommended_word_count=recommended_wc,
            semantic_keywords=semantic_keywords or [],
            readability_target=60.0,
            recommended_backlink_sources=competitor_urls[:5],
            section_recommendations={"intro": 300, "body": (recommended_wc or 1000)-600, "faq": 300},
            title_recommendation=f"{target_keyword} — Complete Guide",
            meta_description_recommendation=f"Learn everything about {target_keyword}.",
            schema_suggestions=["Article", "FAQPage", "BreadcrumbList"],
            competitor_urls=competitor_urls,
        )
