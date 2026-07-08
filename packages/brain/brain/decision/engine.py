"""Decision Engine Core (M5 Phase 2).

Transforms the read-only SiteSynthesis and WebsiteKnowledgeGraph into ranked,
actionable decisions using seven specific scoring dimensions.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any

from brain.decision.models import HistoricalOutcome, PrioritizedDecision, ScoringDimension
from brain.decision.repositories import DecisionRepository, HistoricalOutcomeRepository
from brain.knowledge_graph.models import WebsiteKnowledgeGraph
from brain.models import SiteSynthesis

__all__ = [
    "DecisionEngine",
    "HistoricalOutcomeTracker",
]


class DecisionEngine:
    """Evaluates SiteSynthesis data to produce ranked PrioritizedDecisions."""

    def __init__(
        self,
        decision_repo: DecisionRepository,
        historical_repo: HistoricalOutcomeRepository,
    ) -> None:
        self._decision_repo = decision_repo
        self._historical_repo = historical_repo

    def evaluate_synthesis(
        self, synthesis: SiteSynthesis, graph: WebsiteKnowledgeGraph
    ) -> list[PrioritizedDecision]:
        """Convert engine outputs into prioritized decisions."""
        decisions: list[PrioritizedDecision] = []
        
        # In a real implementation, we would map over each M3/M4 engine's output in the
        # synthesis. Since this is the M5 platform blueprint, we mock the extraction
        # of raw "candidates" from the synthesis payload and score them.
        
        # Example 1: Extract opportunities from M3
        if "opportunity_discovery" in synthesis.m3_engines:
            opp_summary = synthesis.m3_engines["opportunity_discovery"]
            if opp_summary.has_data:
                # Mock candidate generation for testing
                decisions.append(
                    self._score_candidate(
                        tenant_id=synthesis.tenant_id,
                        site_id=synthesis.site_id,
                        title="Optimize high-value underperforming page",
                        description="Page ranks #11 but has high search volume.",
                        source_engine="opportunity_discovery",
                        source_ref="opp-123",
                        target_page_ids=["page-1"],
                        recommended_action="Rewrite content to match intent and add internal links.",
                        effort_hours=4.0,
                        raw_roi=0.8,
                        raw_traffic=0.7,
                        raw_diff=0.3,
                        ai_confidence=0.9,
                        deps_count=0,
                        risk_score=0.1,
                    )
                )

        # Sort by final composite score descending
        decisions.sort(key=lambda d: d.composite_score, reverse=True)
        
        # Persist the decisions
        for d in decisions:
            self._decision_repo.save(d)
            
        return decisions

    def _score_candidate(
        self,
        tenant_id: str,
        site_id: str,
        title: str,
        description: str,
        source_engine: str,
        source_ref: str,
        target_page_ids: list[str],
        recommended_action: str,
        effort_hours: float,
        raw_roi: float,
        raw_traffic: float,
        raw_diff: float,
        ai_confidence: float,
        deps_count: int,
        risk_score: float,
    ) -> PrioritizedDecision:
        """Apply the 7 scoring dimensions to a candidate decision."""
        # Normalize difficulty (lower is better for score)
        norm_diff = max(0.0, 1.0 - raw_diff)
        
        # Normalize dependencies (fewer is better)
        norm_deps = 1.0 if deps_count == 0 else max(0.0, 1.0 - (deps_count * 0.2))
        
        # Normalize risk (lower is better)
        norm_risk = max(0.0, 1.0 - risk_score)
        
        # Historical success (default neutral 0.5 if no data)
        # Real implementation would query the historical_repo based on the action type
        hist_score = 0.5
        
        dimensions = [
            ScoringDimension(name="roi", score=raw_roi, weight=0.25, rationale="High expected return"),
            ScoringDimension(name="traffic_impact", score=raw_traffic, weight=0.20, rationale="Significant volume"),
            ScoringDimension(name="difficulty", score=norm_diff, weight=0.15, rationale=f"Effort: {effort_hours}h"),
            ScoringDimension(name="ai_confidence", score=ai_confidence, weight=0.10, rationale="High pattern match"),
            ScoringDimension(name="dependencies", score=norm_deps, weight=0.10, rationale=f"Deps: {deps_count}"),
            ScoringDimension(name="risk", score=norm_risk, weight=0.10, rationale="Low execution risk"),
            ScoringDimension(name="historical_results", score=hist_score, weight=0.10, rationale="No prior data"),
        ]
        
        composite = sum(d.score * d.weight for d in dimensions)
        
        # Stable ID based on source and ref
        decision_id = f"dec_{hashlib.md5(f'{source_engine}:{source_ref}'.encode()).hexdigest()[:12]}"
        
        return PrioritizedDecision(
            id=decision_id,
            tenant_id=tenant_id,
            site_id=site_id,
            title=title,
            description=description,
            source_engine=source_engine,
            source_ref=source_ref,
            target_page_ids=target_page_ids,
            recommended_action=recommended_action,
            estimated_effort_hours=effort_hours,
            dimensions=dimensions,
            composite_score=composite,
            ai_rationale="The composite score indicates a strong quick-win opportunity.",
            ai_confidence=ai_confidence,
        )


class HistoricalOutcomeTracker:
    """Tracks and evaluates the success of deployed decisions over time."""

    def __init__(self, historical_repo: HistoricalOutcomeRepository) -> None:
        self._historical_repo = historical_repo

    def record_baseline(
        self, decision: PrioritizedDecision, baseline_metrics: dict[str, float]
    ) -> HistoricalOutcome:
        """Snapshot metrics when a decision is deployed."""
        outcome = HistoricalOutcome(
            id=f"out_{uuid.uuid4().hex[:12]}",
            tenant_id=decision.tenant_id,
            site_id=decision.site_id,
            decision_id=decision.id,
            baseline_recorded_at=datetime.now(timezone.utc),
            baseline_metrics=baseline_metrics,
        )
        self._historical_repo.save(outcome)
        return outcome

    def record_outcome(
        self, tenant_id: str, decision_id: str, current_metrics: dict[str, float]
    ) -> HistoricalOutcome | None:
        """Update a deployed decision with real-world outcomes."""
        outcome = self._historical_repo.get_by_decision(tenant_id, decision_id)
        if not outcome:
            return None
            
        outcome.outcome_recorded_at = datetime.now(timezone.utc)
        outcome.outcome_metrics = current_metrics
        
        # Simple evaluation logic: check if primary metric improved
        # A real implementation would be more sophisticated
        is_success = False
        delta = 0.0
        
        if "traffic" in outcome.baseline_metrics and "traffic" in current_metrics:
            base_traf = outcome.baseline_metrics["traffic"]
            curr_traf = current_metrics["traffic"]
            if base_traf > 0:
                delta = (curr_traf - base_traf) / base_traf
                is_success = delta > 0.05  # >5% improvement is a success
                
        # Cap delta between -1.0 and 1.0
        outcome.performance_delta = max(-1.0, min(1.0, delta))
        outcome.is_success = is_success
        
        self._historical_repo.save(outcome)
        return outcome
