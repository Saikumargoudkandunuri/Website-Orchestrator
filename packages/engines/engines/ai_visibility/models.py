"""AI Visibility / GEO (Generative Engine Optimization) engine models (§1.9 / §2.6 / §5 P6).

Tracks brand visibility inside AI-generated answers (Google AI Overviews,
ChatGPT, Perplexity, Gemini) and schema readiness for LLM citation eligibility.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

__all__ = [
    "AiMention",
    "CitationSource",
    "SchemaReadiness",
    "AiVisibilityReport",
]


class AiMention(BaseModel):
    """A brand mention detected in an AI output (§2.6 Brand Radar)."""
    query: str
    platform: str            # chatgpt | perplexity | gemini | google_ai_overview
    mentioned: bool = False
    sentiment: str | None = None   # positive | neutral | negative
    cited_url: str | None = None   # page LLM cited when mentioning brand
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CitationSource(BaseModel):
    """A content source type that LLMs tend to cite (§2.6)."""
    url: str
    content_type: str | None = None       # article | faq | documentation | product
    citation_count: int = 0


class SchemaReadiness(BaseModel):
    """Schema markup completeness for LLM citation eligibility (§1.2 AI/GEO)."""
    has_jsonld: bool = False
    has_article_schema: bool = False
    has_faq_schema: bool = False
    has_author_bio: bool = False
    has_organization_schema: bool = False
    readiness_score: float = 0.0   # 0.0-1.0
    gaps: list[str] = Field(default_factory=list)


class AiVisibilityReport(BaseModel):
    """Site-level AI visibility report (§5 P6)."""
    site_id: str
    tenant_id: str
    version: int = 1
    mentions: list[AiMention] = Field(default_factory=list)
    share_of_voice: float | None = None   # 0.0-1.0 across tracked queries
    citation_sources: list[CitationSource] = Field(default_factory=list)
    schema_readiness: SchemaReadiness = Field(default_factory=SchemaReadiness)
    ai_traffic_estimate: float | None = None
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
