"""RankTrackingProvider interface (§4.5).

Google Search Console is explicitly called out as more tractable — implement a
real GoogleSearchConsoleRankTrackingProvider if GSC credentials are available.
Daily/weekly SERP rank-scraping providers stay fake/architecture-only.

Future adapters to implement (named per spec §4.5):
- GoogleSearchConsoleRankTrackingProvider (implement if GSC credentials available)
- SERPScraperProvider (third-party paid API — architecture only this milestone)
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from core.results import Result
from growth.errors import GrowthDataProviderError

__all__ = [
    "RankingSnapshot",
    "RankTrackingProvider",
]


class RankingSnapshot(BaseModel):
    """A single ranking data point (append-only time series).

    Uses ``captured_at`` semantics rather than the generic ``version: int``
    pattern, since ranking history IS a time series, not a versioned report.

    Per spec §4.5: "use RankingSnapshot as an append-only stream, with
    computed_at semantics naturally satisfied by captured_at."
    """

    site_id: str
    keyword: str
    page_id: str | None = None
    position: float | None = None  # None = not ranking in top N
    device: str = "desktop"  # desktop | mobile
    geo: str | None = None  # ISO country code or city string
    captured_at: datetime
    previous_position: float | None = None  # for change detection
    url: str | None = None  # the URL Google shows for this keyword
    data_source: str = "fake"
    data_completeness: float = 0.0


@runtime_checkable
class RankTrackingProvider(Protocol):
    """Interface for rank tracking data (§4.5).

    Adapter integration note: add a real adapter for
    Google Search Console if credentials are available. Daily/weekly scrapers
    stay fake this milestone.
    """

    def fetch_rankings(
        self,
        site_id: str,
        keywords: list[str],
        device: str = "desktop",
        geo: str | None = None,
    ) -> Result[list[RankingSnapshot], GrowthDataProviderError]: ...

    def name(self) -> str: ...
