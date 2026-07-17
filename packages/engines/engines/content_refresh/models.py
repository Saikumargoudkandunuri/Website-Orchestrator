"""Typed outputs for the Content Refresh Engine."""
from __future__ import annotations

from pydantic import BaseModel, Field

__all__ = ["RefreshFinding", "ContentRefreshProposal", "ContentRefreshReport"]


class RefreshFinding(BaseModel):
    """A real, evidence-backed content-quality finding on one page."""

    page_url: str
    finding_type: str  # thin_content | duplicate_title | duplicate_heading | outdated | missing_faq
    severity: str = "medium"
    evidence: list[str] = Field(default_factory=list)


class ContentRefreshProposal(BaseModel):
    """A concrete structural-edit proposal to resolve one finding."""

    page_url: str
    finding_type: str
    operation: str  # update_heading | replace_content_block
    detail: dict
    reason: str


class ContentRefreshReport(BaseModel):
    site_id: str
    provenance: str = "observed_live_crawl"
    pages_analyzed: int = 0
    findings: list[RefreshFinding] = Field(default_factory=list)
    proposals: list[ContentRefreshProposal] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    def to_summary(self) -> dict:
        return {
            "pages_analyzed": self.pages_analyzed,
            "findings": len(self.findings),
            "proposals": len(self.proposals),
            "provenance": self.provenance,
        }
