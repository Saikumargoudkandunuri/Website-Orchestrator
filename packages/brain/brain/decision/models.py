"""Decision Engine Models (M5 Phase 2).

Provides the structures for cross-engine action recommendations (PrioritizedDecision)
and the historical performance feedback loop (HistoricalOutcome).
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

__all__ = [
    "ScoringDimension",
    "PrioritizedDecision",
    "HistoricalOutcome",
]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ScoringDimension(BaseModel):
    """A named component of a decision's total score for transparent inspectability."""

    name: str  # e.g., 'roi', 'traffic', 'difficulty', 'business_impact', 'ai_confidence', 'dependencies', 'risk', 'historical_results'
    score: float  # -1.0 to 1.0 (normalized)
    weight: float  # Multiplier in the final composite score
    rationale: str | None = None


class PrioritizedDecision(BaseModel):
    """A cross-engine action recommendation fully traceable to its source."""

    id: str
    tenant_id: str
    site_id: str
    
    title: str
    description: str
    
    # Traceability
    source_engine: str  # The M3/M4 engine that surfaced the underlying issue/opportunity
    source_ref: str     # The exact finding ID or reference
    
    # Target (what this decision operates on)
    target_page_ids: list[str] = Field(default_factory=list)
    target_entity_ids: list[str] = Field(default_factory=list)
    
    # Action formulation
    recommended_action: str
    estimated_effort_hours: float | None = None
    
    # Scoring
    dimensions: list[ScoringDimension] = Field(default_factory=list)
    composite_score: float = 0.0  # The final rankable score
    
    # AI synthesis
    ai_rationale: str | None = None
    ai_confidence: float = 0.0
    
    created_at: datetime = Field(default_factory=_utc_now)


class HistoricalOutcome(BaseModel):
    """Before/after observation pair for a deployed decision."""

    id: str
    tenant_id: str
    site_id: str
    decision_id: str
    
    # Baseline
    baseline_recorded_at: datetime
    baseline_metrics: dict[str, float] = Field(default_factory=dict)
    
    # Outcome
    outcome_recorded_at: datetime | None = None
    outcome_metrics: dict[str, float] = Field(default_factory=dict)
    
    # Evaluation
    is_success: bool | None = None
    performance_delta: float | None = None  # Normalized impact score (-1.0 to 1.0)
    
    created_at: datetime = Field(default_factory=_utc_now)
