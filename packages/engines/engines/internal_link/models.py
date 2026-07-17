"""Typed outputs for the Internal Link Engine."""
from __future__ import annotations

from pydantic import BaseModel, Field

__all__ = ["PageAuthority", "InternalLinkProposal", "InternalLinkReport"]


class PageAuthority(BaseModel):
    """A page's real position in the internal link graph."""

    url: str
    title: str | None = None
    authority_score: float = 0.0          # normalized PageRank (0..1), real
    inbound_internal_links: int = 0
    outbound_internal_links: int = 0
    is_orphan: bool = False               # zero resolved inbound internal links


class InternalLinkProposal(BaseModel):
    """A concrete, evidence-backed internal link to add.

    ``suggested_anchor`` is derived from the real target page (title/slug); it is
    a starting point for a human/approval step, not a fabricated optimization.
    """

    source_url: str
    target_url: str
    suggested_anchor: str
    reason: str
    evidence: list[str] = Field(default_factory=list)
    source_authority: float = 0.0
    target_authority: float = 0.0
    priority: str = "medium"              # high | medium | low


class InternalLinkReport(BaseModel):
    """The Internal Link Engine's typed result over a site's real crawl graph."""

    site_id: str
    provenance: str = "observed_live_crawl"
    pages_analyzed: int = 0
    internal_edges: int = 0
    orphan_count: int = 0
    weak_page_count: int = 0
    structure_score: float = 0.0
    authorities: list[PageAuthority] = Field(default_factory=list)
    proposals: list[InternalLinkProposal] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    def to_summary(self) -> dict:
        return {
            "pages_analyzed": self.pages_analyzed,
            "internal_edges": self.internal_edges,
            "orphan_count": self.orphan_count,
            "weak_page_count": self.weak_page_count,
            "structure_score": self.structure_score,
            "proposals": len(self.proposals),
            "provenance": self.provenance,
        }
