"""Backlink Intelligence Engine output models (§4.6).

Architecture-only this milestone for provider-dependent data. The
``broken_backlinks`` sub-capability is implemented for real (§4.6 requirement):
backlinks pointing to now-404 pages on our site can be computed from our own
Technical SEO Engine's findings without needing a real backlink provider.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

# Reuse the provider-agnostic transfer records defined in shared interface.
from engines.shared.provider_abstraction.seo_data_provider_interface import (
    BacklinkRecord,
    ReferringDomain,
)

__all__ = [
    "ToxicLinkFlag",
    "BrokenBacklink",
    "LinkOpportunity",
    "BacklinkIntelligenceReport",
]


class ToxicLinkFlag(BaseModel):
    """A backlink flagged as potentially toxic/spammy (§4.6)."""

    source_url: str
    reason: str | None = None
    spam_score: float | None = None    # provider-signal when available
    data_source: str = "heuristic"


class BrokenBacklink(BaseModel):
    """A backlink pointing to a 404/broken page on our site (§4.6).

    This sub-capability is computed *today* from our own Technical SEO
    Engine findings — no external provider needed.
    """

    source_url: str
    target_url: str    # our URL that is now broken
    anchor_text: str | None = None
    last_seen: str | None = None
    source: str = "observed"   # real, derived from own site data


class LinkOpportunity(BaseModel):
    """A proposed link-building opportunity (§4.6)."""

    target_url: str | None = None      # our page to build links to
    reason: str | None = None
    authority_rationale: str | None = None
    source: str = "proposed"


class BacklinkIntelligenceReport(BaseModel):
    """Sitewide backlink intelligence report (§4.6, architecture-only for provider data)."""

    site_id: str
    tenant_id: str
    version: int = 1
    backlinks: list[BacklinkRecord] = Field(default_factory=list)
    referring_domains: list[ReferringDomain] = Field(default_factory=list)
    anchor_text_distribution: dict[str, int] = Field(default_factory=dict)
    authority_score: float | None = None   # null when on fake provider
    toxic_links: list[ToxicLinkFlag] = Field(default_factory=list)
    broken_backlinks: list[BrokenBacklink] = Field(default_factory=list)  # real today
    link_opportunities: list[LinkOpportunity] = Field(default_factory=list)
    #: Always set — see §4.5 data_source pattern.
    data_source: str = "fake_provider"
    data_completeness: float = 0.0
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
