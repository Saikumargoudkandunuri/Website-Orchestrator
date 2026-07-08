"""Analytics Intelligence Engine models (§4.8)."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any

__all__ = ["AnalyticsSnapshot", "AnalyticsReport"]


@dataclass(frozen=True)
class AnalyticsSnapshot:
    """
    Single analytics observation (§4.8).
    
    Append-only time series like RankingSnapshot.
    """
    snapshot_id: str
    site_id: str
    captured_at: datetime
    sessions: int
    users: int
    pageviews: int
    bounce_rate: float
    avg_session_duration: float
    conversions: int | None = None
    data_source: str = "provider"


@dataclass(frozen=True)
class AnalyticsReport:
    """
    Analytics Intelligence Report (§4.8).
    
    Sitewide, time series pattern, cross-references Rank Tracking + Keyword Intelligence.
    """
    site_id: str
    snapshot_count: int
    latest_snapshot_at: datetime | None
    top_pages: list[dict[str, Any]]
    top_keywords: list[dict[str, Any]]  # Cross-referenced with Rank Tracking/Keyword Intelligence
    growth_trend: dict[str, Any]  # TimeSeriesExport-shaped
    ai_summary: str  # AI narrative layer
    computed_at: datetime
    data_source: str = "provider"
    data_completeness: float = 1.0
