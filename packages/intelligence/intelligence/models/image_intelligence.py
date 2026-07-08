"""Image Intelligence section of the SEO Knowledge Object (§4.8).

Per-image records blending **observed** attributes (url, filename, current alt,
caption) with **proposed**/**inferred** enrichment. ``ai_suggested_alt_text``
reuses Milestone 1's ``update_alt_text`` fix pipeline once approved.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

__all__ = ["ImageRecord", "ImageIntelligenceSection"]


class ImageRecord(BaseModel):
    element_id: str
    image_url: str
    filename: str
    current_alt_text: str | None = None  # observed
    ai_suggested_alt_text: str | None = None  # proposed
    caption: str | None = None  # observed
    compression_suggestion: str | None = None  # inferred
    image_seo_score: float | None = None  # inferred composite


class ImageIntelligenceSection(BaseModel):
    images: list[ImageRecord] = Field(default_factory=list)
