"""Typed outputs for the Programmatic SEO Engine."""
from __future__ import annotations

from pydantic import BaseModel, Field

__all__ = ["ProgrammaticPagePlan", "ProgrammaticSeoReport"]


class ProgrammaticPagePlan(BaseModel):
    """One concrete, real-data-backed landing page to create."""

    # service | city | category | comparison | product | location | industry
    # | pricing | faq
    page_type: str
    slug: str
    title: str
    entity: str          # the real service/city/category/competitor name this page targets
    reason: str
    template_vars: dict = Field(default_factory=dict)


class ProgrammaticSeoReport(BaseModel):
    site_id: str
    provenance: str = "observed_site_data"
    plans: list[ProgrammaticPagePlan] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    def to_summary(self) -> dict:
        return {"plans": len(self.plans), "provenance": self.provenance}
