"""Typed outputs for the Campaign Planner Engine (Milestone 5, item 7).

A campaign is a *named grouping and sequencing* of work the platform's other
governed engines already produce — never a new fabricated action of its own.
Blog/topic clusters come from the real Topical Authority + Site Architecture
engines; internal-linking campaigns from the real Internal Link Engine;
authority-building from the same topic graph; GEO/AI-Overview campaigns from
the real AI Visibility engine's schema-readiness gaps; product-launch and
seasonal campaigns from the account's own onboarding-collected business
profile (CMO memory) — never invented industry data.
"""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

__all__ = ["CampaignPlan", "CampaignPlannerReport"]

#: The eight campaign types the litmus test in the steering doc names.
CAMPAIGN_TYPES = (
    "blog_cluster",
    "topic_cluster",
    "internal_linking",
    "authority_building",
    "geo_optimization",
    "ai_overview_optimization",
    "product_launch",
    "seasonal",
)


class CampaignPlan(BaseModel):
    """One concrete, evidence-backed campaign grouping real work."""

    campaign_type: str  # one of CAMPAIGN_TYPES
    title: str
    reason: str
    evidence: list[str] = Field(default_factory=list)
    #: Real target pages/urls or entity names this campaign concerns.
    target_pages: list[str] = Field(default_factory=list)
    #: Rough count of underlying governed actions this campaign would need
    #: (e.g. N supporting articles, M internal links) — a sequencing hint for
    #: the Editorial Calendar, not a fabricated metric.
    estimated_action_count: int = 0
    priority: str = "medium"  # high | medium | low
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CampaignPlannerReport(BaseModel):
    site_id: str
    provenance: str = "observed_site_data"
    campaigns: list[CampaignPlan] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    def to_summary(self) -> dict:
        return {
            "campaigns": len(self.campaigns),
            "provenance": self.provenance,
            "by_type": {
                t: sum(1 for c in self.campaigns if c.campaign_type == t)
                for t in CAMPAIGN_TYPES
                if any(c.campaign_type == t for c in self.campaigns)
            },
        }
