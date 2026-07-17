"""Typed outputs for the Page Lifecycle Engine."""
from __future__ import annotations

from pydantic import BaseModel, Field

__all__ = ["LifecycleDecision", "PageLifecycleReport"]


class LifecycleDecision(BaseModel):
    """One real, evidence-backed page-lifecycle decision."""

    action: str  # create | edit | delete | merge | make_pillar | expand_cluster
    page_url: str | None = None          # subject page (edit/delete/merge/make_pillar)
    merge_into_url: str | None = None    # canonical target when action == merge
    proposed_url: str | None = None      # target URL/slug when action == create
    reason: str
    evidence: list[str] = Field(default_factory=list)
    priority: str = "medium"


class PageLifecycleReport(BaseModel):
    site_id: str
    provenance: str = "observed_live_crawl"
    pages_analyzed: int = 0
    decisions: list[LifecycleDecision] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    def to_summary(self) -> dict:
        return {
            "pages_analyzed": self.pages_analyzed,
            "decisions": len(self.decisions),
            "provenance": self.provenance,
        }
