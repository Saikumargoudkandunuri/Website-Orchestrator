"""Response DTOs for the intelligence API (§10).

The full :class:`KnowledgeObject` is returned directly (it is already a typed
Pydantic model FastAPI can serialize); this module adds the lightweight
version-history and content-score response shapes.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from intelligence.models.content_intelligence import ContentScore
from intelligence.models.knowledge_object import KnowledgeObject

__all__ = ["VersionSummary", "KnowledgeObject", "ContentScore"]


class VersionSummary(BaseModel):
    """One entry in a page's KnowledgeObject version history (no full payload)."""

    version: int
    created_at: datetime
    crawl_id: str | None = None
