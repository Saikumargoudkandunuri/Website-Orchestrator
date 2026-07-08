"""Recommendation Engine service (section 4.10).

Transforms opportunities into structured, actionable Recommendations with full
traceability back to originating findings. Every Recommendation carries a
problem_ref that chains: Recommendation -> Opportunity -> engine finding ->
raw observation (satisfying the auditability principle from Milestone 1).
"""
from __future__ import annotations
import uuid
from typing import Any
from engines.recommendation.models import DifficultyLevel, Recommendation, RecommendationReport
from engines.opportunity.models import EffortLevel

__all__ = ["RecommendationService"]

_DIFFICULTY_MAP = {
    EffortLevel.SMALL.value: DifficultyLevel.EASY,
    EffortLevel.MEDIUM.value: DifficultyLevel.MODERATE,
    EffortLevel.LARGE.value: DifficultyLevel.HARD,
}

_FIX_TYPE_BENEFIT = {
    "update_alt_text": "Improves accessibility and image SEO ranking signals.",
    "update_meta_description": "Improves click-through rate in search results.",
    "update_title": "Improves title relevance and click-through rate.",
    "update_slug": "Improves URL readability and keyword relevance.",
    "update_schema": "Enables rich results and improved SERP appearance.",
    None: "Resolves a detected SEO issue.",
}


class RecommendationService:
    def __init__(self, capability_runner=None):
        self._runner = capability_runner

    def analyze(self, page_id, site_id, *, knowledge_object=None, site_context=None,
                options=None, opportunity_report=None):
        tenant_id = getattr(knowledge_object, "tenant_id", "") if knowledge_object else ""
        if tenant_id == "" and site_context:
            tenant_id = getattr(site_context, "tenant_id", "")
        recommendations: list[Recommendation] = []

        for opp in getattr(opportunity_report, "opportunities", []) or []:
            fix_type = self._infer_fix_type(opp)
            difficulty = _DIFFICULTY_MAP.get(
                getattr(opp, "effort", EffortLevel.MEDIUM).value, DifficultyLevel.MODERATE
            )
            confidence = self._estimate_confidence(opp)
            problem_summary = self._summarize_problem(opp)
            benefit = _FIX_TYPE_BENEFIT.get(fix_type, _FIX_TYPE_BENEFIT[None])

            recommendations.append(Recommendation(
                id=uuid.uuid4().hex[:12],
                opportunity_id=opp.id,
                problem_ref=opp.source_finding_ref,
                problem_summary=problem_summary,
                impact=opp.impact_estimate,
                priority=opp.priority_score,
                recommended_fix_type=fix_type,
                estimated_benefit=benefit,
                difficulty=difficulty,
                confidence=confidence,
                dependencies=[],
                ai_invocation_ref=None,
                data_completeness=opp.data_completeness,
            ))

        # Sort: critical first, then by priority desc
        recommendations.sort(key=lambda r: (-r.impact, -r.priority))
        return RecommendationReport(
            site_id=site_id, tenant_id=tenant_id,
            page_id=page_id, recommendations=recommendations,
        )

    def _infer_fix_type(self, opp):
        ref = getattr(opp, "source_finding_ref", "") or ""
        for fix_type in ("update_alt_text","update_meta_description","update_title",
                          "update_slug","update_schema"):
            if fix_type.replace("update_","") in ref:
                return fix_type
        return None

    def _estimate_confidence(self, opp):
        impact = getattr(opp, "impact_estimate", 0.5) or 0.5
        completeness = getattr(opp, "data_completeness", 1.0) or 1.0
        return round(impact * completeness * 0.85, 2)

    def _summarize_problem(self, opp):
        ref = getattr(opp, "source_finding_ref", "") or ""
        parts = ref.split("/")
        check = parts[-1].replace("_", " ").title() if parts else "Issue"
        return f"{check} detected on {parts[1] if len(parts) > 1 else 'page'}."
