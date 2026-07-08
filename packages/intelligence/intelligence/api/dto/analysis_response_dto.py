"""Response DTO for triggering analysis (§10)."""

from __future__ import annotations

from pydantic import BaseModel

from intelligence.models.knowledge_object import KnowledgeObject

__all__ = ["AnalyzeResponse"]


class AnalyzeResponse(BaseModel):
    """Result of ``POST /intelligence/pages/{page_id}/analyze``."""

    page_id: str
    version: int
    knowledge_object: KnowledgeObject
