"""Content Intelligence section of the SEO Knowledge Object (§4.6).

Blends **observed** metrics (word count, readability, heading tree, first/last
paragraph) with **inferred** judgments (thin-content confirmation, topic gaps,
coverage/completeness scores, freshness). ``first_paragraph`` is immutable by
default (§4.12) because it often carries legally-sensitive or brand-defining
copy.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

__all__ = [
    "HeadingNode",
    "HeadingAnalysis",
    "DuplicateContentFlag",
    "ContentFreshness",
    "PillarContentFlag",
    "ContentScoreFactor",
    "ContentScore",
    "ContentIntelligenceSection",
]


class HeadingNode(BaseModel):
    level: int  # 1..6
    text: str
    element_id: str


class HeadingAnalysis(BaseModel):
    count: int = 0
    matches_focus_keyphrase: bool = False
    issues: list[str] = Field(default_factory=list)


class DuplicateContentFlag(BaseModel):
    matched_page_id: str
    similarity_score: float


class ContentFreshness(BaseModel):
    last_meaningful_change_at: datetime | None = None
    days_since_update: int | None = None
    staleness_flag: bool = False


class PillarContentFlag(BaseModel):
    """Rank-Math-style pillar content flag (§13.2). Inferred, human-overridable.

    ``linked_cluster_pages`` uses a simple keyword/topic-overlap heuristic this
    milestone — NOT full topic-cluster modeling (deferred, §14).
    """

    is_pillar_content: bool = False
    reasoning: str | None = None
    linked_cluster_pages: list[str] = Field(default_factory=list)  # heuristic
    source: str = "inferred"


class ContentScoreFactor(BaseModel):
    """One transparent, pass/fail factor contributing to the content score."""

    factor_name: str
    passed: bool
    weight: float
    explanation: str


class ContentScore(BaseModel):
    """Deterministic 0-100 content score (§13.2, §13.4).

    Never a black-box number: ``breakdown`` lists every factor, its pass/fail,
    and its weight. ``scoring_version`` is bumped when the scoring function
    changes so historical scores stay interpretable.
    """

    score: int = 0  # 0-100, deterministic composite (NOT an AI call)
    breakdown: list[ContentScoreFactor] = Field(default_factory=list)
    computed_at: datetime | None = None
    scoring_version: str = "1.0.0"


class ContentIntelligenceSection(BaseModel):
    word_count: int = 0  # observed
    reading_time_minutes: float = 0.0  # derived
    thin_content: bool = False  # inferred
    readability_score: float | None = None  # observed (Flesch)
    passive_voice_ratio: float | None = None  # observed
    avg_sentence_length: float | None = None  # observed
    avg_paragraph_length: float | None = None  # observed
    heading_structure: list[HeadingNode] = Field(default_factory=list)  # observed
    h1_analysis: HeadingAnalysis = Field(default_factory=HeadingAnalysis)
    first_paragraph: str | None = None  # observed, immutable by default
    last_paragraph: str | None = None  # observed
    duplicate_content: list[DuplicateContentFlag] = Field(default_factory=list)
    missing_topics: list[str] = Field(default_factory=list)  # inferred
    topic_coverage_score: float | None = None  # inferred
    semantic_completeness_score: float | None = None  # inferred
    content_freshness: ContentFreshness = Field(default_factory=ContentFreshness)
    # --- Milestone 2.1 (§13.2) ---
    pillar_content: PillarContentFlag = Field(default_factory=PillarContentFlag)
    content_score: ContentScore = Field(default_factory=ContentScore)
