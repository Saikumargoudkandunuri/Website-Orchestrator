"""Reputation Management Engine models (§4.4)."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

__all__ = [
    "Review",
    "ReviewsSummary",
    "SentimentBreakdown",
    "NegativeReviewFlag",
    "ReputationResponseDraft",
    "ReputationReport",
]


@dataclass(frozen=True)
class Review:
    """Individual review from any platform."""
    review_id: str
    platform: str  # "google", "facebook", "trustpilot", "yelp", etc.
    rating: float  # 1.0-5.0
    text: str
    author: str
    published_at: datetime
    sentiment_score: float  # -1.0 (negative) to 1.0 (positive), AI-computed
    sentiment_label: str  # "positive", "neutral", "negative"


@dataclass(frozen=True)
class ReviewsSummary:
    """Aggregate review statistics."""
    total_reviews: int
    average_rating: float
    rating_distribution: dict[int, int]  # {5: 120, 4: 45, 3: 10, 2: 5, 1: 2}
    recent_reviews: list[Review]  # Last N reviews


@dataclass(frozen=True)
class SentimentBreakdown:
    """AI-computed sentiment analysis across all reviews."""
    positive_count: int
    neutral_count: int
    negative_count: int
    average_sentiment: float  # -1.0 to 1.0
    sentiment_trend: str  # "improving", "stable", "declining"


@dataclass(frozen=True)
class NegativeReviewFlag:
    """Flagged negative review requiring attention."""
    review: Review
    urgency: str  # "critical", "high", "medium"
    flagged_keywords: list[str]  # Words triggering flag (e.g., "refund", "lawsuit")
    recommended_action: str


@dataclass(frozen=True)
class ReputationResponseDraft:
    """
    AI-generated response suggestion (§4.4).
    
    Uses shared BrandVoiceProfile. Goes through lightweight approval flow
    (pending → approved) before being sent (sending integration out of scope).
    """
    draft_id: str
    review_ref: str  # Review this responds to
    response_text: str
    tone: str  # From BrandVoiceProfile
    brand_voice_profile_ref: str
    ai_invocations: list[dict]  # AIInvocation audit trail
    status: str  # "draft", "pending", "approved", "rejected"
    created_at: datetime
    approved_at: datetime | None = None


@dataclass(frozen=True)
class ReputationReport:
    """
    Reputation Management Report (§4.4).
    
    Sitewide/per-location scope.
    Provider-fake: review ingestion, brand mentions.
    REAL: sentiment analysis against fixture/provider-supplied review text.
    """
    site_id: str
    location_id: str | None  # None = sitewide, else specific location
    reviews_summary: ReviewsSummary
    sentiment_breakdown: SentimentBreakdown
    negative_review_flags: list[NegativeReviewFlag]
    response_drafts: list[ReputationResponseDraft]
    reputation_score: dict[str, Any]  # SeoScoreBreakdown-shaped
    computed_at: datetime
    version: int
    data_source: str = "provider_fake+ai"  # Reviews are fake, sentiment analysis is real
    data_completeness: float = 0.5  # Honest about provider-fake review data
