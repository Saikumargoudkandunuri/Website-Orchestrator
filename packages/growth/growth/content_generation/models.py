"""Content Generation Engine output models (§4.1)."""
from __future__ import annotations
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from growth.shared.content_asset import ContentAssetType, ContentPayload

__all__ = ["ContentGenerationRequest", "ContentGenerationReport"]


class ContentGenerationRequest(BaseModel):
    """A request to generate a specific content asset."""
    site_id: str
    page_id: str | None = None
    asset_type: ContentAssetType = ContentAssetType.BLOG_POST
    topic: str = ""
    target_keyword: str | None = None
    language: str = "en"
    writing_style: str = "professional"
    word_count_target: int = 800
    brand_voice_profile_ref: str | None = None
    # References to upstream findings (by ID, not re-derived)
    missing_sections_ref: list[str] = Field(default_factory=list)
    missing_topics_ref: list[str] = Field(default_factory=list)
    context: dict = Field(default_factory=dict)
    tenant_id: str = ""
    organization_id: str | None = None
    client_id: str | None = None


class ContentGenerationReport(BaseModel):
    """Content Generation engine output — wraps a generated ContentAsset draft."""
    site_id: str
    tenant_id: str
    content_asset_id: str  # ID of the created ContentAsset
    asset_type: str
    generation_request_summary: str = ""
    version: int = 1
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    data_source: str = "ai_generation"
    data_completeness: float = 1.0
