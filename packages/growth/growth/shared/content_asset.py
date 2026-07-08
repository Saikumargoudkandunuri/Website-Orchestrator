"""ContentAsset model and governance extension (§2.2, §4.1.4).

Extends Milestone 1's governance state machine with a new ``ContentAsset`` entity
that flows through the SAME state machine, plus one new intermediate state,
``in_review``, sitting between ``Pending`` and ``Approved``.

This is the only schema-level extension to Milestone 1 permitted in this
milestone — strictly additive (new state, new entity type). The existing ``Fix``
flow for small atomic changes continues to work completely unchanged.

State machine:
  draft → pending → [in_review] → approved → published → verified → closed
                                            ↓
                                         rejected
                               (at any state) → failed

The ``in_review`` state is OPTIONAL per asset_type — configurable, not hardcoded.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

__all__ = [
    "ContentAssetType",
    "ContentAssetStatus",
    "ContentSection",
    "MetadataSection",
    "SchemaBlock",
    "ContentPayload",
    "ContentAsset",
    "ContentAssetHistoryEntry",
    # Config
    "ASSET_TYPES_REQUIRING_REVIEW",
]


# --- Asset types ---

class ContentAssetType(str, Enum):
    BLOG_POST = "blog_post"
    LANDING_PAGE = "landing_page"
    SERVICE_PAGE = "service_page"
    LOCATION_PAGE = "location_page"
    PRODUCT_PAGE = "product_page"
    CATEGORY_PAGE = "category_page"
    FAQ_PAGE = "faq_page"
    COMPARISON_PAGE = "comparison_page"
    PILLAR_PAGE = "pillar_page"
    CLUSTER_PAGE = "cluster_page"


# --- Status (extended from Milestone 1 FixStatus) ---

class ContentAssetStatus(str, Enum):
    DRAFT = "draft"
    PENDING = "pending"
    IN_REVIEW = "in_review"   # NEW state — only for large content requiring editorial review
    APPROVED = "approved"
    PUBLISHED = "published"
    VERIFIED = "verified"
    CLOSED = "closed"
    REJECTED = "rejected"
    FAILED = "failed"


#: Asset types that require the ``in_review`` state by default.
#: This is configurable per asset_type — override at the organization/site level.
ASSET_TYPES_REQUIRING_REVIEW: frozenset[ContentAssetType] = frozenset({
    ContentAssetType.BLOG_POST,
    ContentAssetType.LANDING_PAGE,
    ContentAssetType.SERVICE_PAGE,
    ContentAssetType.PILLAR_PAGE,
    ContentAssetType.LOCATION_PAGE,
    ContentAssetType.COMPARISON_PAGE,
})


# --- Content payload models ---

class ContentSection(BaseModel):
    """One section of generated content."""

    section_type: str  # e.g. "intro", "body", "conclusion", "faq", "cta"
    heading: str | None = None
    content: str = ""
    word_count: int = 0


class MetadataSection(BaseModel):
    """SEO metadata for a generated asset."""

    meta_title: str | None = None
    meta_description: str | None = None
    slug: str | None = None
    canonical_url: str | None = None
    og_title: str | None = None
    og_description: str | None = None


class SchemaBlock(BaseModel):
    """A JSON-LD schema block."""

    schema_type: str  # e.g. "Article", "LocalBusiness", "FAQPage"
    jsonld: str = ""  # serialized JSON-LD string


class ContentPayload(BaseModel):
    """The typed content payload for a generated ContentAsset.

    The primary output of the AI Content Generation Engine.
    """

    title: str
    body_sections: list[ContentSection] = Field(default_factory=list)
    meta: MetadataSection = Field(default_factory=MetadataSection)
    schema_blocks: list[SchemaBlock] = Field(default_factory=list)
    cta: str | None = None
    language: str = "en"  # BCP-47
    writing_style: str = "professional"
    brand_voice_profile_ref: str | None = None  # BrandVoiceProfile id/site_id
    word_count: int = 0
    generation_reasoning: str | None = None


# --- History entry (reuses M1's FixHistoryEntry pattern) ---

class ContentAssetHistoryEntry(BaseModel):
    """An audit trail entry for a ContentAsset state transition.

    Reuses Milestone 1's FixHistoryEntry concept — same pattern, different entity.
    No new audit mechanism is introduced.
    """

    id: str
    content_asset_id: str
    from_status: ContentAssetStatus | None = None
    to_status: ContentAssetStatus
    actor: str
    rationale: str
    notes: str | None = None
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# --- ContentAsset entity ---

class ContentAsset(BaseModel):
    """A full content asset governed by the extended state machine.

    Additive to Milestone 1's Digital Twin — new entity type, same governance
    pattern (state transitions, audit history, Publisher interface).
    """

    id: str
    tenant_id: str
    organization_id: str | None = None
    client_id: str | None = None
    site_id: str
    page_id: str | None = None  # null for net-new pages not yet existing on the site

    asset_type: ContentAssetType
    status: ContentAssetStatus = ContentAssetStatus.DRAFT

    content_payload: ContentPayload
    generation_source_id: str | None = None  # GeneratedArtifact.id ref

    reviewer: str | None = None
    review_notes: str | None = None

    history: list[ContentAssetHistoryEntry] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    approved_at: datetime | None = None
    published_at: datetime | None = None
    verified_at: datetime | None = None

    failure_reason: str | None = None

    def requires_review(
        self,
        review_required_types: frozenset[ContentAssetType] | None = None,
    ) -> bool:
        """Return True if this asset type requires the in_review state."""
        check = review_required_types if review_required_types is not None else ASSET_TYPES_REQUIRING_REVIEW
        return self.asset_type in check

    def transition(
        self,
        new_status: ContentAssetStatus,
        actor: str,
        rationale: str,
        notes: str | None = None,
        entry_id: str | None = None,
    ) -> "ContentAsset":
        """Return a new ContentAsset with status transitioned and history appended."""
        import uuid

        now = datetime.now(timezone.utc)
        entry = ContentAssetHistoryEntry(
            id=entry_id or uuid.uuid4().hex,
            content_asset_id=self.id,
            from_status=self.status,
            to_status=new_status,
            actor=actor,
            rationale=rationale,
            notes=notes,
            occurred_at=now,
        )
        updates: dict[str, Any] = {
            "status": new_status,
            "updated_at": now,
            "history": list(self.history) + [entry],
        }
        if new_status == ContentAssetStatus.APPROVED:
            updates["approved_at"] = now
        elif new_status == ContentAssetStatus.PUBLISHED:
            updates["published_at"] = now
        elif new_status == ContentAssetStatus.VERIFIED:
            updates["verified_at"] = now
        return self.model_copy(update=updates)
