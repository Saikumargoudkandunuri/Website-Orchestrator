"""Shared interface for third-party SEO data providers (§1.4, §4.5, §4.6).

No concrete provider is wired this milestone. The interface is designed so that
a Majestic, Ahrefs, or Search Atlas adapter can be dropped in without touching
any engine business logic — a strict config-driven swap, identical in discipline
to Milestone 2's AIProvider abstraction.

Future adapters to implement (named per spec §4.6):
- MajesticBacklinkProvider
- AhrefsDataProvider
- SearchAtlasProvider
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

from core.results import Result
from engines.errors import EngineDataProviderError

__all__ = [
    "CompetitorPage",
    "CompetitorKeyword",
    "CompetitorBacklink",
    "BacklinkRecord",
    "ReferringDomain",
    "CompetitorDataProvider",
    "BacklinkDataProvider",
]


# --- Competitor data models --------------------------------------------------

class CompetitorPage(BaseModel):
    url: str
    title: str | None = None
    estimated_traffic: float | None = None
    ranking_keywords: list[str] = Field(default_factory=list)
    topic: str | None = None


class CompetitorKeyword(BaseModel):
    keyword: str
    competitor_position: int | None = None
    our_position: int | None = None
    estimated_volume: float | None = None
    difficulty: float | None = None


class CompetitorBacklink(BaseModel):
    source_url: str
    target_url: str
    anchor_text: str | None = None
    domain_authority: float | None = None


# --- Backlink data models ----------------------------------------------------

class BacklinkRecord(BaseModel):
    source_url: str
    target_url: str
    anchor_text: str | None = None
    first_seen: str | None = None     # ISO-8601 date string
    last_seen: str | None = None
    link_type: str = "dofollow"       # dofollow | nofollow | ugc | sponsored
    domain_authority: float | None = None


class ReferringDomain(BaseModel):
    domain: str
    backlink_count: int = 0
    authority_score: float | None = None
    first_seen: str | None = None
    is_toxic: bool = False


# --- Provider protocols ------------------------------------------------------

@runtime_checkable
class CompetitorDataProvider(Protocol):
    """Interface for competitor intelligence data (§4.5).

    TODO(competitor-provider-integration): implement a real provider adapter
    (e.g. SearchAtlas, Ahrefs, or custom competitor-scraping) by subclassing
    and registering this protocol.
    """

    def fetch_competitor_pages(
        self, competitor_domain: str, topic: str
    ) -> Result[list[CompetitorPage], EngineDataProviderError]: ...

    def fetch_competitor_keywords(
        self, competitor_domain: str
    ) -> Result[list[CompetitorKeyword], EngineDataProviderError]: ...

    def fetch_competitor_backlinks(
        self, competitor_domain: str
    ) -> Result[list[CompetitorBacklink], EngineDataProviderError]: ...

    def name(self) -> str: ...


@runtime_checkable
class BacklinkDataProvider(Protocol):
    """Interface for backlink intelligence data (§4.6).

    TODO(backlink-provider-integration): implement a real provider adapter
    (e.g. Majestic, Ahrefs, or Search Atlas) by subclassing and registering.
    """

    def fetch_backlinks(
        self, domain: str
    ) -> Result[list[BacklinkRecord], EngineDataProviderError]: ...

    def fetch_referring_domains(
        self, domain: str
    ) -> Result[list[ReferringDomain], EngineDataProviderError]: ...

    def name(self) -> str: ...
