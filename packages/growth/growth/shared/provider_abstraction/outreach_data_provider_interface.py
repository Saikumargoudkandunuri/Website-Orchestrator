"""OutreachDataProvider interface (§4.9).

No concrete provider is wired this milestone. The interface is designed so that
a Hunter, BuzzStream, WhitePress, Prowly, or Cision adapter can be dropped in.

Future adapters to implement (named per spec §4.9):
- HunterProvider
- BuzzStreamProvider
- WhitePressProvider
- ProwlyProvider
- CisionProvider
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

from core.results import Result
from growth.errors import GrowthDataProviderError

__all__ = [
    "ContactRecord",
    "DomainQualificationData",
    "OutreachDataProvider",
]


class ContactRecord(BaseModel):
    """A discovered contact at a domain."""

    domain: str
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    title: str | None = None
    linkedin_url: str | None = None
    confidence: float | None = None  # provider-reported confidence
    data_source: str = "fake"


class DomainQualificationData(BaseModel):
    """Domain qualification signals from a provider."""

    domain: str
    domain_authority: float | None = None
    spam_score: float | None = None
    monthly_traffic: float | None = None
    is_relevant: bool = True
    topics: list[str] = Field(default_factory=list)
    data_source: str = "fake"
    data_completeness: float = 0.0


@runtime_checkable
class OutreachDataProvider(Protocol):
    """Interface for outreach/contact-discovery data (§4.9).

    Adapter integration note: add real adapters for
    Hunter, BuzzStream, WhitePress, Prowly, or Cision.
    """

    def fetch_contacts(
        self, domain: str
    ) -> Result[list[ContactRecord], GrowthDataProviderError]: ...

    def fetch_domain_qualification(
        self, domain: str
    ) -> Result[DomainQualificationData, GrowthDataProviderError]: ...

    def name(self) -> str: ...
