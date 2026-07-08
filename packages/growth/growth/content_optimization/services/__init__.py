"""Content Optimization services."""
from __future__ import annotations
from datetime import datetime, timezone
from core.results import Ok, Result
from growth.content_optimization.models import (
    ContentOptimizationReport,
    SnippetOpportunity,
    PaaOpportunity,
)
from growth.errors import GrowthAnalysisError

__all__ = ["ContentOptimizationService"]


class ContentOptimizationService:
    """Content Optimization business logic (§4.2)."""

    def analyze(
        self,
        page_id: str,
        content_intelligence_output: dict,
        content_intelligence_section: dict,
        keyword_intelligence_section: dict,
    ) -> Result[ContentOptimizationReport, GrowthAnalysisError]:
        snippet_opps = self._detect_snippet_opportunities(
            content_intelligence_output, keyword_intelligence_section
        )
        paa_opps = self._detect_paa_opportunities(
            content_intelligence_section, keyword_intelligence_section
        )
        intent_score = self._compute_intent_match_score(
            content_intelligence_section, keyword_intelligence_section
        )
        eeat_recs = self._generate_eeat_recommendations(content_intelligence_section)
        opt_score = self._compute_optimization_score(
            snippet_opps, paa_opps, intent_score, eeat_recs
        )
        return Ok(ContentOptimizationReport(
            page_id=page_id,
            featured_snippet_opportunities=snippet_opps,
            paa_opportunities=paa_opps,
            intent_match_score=intent_score,
            eeat_recommendations=eeat_recs,
            optimization_score=opt_score,
            computed_at=datetime.now(timezone.utc),
            version=1,
        ))

    def _detect_snippet_opportunities(
        self, content_intel: dict, keyword_intel: dict
    ) -> list[SnippetOpportunity]:
        headings = content_intel.get("headings") or content_intel.get("heading_structure") or []
        questions = keyword_intel.get("question_keywords") or keyword_intel.get("questions") or []
        word_count = int(content_intel.get("word_count") or 0)
        opportunities: list[SnippetOpportunity] = []
        for question in questions[:5]:
            has_question_heading = any(str(question).lower().rstrip("?") in str(h).lower() for h in headings)
            opportunities.append(SnippetOpportunity(
                query_pattern=str(question),
                current_position=keyword_intel.get("current_position"),
                has_suitable_answer_format=has_question_heading and 40 <= word_count,
                recommendation=(
                    "Add a concise 40-60 word answer directly under a matching question heading."
                    if not has_question_heading else
                    "Tighten the answer under this heading into a direct snippet-ready response."
                ),
                confidence_score=0.72 if has_question_heading else 0.58,
            ))
        return opportunities

    def _detect_paa_opportunities(
        self, content_intel: dict, keyword_intel: dict
    ) -> list[PaaOpportunity]:
        covered = {str(item).lower() for item in content_intel.get("covered_questions", [])}
        questions = keyword_intel.get("people_also_ask") or keyword_intel.get("question_keywords") or []
        return [
            PaaOpportunity(
                question=str(question),
                is_covered=str(question).lower() in covered,
                coverage_quality_score=0.8 if str(question).lower() in covered else None,
                recommendation="Add this question to the FAQ section with a concise answer."
                if str(question).lower() not in covered else
                "Refresh the existing answer with clearer entity coverage.",
            )
            for question in questions[:8]
        ]

    def _compute_intent_match_score(
        self, content_intel: dict, keyword_intel: dict
    ) -> float:
        intent = str(keyword_intel.get("search_intent") or "").lower()
        content_format = str(content_intel.get("content_format") or content_intel.get("page_type") or "").lower()
        if not intent:
            return 0.75
        expected = {
            "informational": {"guide", "blog", "faq", "how-to"},
            "commercial": {"comparison", "review", "service", "landing"},
            "transactional": {"product", "category", "landing", "service"},
            "navigational": {"home", "brand", "about"},
        }
        for key, formats in expected.items():
            if key in intent:
                return 0.9 if any(fmt in content_format for fmt in formats) else 0.55
        return 0.75

    def _generate_eeat_recommendations(self, content_intel: dict) -> list[str]:
        recs: list[str] = []
        if not content_intel.get("author_present"):
            recs.append("Add an author bio with relevant credentials.")
        if not content_intel.get("external_sources"):
            recs.append("Cite authoritative external sources for factual claims.")
        if not content_intel.get("reviewed_at"):
            recs.append("Add or refresh publication and review dates.")
        return recs or ["Maintain current EEAT signals and refresh examples periodically."]

    def _compute_optimization_score(
        self,
        snippet_opps: list[SnippetOpportunity],
        paa_opps: list[PaaOpportunity],
        intent_score: float,
        eeat_recs: list[str],
    ) -> dict:
        snippet_score = 1.0 if not snippet_opps else sum(o.confidence_score for o in snippet_opps) / len(snippet_opps)
        paa_score = 1.0 if not paa_opps else sum((o.coverage_quality_score or 0.35) for o in paa_opps) / len(paa_opps)
        eeat_score = max(0.3, 1.0 - (0.18 * len(eeat_recs)))
        overall = snippet_score * 0.25 + paa_score * 0.25 + intent_score * 0.25 + eeat_score * 0.25
        return {
            "overall": round(overall, 2),
            "breakdown": {
                "snippet_readiness": round(snippet_score, 2),
                "paa_coverage": round(paa_score, 2),
                "intent_alignment": round(intent_score, 2),
                "eeat_strength": round(eeat_score, 2),
            },
            "weights": {
                "snippet_readiness": 0.25,
                "paa_coverage": 0.25,
                "intent_alignment": 0.25,
                "eeat_strength": 0.25,
            },
        }