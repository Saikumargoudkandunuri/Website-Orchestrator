"""ReputationDataProvider interface (§4.4).

No concrete provider is wired this milestone. The interface is designed so that
a Google Reviews, Facebook, Trustpilot, or Yelp adapter can be dropped in without
touching any engine business logic.

Future adapters to implement (named per spec §4.4):
- GoogleReviewsProvider
- FacebookReviewsProvider
- TrustpilotProvider
- YelpProvider
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

from core.results import Result
from growth.errors import GrowthDataProviderError

__all__ = [
    "ReviewRecord",
    "BrandMention",
    "ReputationDataProvider",
]


class ReviewRecord(BaseModel):
    """A single review from any platform."""

    review_id: str
    platform: str  # google | facebook | trustpilot | yelp
    author_name: str | None = None
    rating: float | None = None  # out of 5.0 typically
    text: str = ""
    date: datetime | None = None
    is_responded: bool = False
    response_text: str | None = None
    location_id: str | None = None
    data_source: str = "fake"
    data_completeness: float = 0.0


class BrandMention(BaseModel):
    """A brand mention found by monitoring (provider-fake)."""

    mention_id: str
    platform: str
    url: str | None = None
    text: str = ""
    sentiment: str | None = None  # positive | negative | neutral
    date: datetime | None = None
    author: str | None = None
    data_source: str = "fake"


@runtime_checkable
class ReputationDataProvider(Protocol):
    """Interface for reputation/review data (§4.4).

    Adapter integration note: add a real provider adapter
    (e.g. Google Reviews API, Trustpilot API) by subclassing and registering.
    """

    def fetch_reviews(
        self, site_id: str, location_id: str | None = None
    ) -> Result[list[ReviewRecord], GrowthDataProviderError]: ...

    def fetch_brand_mentions(
        self, site_id: str
    ) -> Result[list[BrandMention], GrowthDataProviderError]: ...

    def name(self) -> str: ...
