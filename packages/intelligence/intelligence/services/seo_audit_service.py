"""Holistic SEO audit -> AI Intelligence Summary (§4.12, §13.2).

Runs LAST in the DAG because it reasons over the whole assembled KnowledgeObject.
Produces the AI summary (purpose/audience/goal/gaps/priorities/do_not_change)
plus the Rank-Math-style per-factor ``seo_recommendations`` checklist.
"""

from __future__ import annotations

from intelligence.models.knowledge_object import (
    AiIntelligenceSummary,
    PrioritizedImprovement,
    SeoRecommendation,
    SeoRecommendationPriority,
    SeoRecommendationStatus,
)
from intelligence.services.base import AnalysisContext, AnalyzerService

__all__ = ["SeoAuditService"]

_STATUS = {s.value for s in SeoRecommendationStatus}
_PRIORITY = {p.value for p in SeoRecommendationPriority}


class SeoAuditService(AnalyzerService):
    section = "ai_summary"

    def analyze(self, ctx: AnalysisContext) -> None:
        if ctx.runner is None:
            return
        result = ctx.runner.run("seo_audit", ctx.prompt_context, page_id=ctx.page_id)
        ctx.warnings.extend(result.warnings)
        payload = result.payload
        if not payload:
            return

        summary = AiIntelligenceSummary(
            page_purpose=payload.get("page_purpose"),
            target_audience=payload.get("target_audience"),
            business_goal=payload.get("business_goal"),
            user_expectations=payload.get("user_expectations"),
            search_engine_expectations=payload.get("search_engine_expectations"),
            key_gaps=payload.get("key_gaps", []),
            improvement_priorities=[
                PrioritizedImprovement(
                    title=p.get("title", ""),
                    rationale=p.get("rationale"),
                    priority=int(p.get("priority", 0) or 0),
                    capability=p.get("capability"),
                )
                for p in payload.get("improvement_priorities", [])
                if isinstance(p, dict) and p.get("title")
            ],
            do_not_change=payload.get("do_not_change", []),
            seo_recommendations=[
                self._recommendation(r)
                for r in payload.get("seo_recommendations", [])
                if isinstance(r, dict) and self._recommendation(r) is not None
            ],
        )
        # Cross-reference human-readable do_not_change with machine immutable_fields.
        ctx.ko.ai_summary = summary

    def _recommendation(self, r: dict) -> SeoRecommendation | None:
        status = r.get("status")
        priority = r.get("priority", "medium")
        if status not in _STATUS:
            return None
        return SeoRecommendation(
            factor=r.get("factor", ""),
            status=SeoRecommendationStatus(status),
            recommendation_text=r.get("recommendation_text", ""),
            priority=SeoRecommendationPriority(priority if priority in _PRIORITY else "medium"),
            related_fix_type=r.get("related_fix_type"),
        )
