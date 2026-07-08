"""Competitor Intelligence Engine output models (§4.5).

Architecture-only this milestone: every field that would require real competitor
data is nullable/empty and ``data_source`` is always ``"fake_provider"`` until
a real CompetitorDataProvider is plugged in.  ``data_source`` propagates through
to SEO Scoring / Opportunity engines so they never assert confident numbers
built on placeholder data.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

__all__ = [
    "KeywordGap",
    "ContentGap",
    "TechnicalGap",
    "PageGap",
    "CompetitorIntelligenceReport",
]


class KeywordGap(BaseModel):
    """A keyword the competitor ranks for that we don't."""

    keyword: str
    competitor_position: int | None = None
    our_position: int | None = None
    estimated_volume: float | None = None
    source: str = "inferred"


class ContentGap(BaseModel):
    """A topic/section the competitor covers that we don't."""

    topic: str
    competitor_url: str | None = None
    our_coverage: float = 0.0  # 0.0 = entirely missing
    source: str = "inferred"


class TechnicalGap(BaseModel):
    """A technical SEO advantage the competitor has that we lack."""

    check_name: str          # aligned to TechnicalFinding.check_name taxonomy
    competitor_passes: bool = True
    we_pass: bool = False
    description: str | None = None
    source: str = "inferred"


class PageGap(BaseModel):
    """A page/page-type the competitor has that we entirely lack."""

    topic: str
    competitor_url: str | None = None
    estimated_traffic: float | None = None
    source: str = "inferred"


class CompetitorIntelligenceReport(BaseModel):
    """Sitewide competitor intelligence report (§4.5, architecture-only)."""

    site_id: str
    tenant_id: str
    version: int = 1
    competitor_domain: str = ""
    keyword_gaps: list[KeywordGap] = Field(default_factory=list)
    content_gaps: list[ContentGap] = Field(default_factory=list)
    technical_gaps: list[TechnicalGap] = Field(default_factory=list)
    authority_gap_score: float | None = None
    backlink_gap_summary: list[str] = Field(default_factory=list)
    topic_gap_summary: list[str] = Field(default_factory=list)
    page_gaps: list[PageGap] = Field(default_factory=list)
    visibility_gap_score: float | None = None
    #: Always set — consumers must check before treating output as ground truth.
    data_source: str = "fake_provider"
    data_completeness: float = 0.0   # 0.0 = entirely placeholder; 1.0 = full real data
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
