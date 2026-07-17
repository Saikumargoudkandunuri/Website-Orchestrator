"""Rank Tracking Engine models (§4.5)."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

__all__ = [
    "RankingSnapshot",
    "RankingChange",
    "TimeSeriesExport",
    "RankTrackingReport",
    "TrackedKeyword",
]


@dataclass(frozen=True)
class TrackedKeyword:
    """Keyword configuration for rank tracking."""
    keyword_id: str
    keyword: str
    page_id: str
    device: str  # "desktop" | "mobile"
    geo: str  # "US" | "US-CA-Los Angeles" | "UK" | etc.
    cadence: str  # "daily" | "weekly" | "monthly"
    active: bool = True


@dataclass(frozen=True)
class RankingSnapshot:
    """
    Single ranking observation (§4.5).
    
    CRITICAL: This is append-only time series, NOT versioned reports.
    Uses captured_at for time series semantics, not computed_at/version.
    """
    snapshot_id: str
    keyword_id: str
    keyword: str
    page_id: str
    position: int | None  # None = not ranking in top 100
    device: str
    geo: str
    captured_at: datetime
    url: str | None = None  # Actual URL that ranked (may differ from expected page)
    data_source: str = "provider"
    serp_features: list[str] = field(default_factory=list)  # SERP features present for this query


@dataclass(frozen=True)
class RankingChange:
    """Detected ranking change between consecutive snapshots."""
    keyword_id: str
    keyword: str
    page_id: str
    previous_position: int | None
    current_position: int | None
    change: int  # Positive = improvement (moved up), negative = decline
    change_percentage: float | None
    detected_at: datetime
    significance: str  # "major" | "moderate" | "minor"


@dataclass(frozen=True)
class TimeSeriesExport:
    """Graph-ready time series data (§4.5)."""
    series: list[dict[str, Any]]  # [{"date": "2026-01-15", "value": 3.5}, ...]
    metric_name: str
    aggregation: str  # "average" | "sum" | "count"


@dataclass(frozen=True)
class RankTrackingReport:
    """
    Rank Tracking Report (§4.5).
    
    Per-keyword-per-page scope, sitewide aggregation.
    Time series pattern: references append-only RankingSnapshot stream.
    """
    site_id: str
    snapshot_count: int  # Total snapshots in time series
    latest_snapshot_at: datetime | None
    changes: list[RankingChange]  # Recent ranking changes
    visibility_trend: TimeSeriesExport  # Time series of visibility score
    share_of_voice: float | None  # Requires competitor data (delegates to M3 Competitor Intelligence)
    computed_at: datetime  # Report assembly time (NOT snapshot capture time)
    data_source: str = "provider"
    data_completeness: float = 1.0
    # --- Priority 2 additions (Semrush Position Tracking / Ahrefs Rank Tracker) ---
    serp_features: dict[str, int] = field(default_factory=dict)   # feature_type -> count owned
    rank_distribution: dict[str, int] = field(default_factory=dict)  # "1-3" | "4-10" | "11-20" | "21-50" | "51-100"


# Note: RankingSnapshot itself is NOT a "report" - it's raw time series data
# RankTrackingReport is the analytical layer over the time series
