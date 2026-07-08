"""Internal SEO section of the SEO Knowledge Object (§4.7).

Observed link graph facts (internal links, broken links, depth, orphan status —
all computed, never AI-guessed) plus **proposed** internal-link suggestions.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

__all__ = [
    "InternalLink",
    "BrokenLink",
    "SuggestedInternalLink",
    "SuggestedExternalLink",
    "InternalSeoSection",
]


class InternalLink(BaseModel):
    target_page_id: str | None = None
    target_url: str
    anchor_text: str | None = None
    element_id: str


class BrokenLink(BaseModel):
    url: str
    status_code: int | None = None
    element_id: str | None = None


class SuggestedInternalLink(BaseModel):
    target_page_id: str | None = None
    target_url: str | None = None
    suggested_anchor_text: str
    reasoning: str | None = None
    confidence: float | None = None


class SuggestedExternalLink(BaseModel):
    """Proposed outbound authoritative citation (§13.2).

    Higher hallucination risk than internal links: ``suggested_target_url`` is
    left ``None`` (description-only) unless the URL can be verified, per
    ``external_link_validator`` (§13.4).
    """

    anchor_text_context: str
    suggested_target_url: str | None = None  # proposed, nullable if unverifiable
    suggested_target_description: str = ""  # fallback when no confident URL
    reasoning: str = ""
    authority_rationale: str = ""  # why this is an EEAT-positive citation
    confidence: float | None = None
    source: str = "proposed"


class InternalSeoSection(BaseModel):
    internal_links: list[InternalLink] = Field(default_factory=list)  # observed
    orphan_page: bool = False  # inferred (computed from graph)
    link_depth: int | None = None  # observed/computed
    broken_links: list[BrokenLink] = Field(default_factory=list)  # observed
    suggested_internal_links: list[SuggestedInternalLink] = Field(
        default_factory=list
    )  # proposed
    suggested_external_links: list[SuggestedExternalLink] = Field(
        default_factory=list
    )  # proposed (§13.2)
