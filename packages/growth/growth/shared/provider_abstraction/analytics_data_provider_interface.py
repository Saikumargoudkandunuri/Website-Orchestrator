"""AnalyticsDataProvider interface (§4.8).

Google Search Console and Google Analytics are well-documented first-party APIs.
If credentials are available in the environment, real adapters should be
implemented; otherwise, the fake adapter is used.

Future adapters to implement (named per spec §4.8):
- GoogleAnalyticsProvider (implement if GA credentials available)
- GoogleSearchConsoleAnalyticsProvider (implement if GSC credentials available)
- MatomoProvider
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

from core.results import Result
from growth.errors import GrowthDataProviderError

__all__ = [
    "AnalyticsSnapshot",
    "TopPage",
    "TopKeyword",
    "AnalyticsDataProvider",
]


class AnalyticsSnapshot(BaseModel):
    """A point-in-time analytics snapshot (append-only time series).

    Analogous to RankingSnapshot — use ``captured_at`` for the time series.
    """

    site_id: str
    captured_at: datetime
    sessions: int = 0
    users: int = 0
    pageviews: int = 0
    bounce_rate: float | None = None  # 0.0-1.0
    avg_session_duration_s: float | None = None
    conversions: int = 0
    conversion_rate: float | None = None
    clicks: int = 0
    impressions: int = 0
    ctr: float | None = None  # click-through rate
    avg_position: float | None = None
    data_source: str = "fake"
    data_completeness: float = 0.0


class TopPage(BaseModel):
    """A top-performing page from analytics."""

    url: str
    page_id: str | None = None
    sessions: int = 0
    pageviews: int = 0
    bounce_rate: float | None = None
    avg_time_on_page_s: float | None = None
    data_source: str = "fake"


class TopKeyword(BaseModel):
    """A top-driving keyword from Search Console."""

    keyword: str
    clicks: int = 0
    impressions: int = 0
    ctr: float | None = None
    avg_position: float | None = None
    data_source: str = "fake"


@runtime_checkable
class AnalyticsDataProvider(Protocol):
    """Interface for analytics data (§4.8).

    Adapter integration note: add real adapters for
    Google Analytics and Google Search Console if credentials are available.
    Matomo stays fake/architecture-only.
    """

    def fetch_snapshot(
        self,
        site_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Result[AnalyticsSnapshot, GrowthDataProviderError]: ...

    def fetch_top_pages(
        self,
        site_id: str,
        limit: int = 10,
    ) -> Result[list[TopPage], GrowthDataProviderError]: ...

    def fetch_top_keywords(
        self,
        site_id: str,
        limit: int = 20,
    ) -> Result[list[TopKeyword], GrowthDataProviderError]: ...

    def name(self) -> str: ...
