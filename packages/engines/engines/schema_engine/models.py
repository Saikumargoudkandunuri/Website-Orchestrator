"""Typed outputs for the Schema Engine."""
from __future__ import annotations

from pydantic import BaseModel, Field

__all__ = ["SchemaGap", "SchemaProposal", "SchemaReport"]


class SchemaGap(BaseModel):
    """A missing or incomplete schema type detected on a real page."""

    page_url: str
    missing_type: str
    reason: str
    evidence: list[str] = Field(default_factory=list)


class SchemaProposal(BaseModel):
    """A concrete JSON-LD payload built only from fields observed on the page."""

    page_url: str
    schema_type: str
    data: dict
    reason: str


class SchemaReport(BaseModel):
    """Schema Engine result over a site's real crawled pages."""

    site_id: str
    provenance: str = "observed_live_crawl"
    pages_analyzed: int = 0
    gaps: list[SchemaGap] = Field(default_factory=list)
    proposals: list[SchemaProposal] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    def to_summary(self) -> dict:
        return {
            "pages_analyzed": self.pages_analyzed,
            "gaps": len(self.gaps),
            "proposals": len(self.proposals),
            "provenance": self.provenance,
        }
