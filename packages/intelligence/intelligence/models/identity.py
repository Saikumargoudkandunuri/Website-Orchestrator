"""Identity section of the SEO Knowledge Object (§4.3, extended by §13.2).

Pure **observation** for the core fields: everything here is measured from the
crawled page, not inferred by AI. It anchors the page in the site graph (URL,
canonical, slug, type, language, section, parent, breadcrumbs) so later agents
can address it without re-parsing HTML.

Milestone 2.1 adds a **proposed** SEO-friendly slug and an observed/inferred
``UrlAnalysis`` (Rank Math URL analysis parity).
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from intelligence.models.metadata_intelligence import MetadataField

__all__ = ["PageType", "UrlAnalysis", "IdentitySection"]


class PageType(str, Enum):
    """A page's role on the site. Extensible: unknown roles map to ``OTHER``."""

    HOME = "home"
    CATEGORY = "category"
    PRODUCT = "product"
    SERVICE = "service"
    BLOG_POST = "blog_post"
    LANDING_PAGE = "landing_page"
    CONTACT = "contact"
    ABOUT = "about"
    FAQ = "faq"
    OTHER = "other"


class UrlAnalysis(BaseModel):
    """Rank-Math-style URL analysis (§13.2). Source: mixed (observed + inferred)."""

    length_characters: int = 0  # observed
    contains_focus_keyphrase: bool = False  # observed, cross-checked with keywords
    contains_stop_words: bool = False  # observed
    readable_structure: bool = True  # observed (hyphenated, lowercase, no noise)
    depth: int = 0  # observed, path segment count
    issues: list[str] = Field(default_factory=list)  # inferred human-readable flags
    source: str = "mixed"


class IdentitySection(BaseModel):
    """Observed identity of a page within the site graph (§4.3)."""

    url: str
    canonical_url: str | None = None
    slug: str = ""  # observed
    proposed_slug: MetadataField = Field(default_factory=MetadataField)  # proposed (§13.2)
    page_type: PageType = PageType.OTHER
    language: str = "en"  # BCP-47
    site_section: str | None = None
    parent_page_id: str | None = None
    breadcrumbs: list[str] = Field(default_factory=list)
    url_analysis: UrlAnalysis = Field(default_factory=UrlAnalysis)  # §13.2
    source: str = "observed"
