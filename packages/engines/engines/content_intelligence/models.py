"""Content Intelligence Engine output models (§4.4).

Extends Milestone 2's ContentIntelligenceSection with finer-grained analysis.
The AiContentScore is explicitly labeled as inference (holistic AI judgment),
kept distinct from Milestone 2.1's deterministic ContentScore.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

__all__ = [
    "DuplicateFragment",
    "EntityCoverageResult",
    "QuestionCoverageResult",
    "AiContentScore",
    "ContentEngineReport",
]


class DuplicateFragment(BaseModel):
    """A paragraph/section duplicated on another page (§4.4, finer than M2's whole-page dupe)."""

    fragment_hash: str                      # deterministic hash of normalised fragment text
    fragment_excerpt: str | None = None     # first 200 chars
    matched_page_ids: list[str] = Field(default_factory=list)
    similarity_score: float = 1.0
    source: str = "observed"


class EntityCoverageResult(BaseModel):
    """Named entity presence vs absence analysis (§4.4)."""

    entities_present: list[str] = Field(default_factory=list)
    entities_missing: list[str] = Field(default_factory=list)
    coverage_score: float = 0.0   # 0.0-1.0; proportion of expected entities present
    source: str = "inferred"


class QuestionCoverageResult(BaseModel):
    """Does the page answer the questions users are likely asking? (§4.4)."""

    questions_answered: list[str] = Field(default_factory=list)
    questions_missing: list[str] = Field(default_factory=list)
    coverage_score: float = 0.0
    source: str = "inferred"


class AiContentScore(BaseModel):
    """AI-reasoned holistic content quality score (§4.4).

    Explicitly **distinct** from Milestone 2.1's deterministic ``ContentScore``
    (which is a pure computation). This score is AI-inferred; both are stored
    and cross-referenced in the engine report so they are never conflated.
    """

    score: float = 0.0             # 0.0-100.0; AI-holistic quality judgment
    reasoning: str | None = None   # AI-produced rationale (inference)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    source: str = "inferred"       # explicitly labeled as AI inference


class ContentEngineReport(BaseModel):
    """Content Intelligence engine output for one page (§4.4)."""

    page_id: str
    site_id: str
    tenant_id: str
    version: int = 1
    duplicate_fragments: list[DuplicateFragment] = Field(default_factory=list)
    semantic_richness_score: float | None = None    # inferred
    entity_coverage: EntityCoverageResult = Field(default_factory=EntityCoverageResult)
    question_coverage: QuestionCoverageResult = Field(default_factory=QuestionCoverageResult)
    missing_sections: list[str] = Field(default_factory=list)  # AI-inferred structural gaps
    content_depth_score: float | None = None         # inferred
    ai_content_score: AiContentScore = Field(default_factory=AiContentScore)
    optimization_suggestions: list[str] = Field(default_factory=list)
    #: M2.1 deterministic ContentScore reference (cross-referenced, not duplicated).
    m2_content_score_ref: str | None = None    # e.g. "KnowledgeObject/{page_id}/version/{v}"
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ContentBrief(BaseModel):
    """Pre-writing SEO brief from top-10 SERP analysis (§1.6.3 SEO Content Template)."""
    target_keyword: str
    recommended_word_count: int | None = None
    semantic_keywords: list[str] = Field(default_factory=list)
    readability_target: float | None = None
    recommended_backlink_sources: list[str] = Field(default_factory=list)
    section_recommendations: dict[str, int] = Field(default_factory=dict)  # section -> target chars
    title_recommendation: str | None = None
    meta_description_recommendation: str | None = None
    schema_suggestions: list[str] = Field(default_factory=list)
    competitor_urls: list[str] = Field(default_factory=list)


class FreshnessStatus(BaseModel):
    """Content freshness monitoring (§5 P4 Content freshness)."""
    page_id: str
    last_updated: datetime | None = None
    days_since_update: int | None = None
    is_stale: bool = False            # True if not updated in 12+ months
    stale_threshold_days: int = 365
    recommendation: str | None = None
