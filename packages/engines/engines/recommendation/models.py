"""Recommendation Engine output models (§4.10).

The human-facing synthesis layer — every Recommendation is fully traceable
end-to-end back through Opportunity → originating engine finding → raw
observation (satisfying the auditability principle from Milestone 1).
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field

__all__ = [
    "DifficultyLevel",
    "Recommendation",
    "RecommendationReport",
]


class DifficultyLevel(str, Enum):
    EASY = "easy"
    MODERATE = "moderate"
    HARD = "hard"


class Recommendation(BaseModel):
    """One actionable recommendation fully traceable to its source (§4.10)."""

    id: str
    #: Cross-reference to the originating Opportunity (traceability chain: §4.10).
    opportunity_id: str | None = None
    #: Cross-reference to the originating engine finding.
    problem_ref: str                  # e.g. "technical_seo/{page_id}/redirect_chain"
    problem_summary: str
    impact: float = 0.0               # 0.0-1.0, pulled from Opportunity Engine
    priority: float = 0.0             # pulled from Opportunity Engine
    #: Links to a Milestone 1 FixGenerator type where directly actionable.
    recommended_fix_type: str | None = None  # e.g. "update_meta_description"
    estimated_benefit: str = ""
    difficulty: DifficultyLevel = DifficultyLevel.MODERATE
    #: AI-assessed confidence in this recommendation (distinct from underlying finding confidence).
    confidence: float = 0.5
    #: Other recommendation ids that should logically precede this one.
    dependencies: list[str] = Field(default_factory=list)
    #: Reference to the AIInvocation that produced the synthesis narrative.
    ai_invocation_ref: str | None = None
    data_completeness: float = 1.0  # propagated from upstream sources
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RecommendationReport(BaseModel):
    """Synthesis layer output — the human-facing front door (§4.10)."""

    site_id: str
    tenant_id: str
    version: int = 1
    page_id: str | None = None       # null for a sitewide report
    recommendations: list[Recommendation] = Field(default_factory=list)
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
