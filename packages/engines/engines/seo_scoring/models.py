"""SEO Scoring Engine output models (§4.8).

Transparent, non-black-box composite scoring: every component exposes its value,
``data_completeness`` (honest about provider-dependent inputs), and ``notes``.
The scoring_version is bumped when factor weights change — mirroring M2.1's
ContentScore discipline.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

__all__ = [
    "ComponentScore",
    "SeoScoreBreakdown",
    "SeoScoreReport",
    "SCORING_VERSION",
]

SCORING_VERSION = "1.0.0"


class ComponentScore(BaseModel):
    """One component in the overall SEO score breakdown (§4.8)."""

    value: float                   # 0.0-100.0
    data_completeness: float = 1.0 # 0.0 = placeholder data; 1.0 = full real data
    notes: str = ""                # human-readable context, e.g. "based on fake_provider data"
    weight: float = 0.0


class SeoScoreBreakdown(BaseModel):
    """Full transparent breakdown of the composite SEO score (§4.8)."""

    component_scores: dict[str, ComponentScore] = Field(default_factory=dict)
    # Explicit components for the required score axes:
    # technical_score, content_score, keyword_score, authority_score,
    # internal_link_score, performance_score, accessibility_score, trust_score
    weights: dict[str, float] = Field(default_factory=dict)
    overall_score: float = 0.0
    scoring_version: str = SCORING_VERSION


class SeoScoreReport(BaseModel):
    """Per-page composite SEO score (§4.8).

    Runs AFTER Technical SEO, Content Intelligence, Keyword Intelligence,
    Site Architecture (link equity), and optionally Backlink/Topical Authority
    engines have produced their reports.
    """

    page_id: str
    site_id: str
    tenant_id: str
    version: int = 1
    breakdown: SeoScoreBreakdown = Field(default_factory=SeoScoreBreakdown)
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
