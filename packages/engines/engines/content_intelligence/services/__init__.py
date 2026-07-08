from __future__ import annotations
import hashlib, re
from typing import Any
from engines.content_intelligence.models import AiContentScore, ContentEngineReport, DuplicateFragment, EntityCoverageResult, QuestionCoverageResult
__all__ = ["ContentIntelligenceService"]
_MIN_FRAG_WORDS = 30
class ContentIntelligenceService:
    def __init__(self, capability_runner=None):
        self._runner = capability_runner
    def analyze(self, page_id, site_id, *, knowledge_object=None, site_context=None, options=None):
        tenant_id = getattr(knowledge_object,"tenant_id","") if knowledge_object else ""
        dups=[]; ec=EntityCoverageResult(); qc=QuestionCoverageResult()
        missing=[]; ai=AiContentScore(); rich=None; depth=None; suggestions=[]; m2ref=None
        if knowledge_object is not None:
            ko=knowledge_object; content=getattr(ko,"content_intelligence",None)
            if content: dups=self._dups(ko); ec=self._entity_cov(ko); rich=self._rich(content); depth=self._depth(content)
            m2ref=f"KnowledgeObject/{page_id}/version/{getattr(ko,'version','?')}"
            if self._runner: ai,missing,suggestions=self._ai(ko,page_id)
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
