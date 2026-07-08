"""LocalSeoDataProvider interface (§4.3).

No concrete provider is wired this milestone. The interface is designed so that
a Yext, BrightLocal, Local Viking, Local Falcon, or Citation Vault adapter can
be dropped in without touching any engine business logic.

Future adapters to implement (named per spec §4.3):
- YextLocalSeoProvider
- BrightLocalProvider
- LocalVikingProvider
- LocalFalconProvider
- CitationVaultProvider
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

from core.results import Result
from growth.errors import GrowthDataProviderError

__all__ = [
    "BusinessProfileData",
    "CitationRecord",
    "DirectoryListing",
    "LocalSeoDataProvider",
]


class BusinessProfileData(BaseModel):
    """Google Business Profile data for one location."""

    location_id: str
    business_name: str | None = None
    address: str | None = None
    phone: str | None = None
    website: str | None = None
    categories: list[str] = Field(default_factory=list)
    hours: dict[str, str] = Field(default_factory=dict)  # day -> hours string
    photo_count: int = 0
    post_count_last_30_days: int = 0
    attributes: dict[str, str] = Field(default_factory=dict)
    rating: float | None = None
    review_count: int = 0
    is_verified: bool = False
    data_source: str = "fake"
    data_completeness: float = 0.0


class CitationRecord(BaseModel):
    """A single citation/directory listing for a location."""

    directory_name: str
    url: str | None = None
    business_name: str | None = None
    address: str | None = None
    phone: str | None = None
    is_claimed: bool = False
    is_accurate: bool = False
    data_source: str = "fake"


class DirectoryListing(BaseModel):
    """A directory where the business should be listed."""

    directory_name: str
    directory_url: str
    is_listed: bool = False
    listing_url: str | None = None
    status: str = "unknown"  # listed | missing | incorrect | unclaimed
    data_source: str = "fake"


@runtime_checkable
class LocalSeoDataProvider(Protocol):
    """Interface for local SEO data (§4.3).

    Adapter integration note: add a real provider adapter
    (e.g. Yext, BrightLocal, Local Viking) by subclassing and registering.
    """

    def fetch_business_profile(
        self, location_id: str
    ) -> Result[BusinessProfileData, GrowthDataProviderError]: ...

    def fetch_citations(
        self, location_id: str
    ) -> Result[list[CitationRecord], GrowthDataProviderError]: ...

    def fetch_directory_listings(
        self, location_id: str
    ) -> Result[list[DirectoryListing], GrowthDataProviderError]: ...

    def name(self) -> str: ...
