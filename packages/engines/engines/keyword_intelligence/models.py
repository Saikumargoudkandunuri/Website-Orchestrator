"""Keyword Intelligence Engine output models (§4.3).

Extends (does not duplicate) Milestone 2's KeywordIntelligenceSection.
New this milestone: clustering, difficulty/traffic estimates (architecture-only
behind provider interface), opportunity scoring, cannibalization detection.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

__all__ = [
    "KeywordCluster",
    "DifficultyEstimate",
    "CannibalizationFlag",
    "LongTailOpportunity",
    "KeywordEngineReport",
]


class KeywordCluster(BaseModel):
    """A group of semantically related keywords for this page (§4.3)."""

    cluster_id: str
    label: str
    keywords: list[str] = Field(default_factory=list)
    primary_keyword: str | None = None
    source: str = "inferred"


class DifficultyEstimate(BaseModel):
    """Keyword difficulty/traffic estimate (§4.3, architecture-only until real provider).

    ``data_source`` propagates whether this came from a real provider or the
    deterministic heuristic fallback, so downstream engines (SEO Scoring) can
    set ``data_completeness`` honestly.
    """

    keyword: str
    difficulty: float | None = None          # 0.0-1.0; null until real provider
    estimated_monthly_traffic: float | None = None
    opportunity_score: float | None = None   # combined difficulty + traffic fit
    data_source: str = "heuristic"           # "heuristic" | provider name
    confidence: float | None = None


class CannibalizationFlag(BaseModel):
    """Two pages targeting the same/near-identical focus keyphrase (§4.3)."""

    keyphrase: str
    competing_page_ids: list[str] = Field(default_factory=list)
    severity: str = "medium"     # critical | high | medium | low
    source: str = "observed"


class LongTailOpportunity(BaseModel):
    """A specific long-tail keyword opportunity surfaced for this page (§4.3)."""

    keyword: str
    estimated_volume: float | None = None
    current_coverage: float = 0.0       # 0.0 = not covered; 1.0 = well covered
    data_source: str = "heuristic"


class SerpFeature(BaseModel):
    """A SERP feature present for a tracked keyword (§1.3 / §1.5)."""
    feature_type: str   # featured_snippet | ai_overview | local_pack | paa | sitelinks | reviews ...
    owned_by_us: bool = False
    source: str = "inferred"


class KeywordGapItem(BaseModel):
    """One keyword in a gap analysis segment (§1.4.5 Keyword Gap)."""
    keyword: str
    competitor_positions: dict[str, int | None] = Field(default_factory=dict)  # domain -> position
    our_position: int | None = None
    estimated_volume: float | None = None
    segment: str  # missing | weak | strong | untapped | unique


class PillarClusterPlan(BaseModel):
    """A pillar page + cluster pages plan (§1.5.3 Keyword Strategy Builder)."""
    pillar_keyword: str
    cluster_ids: list[str] = Field(default_factory=list)
    total_cluster_volume: float = 0.0
    average_difficulty: float | None = None
    intent: str | None = None


class KeywordEngineReport(BaseModel):
    """Keyword Intelligence engine output for one page (§4.3)."""

    page_id: str
    site_id: str
    tenant_id: str
    version: int = 1
    clusters: list[KeywordCluster] = Field(default_factory=list)
    difficulty_estimates: list[DifficultyEstimate] = Field(default_factory=list)
    cannibalization_flags: list[CannibalizationFlag] = Field(default_factory=list)
    long_tail_opportunities: list[LongTailOpportunity] = Field(default_factory=list)
    keyword_gap_summary: list[str] = Field(default_factory=list)  # sitewide gaps, AI-inferred
    # --- Priority 2 additions (Semrush Keyword Research / Gap) ---
    serp_features: list[SerpFeature] = Field(default_factory=list)
    keyword_gaps: list[KeywordGapItem] = Field(default_factory=list)
    pillar_plan: list[PillarClusterPlan] = Field(default_factory=list)
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
