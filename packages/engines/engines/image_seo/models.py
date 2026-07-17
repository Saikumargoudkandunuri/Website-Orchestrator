"""Typed outputs for the Image SEO Engine."""
from __future__ import annotations

from pydantic import BaseModel, Field

__all__ = ["ImageFinding", "ImageProposal", "ImageSeoReport"]


class ImageFinding(BaseModel):
    """A real, evidence-backed image-markup deficiency on one page."""

    page_url: str
    src: str
    finding_type: str  # missing_alt | poor_filename | missing_caption | missing_lazy_loading | missing_dimensions
    severity: str = "medium"
    evidence: str = ""


class ImageProposal(BaseModel):
    """A concrete structural-edit proposal to resolve one finding (never alt text)."""

    page_url: str
    src: str
    finding_type: str
    loading: str | None = None
    width: str | None = None
    height: str | None = None
    caption: str | None = None
    reason: str = ""


class ImageSeoReport(BaseModel):
    page_url: str
    provenance: str = "observed_live_page"
    images_analyzed: int = 0
    findings: list[ImageFinding] = Field(default_factory=list)
    proposals: list[ImageProposal] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    def to_summary(self) -> dict:
        return {
            "images_analyzed": self.images_analyzed,
            "findings": len(self.findings),
            "proposals": len(self.proposals),
            "provenance": self.provenance,
        }
