"""Metadata section of the SEO Knowledge Object (§4.5, extended by §13.2/§13.3).

Each :class:`MetadataField` keeps the **observed** ``current_value`` strictly
separate from the **proposed** ``proposed_value`` (with reasoning), honoring the
Observation/Inference/Proposal rule (§1.3): a proposal is never conflated with
the fact on the page.

Milestone 2.1 adds editor-override semantics (§13.3): every ``MetadataField``
(and the new :class:`OgImageField`) records whether its value came from the
``system`` or a ``human``. Human overrides survive re-analysis unless explicitly
force-regenerated — the carry-forward logic lives in the analysis orchestrator.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

__all__ = [
    "OverrideSource",
    "MetadataField",
    "OgImageField",
    "OpenGraphData",
    "TwitterCardData",
    "RobotsDirective",
    "MetadataSection",
]


class OverrideSource(str, Enum):
    """Who last set a field's value (§13.3)."""

    SYSTEM = "system"
    HUMAN = "human"


class MetadataField(BaseModel):
    current_value: str | None = None  # observed
    proposed_value: str | None = None  # proposed
    proposed_reasoning: str | None = None
    character_count: int | None = None
    within_recommended_length: bool | None = None
    # --- Milestone 2.1 editor-override semantics (§13.3) ---
    override_source: OverrideSource = OverrideSource.SYSTEM
    overridden_at: datetime | None = None
    overridden_by: str | None = None


class OgImageField(BaseModel):
    """Open Graph image field with dimension validation (§13.2)."""

    current_value: str | None = None  # observed OG image URL, if any
    proposed_value: str | None = None  # proposed image URL/asset reference
    proposed_reasoning: str | None = None
    source_image_element_id: str | None = None  # links to ImageRecord.element_id
    dimensions_valid: bool | None = None  # validated against OG guideline (>=1200x630)
    # --- override semantics ---
    override_source: OverrideSource = OverrideSource.SYSTEM
    overridden_at: datetime | None = None
    overridden_by: str | None = None


class OpenGraphData(BaseModel):
    title: str | None = None  # observed raw og:title tag value
    description: str | None = None  # observed raw og:description tag value
    image: str | None = None  # observed raw og:image tag value
    type: str | None = None
    url: str | None = None
    # --- Milestone 2.1: independently editable social fields (§13.2) ---
    og_title: MetadataField = Field(default_factory=MetadataField)
    og_description: MetadataField = Field(default_factory=MetadataField)
    og_image: OgImageField = Field(default_factory=OgImageField)
    og_type: str | None = None


class TwitterCardData(BaseModel):
    card: str | None = None
    title: str | None = None
    description: str | None = None
    image: str | None = None


class RobotsDirective(BaseModel):
    index: bool = True
    follow: bool = True
    raw: str | None = None


class MetadataSection(BaseModel):
    seo_title: MetadataField = Field(default_factory=MetadataField)
    meta_description: MetadataField = Field(default_factory=MetadataField)
    open_graph: OpenGraphData = Field(default_factory=OpenGraphData)
    twitter_card: TwitterCardData = Field(default_factory=TwitterCardData)
    canonical: MetadataField = Field(default_factory=MetadataField)
    robots: RobotsDirective = Field(default_factory=RobotsDirective)
