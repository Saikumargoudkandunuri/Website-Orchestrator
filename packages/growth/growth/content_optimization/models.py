"""Content Optimization Engine models (§4.2)."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

__all__ = [
    "SnippetOpportunity",
    "PaaOpportunity",
    "ContentOptimizationReport",
]


@dataclass(frozen=True)
class SnippetOpportunity:
    """Featured snippet opportunity detection (§4.2)."""
    query_pattern: str
    current_position: int | None
    has_suitable_answer_format: bool
    recommendation: str
    confidence_score: float


@dataclass(frozen=True)
class PaaOpportunity:
    """People Also Ask opportunity detection (§4.2)."""
    question: str
    is_covered: bool
    coverage_quality_score: float | None
    recommendation: str


@dataclass(frozen=True)
class ContentOptimizationReport:
    """
    Content Optimization Report (§4.2).
    
    Thin wrapper over M3 Content Intelligence + M2 ContentIntelligenceSection.
    New contributions: featured snippet, PAA, intent matching, EEAT recommendations.
    """
    page_id: str
    featured_snippet_opportunities: list[SnippetOpportunity]
    paa_opportunities: list[PaaOpportunity]
    intent_match_score: float  # 0.0-1.0, does format match search intent?
    eeat_recommendations: list[str]  # Actionable version of M2 EeatSection
    optimization_score: dict[str, Any]  # SeoScoreBreakdown-shaped, transparent breakdown
    computed_at: datetime
    version: int
    data_source: str = "deterministic+ai"
    data_completeness: float = 1.0
