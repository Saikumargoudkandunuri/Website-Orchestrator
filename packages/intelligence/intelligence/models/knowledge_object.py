"""The composed, versioned SEO Knowledge Object (§4.2, §4.12).

A ``KnowledgeObject`` is the durable, per-page unit of persistent understanding
that distinguishes this system from stateless scanners. It is **append-only and
versioned**: each analysis produces a new ``version`` for a ``page_id`` rather
than overwriting the prior one, so future agents can reason about change over
time. It composes the nine typed sections plus an AI summary, and carries a
first-class, machine-enforced ``immutable_fields`` list (§4.12) that the
validation pipeline uses to reject proposals targeting locked field paths.
"""

from __future__ import annotations

from datetime import datetime, timezone

from enum import Enum

from pydantic import BaseModel, Field

from intelligence.models.content_intelligence import ContentIntelligenceSection
from intelligence.models.eeat import EeatSection
from intelligence.models.identity import IdentitySection
from intelligence.models.image_intelligence import ImageIntelligenceSection
from intelligence.models.internal_seo import InternalSeoSection
from intelligence.models.keyword_intelligence import KeywordIntelligenceSection
from intelligence.models.metadata_intelligence import MetadataSection
from intelligence.models.schema_intelligence import SchemaIntelligenceSection
from intelligence.models.technical_seo import TechnicalSeoSection

__all__ = [
    "PrioritizedImprovement",
    "SeoRecommendationStatus",
    "SeoRecommendationPriority",
    "SeoRecommendation",
    "FieldOverride",
    "AiIntelligenceSummary",
    "KnowledgeObject",
    "DEFAULT_IMMUTABLE_FIELDS",
]

#: Sensible default immutable field paths (§4.12). These must never be
#: auto-overwritten by a proposal service or AI output. A future "lock this
#: field" API will let owners extend this per page; for now it is seeded
#: programmatically.
DEFAULT_IMMUTABLE_FIELDS: tuple[str, ...] = (
    "identity.canonical_url",
    "metadata.canonical",
    "content_intelligence.first_paragraph",
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PrioritizedImprovement(BaseModel):
    """A ranked improvement recommendation (part of the AI summary)."""

    title: str
    rationale: str | None = None
    priority: int = 0  # lower = higher priority
    capability: str | None = None  # which AI capability could act on it


class SeoRecommendationStatus(str, Enum):
    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"


class SeoRecommendationPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SeoRecommendation(BaseModel):
    """Rank-Math-style, checklist-shaped, per-factor recommendation (§13.2).

    Distinct from the broader ``improvement_priorities``: this is the concrete,
    per-factor pass/warning/fail checklist an editor sees.
    """

    factor: str  # aligned to ContentScoreFactor taxonomy where applicable
    status: SeoRecommendationStatus
    recommendation_text: str
    priority: SeoRecommendationPriority = SeoRecommendationPriority.MEDIUM
    related_fix_type: str | None = None  # names the FixGenerator that resolves it


class FieldOverride(BaseModel):
    """Registry entry recording a human override of a field path (§13.3)."""

    source: str = "human"  # "system" | "human"
    overridden_at: datetime | None = None
    overridden_by: str | None = None


class AiIntelligenceSummary(BaseModel):
    """The AI's holistic read of the page (§4.12) — all **inferred**.

    ``do_not_change`` is the human-readable counterpart to the machine-enforced
    :attr:`KnowledgeObject.immutable_fields`.
    """

    page_purpose: str | None = None
    target_audience: str | None = None
    business_goal: str | None = None
    competitive_positioning: str | None = None  # nullable until competitor data exists
    user_expectations: str | None = None
    search_engine_expectations: str | None = None
    key_gaps: list[str] = Field(default_factory=list)
    improvement_priorities: list[PrioritizedImprovement] = Field(default_factory=list)
    do_not_change: list[str] = Field(default_factory=list)
    # --- Milestone 2.1 (§13.2): Rank-Math-style per-factor SEO checklist ---
    seo_recommendations: list[SeoRecommendation] = Field(default_factory=list)


class KnowledgeObject(BaseModel):
    """One versioned, per-page unit of persistent SEO understanding (§4.2)."""

    id: str
    page_id: str  # stable, addressable page identifier (see repository)
    tenant_id: str
    version: int
    created_at: datetime = Field(default_factory=_utc_now)
    crawl_id: str | None = None

    identity: IdentitySection
    keyword_intelligence: KeywordIntelligenceSection = Field(
        default_factory=KeywordIntelligenceSection
    )
    metadata: MetadataSection = Field(default_factory=MetadataSection)
    content_intelligence: ContentIntelligenceSection = Field(
        default_factory=ContentIntelligenceSection
    )
    internal_seo: InternalSeoSection = Field(default_factory=InternalSeoSection)
    image_intelligence: ImageIntelligenceSection = Field(
        default_factory=ImageIntelligenceSection
    )
    schema_intelligence: SchemaIntelligenceSection = Field(
        default_factory=SchemaIntelligenceSection
    )
    technical_seo: TechnicalSeoSection = Field(default_factory=TechnicalSeoSection)
    eeat: EeatSection = Field(default_factory=EeatSection)
    ai_summary: AiIntelligenceSummary = Field(default_factory=AiIntelligenceSummary)

    immutable_fields: list[str] = Field(
        default_factory=lambda: list(DEFAULT_IMMUTABLE_FIELDS)
    )
    # --- Milestone 2.1 (§13.3): uniform registry of human-overridden field
    # paths (covers both MetadataField-shaped and scalar fields). The analysis
    # orchestrator carries these forward on re-analysis unless force-regenerated.
    overrides: dict[str, FieldOverride] = Field(default_factory=dict)
