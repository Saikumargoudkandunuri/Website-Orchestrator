"""Reputation Management services."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone

from core.results import Err, Ok, Result
from growth.errors import GrowthAnalysisError
from growth.reputation_management.models import (
    NegativeReviewFlag,
    ReputationReport,
    ReputationResponseDraft,
    Review,
    ReviewsSummary,
    SentimentBreakdown,
)
from growth.shared.brand_voice_profile import BrandVoiceProfile
from growth.shared.provider_abstraction.reputation_data_provider_interface import ReputationDataProvider
from intelligence.ai.provider_interface import AICompletionRequest, AIProvider

__all__ = ["ReputationService"]


class ReputationService:
    """Analyze reviews with provider-abstracted ingestion and AI sentiment."""

    def __init__(
        self,
        provider: ReputationDataProvider,
        ai_provider: AIProvider,
        brand_voice_profile: BrandVoiceProfile | None = None,
    ) -> None:
        self._provider = provider
        self._ai = ai_provider
        self._brand_voice = brand_voice_profile

    def analyze(
        self,
        site_id: str,
        location_id: str | None = None,
    ) -> Result[ReputationReport, GrowthAnalysisError]:
        reviews_result = self._provider.fetch_reviews(site_id, location_id)
        if reviews_result.is_err:
            return Err(GrowthAnalysisError(f"Failed to fetch reviews: {reviews_result.unwrap_err()}"))

        reviews = self._analyze_sentiment_batch(reviews_result.unwrap())
        summary = self._build_reviews_summary(reviews)
        sentiment = self._build_sentiment_breakdown(reviews)
        flags = self._flag_negative_reviews(reviews)
        drafts = self._generate_response_drafts(flags)
        report = ReputationReport(
            site_id=site_id,
            location_id=location_id,
            reviews_summary=summary,
            sentiment_breakdown=sentiment,
            negative_review_flags=flags,
            response_drafts=drafts,
            reputation_score=self._compute_reputation_score(summary, sentiment, flags),
            computed_at=datetime.now(timezone.utc),
            version=1,
        )
        return Ok(report)

    def _analyze_sentiment_batch(self, raw_reviews: list) -> list[Review]:
        reviews: list[Review] = []
        for raw in raw_reviews:
            text = getattr(raw, "text", "")
            rating = float(getattr(raw, "rating", 0.0))
            sentiment_score, sentiment_label = self._ai_sentiment(text, rating)
            reviews.append(Review(
                review_id=getattr(raw, "review_id", ""),
                platform=getattr(raw, "platform", "unknown"),
                rating=rating,
                text=text,
                author=getattr(raw, "author_name", ""),
                published_at=getattr(raw, "date", datetime.now(timezone.utc)),
                sentiment_score=sentiment_score,
                sentiment_label=sentiment_label,
            ))
        return reviews

    def _ai_sentiment(self, review_text: str, rating: float) -> tuple[float, str]:
        request = AICompletionRequest(
            prompt=self._build_sentiment_prompt(review_text),
            max_tokens=100,
            temperature=0.0,
            json_mode=True,
            metadata={"capability": "sentiment_analysis", "prompt_version": "1.0.0"},
        )
        result = self._ai.complete(request)
        if result.is_ok:
            return self._parse_sentiment_response(result.unwrap().raw_text)
        return self._heuristic_sentiment(rating)

    def _build_sentiment_prompt(self, review_text: str) -> str:
        return (
            "Analyze this customer review. Return JSON with score from -1.0 to 1.0 "
            f"and label positive, neutral, or negative. Review: {review_text!r}"
        )

    def _parse_sentiment_response(self, response: str) -> tuple[float, str]:
        try:
            data = json.loads(response.strip())
            score = float(data.get("score", 0.0))
            label = str(data.get("label", "neutral"))
            if label not in {"positive", "neutral", "negative"}:
                label = "neutral"
            return max(-1.0, min(1.0, score)), label
        except Exception:
            lowered = response.lower()
            if "positive" in lowered:
                return 0.7, "positive"
            if "negative" in lowered:
                return -0.7, "negative"
            return 0.0, "neutral"

    def _heuristic_sentiment(self, rating: float) -> tuple[float, str]:
        if rating >= 4.0:
            return 0.8, "positive"
        if rating >= 3.0:
            return 0.0, "neutral"
        return -0.8, "negative"

    def _build_reviews_summary(self, reviews: list[Review]) -> ReviewsSummary:
        if not reviews:
            return ReviewsSummary(0, 0.0, {}, [])
        ratings = [r.rating for r in reviews]
        return ReviewsSummary(
            total_reviews=len(reviews),
            average_rating=sum(ratings) / len(ratings),
            rating_distribution=dict(Counter(int(r.rating) for r in reviews)),
            recent_reviews=sorted(reviews, key=lambda r: r.published_at, reverse=True)[:10],
        )

    def _build_sentiment_breakdown(self, reviews: list[Review]) -> SentimentBreakdown:
        if not reviews:
            return SentimentBreakdown(0, 0, 0, 0.0, "stable")
        counts = Counter(r.sentiment_label for r in reviews)
        avg = sum(r.sentiment_score for r in reviews) / len(reviews)
        return SentimentBreakdown(
            positive_count=counts.get("positive", 0),
            neutral_count=counts.get("neutral", 0),
            negative_count=counts.get("negative", 0),
            average_sentiment=avg,
            sentiment_trend="stable",
        )

    def _flag_negative_reviews(self, reviews: list[Review]) -> list[NegativeReviewFlag]:
        critical = {"refund", "lawsuit", "fraud", "scam", "terrible", "worst"}
        high = {"angry", "disappointed", "unacceptable", "never again"}
        flags: list[NegativeReviewFlag] = []
        for review in reviews:
            if review.sentiment_label != "negative":
                continue
            text = review.text.lower()
            flagged = [word for word in critical if word in text]
            urgency = "critical" if flagged else "high" if any(word in text for word in high) else "medium"
            flags.append(NegativeReviewFlag(
                review=review,
                urgency=urgency,
                flagged_keywords=flagged,
                recommended_action=self._recommend_action(urgency),
            ))
        return flags

    def _recommend_action(self, urgency: str) -> str:
        if urgency == "critical":
            return "Immediate response required. Escalate to management and offer direct support."
        if urgency == "high":
            return "Respond within 24 hours with a personalized acknowledgement."
        return "Respond within 48 hours and acknowledge the concern."

    def _generate_response_drafts(self, negative_flags: list[NegativeReviewFlag]) -> list[ReputationResponseDraft]:
        drafts: list[ReputationResponseDraft] = []
        for flag in [f for f in negative_flags if f.urgency in {"critical", "high"}][:5]:
            request = AICompletionRequest(
                prompt=self._build_response_prompt(flag.review),
                max_tokens=200,
                temperature=0.4,
                metadata={"capability": "reputation_response", "prompt_version": "1.0.0"},
            )
            result = self._ai.complete(request)
            if result.is_err:
                continue
            drafts.append(ReputationResponseDraft(
                draft_id=f"draft-{flag.review.review_id}",
                review_ref=flag.review.review_id,
                response_text=result.unwrap().raw_text.strip(),
                tone=self._brand_voice.tone_descriptors[0] if self._brand_voice and self._brand_voice.tone_descriptors else "professional",
                brand_voice_profile_ref=getattr(self._brand_voice, "profile_id", "default"),
                ai_invocations=[{"model": result.unwrap().model}],
                status="draft",
                created_at=datetime.now(timezone.utc),
            ))
        return drafts

    def _build_response_prompt(self, review: Review) -> str:
        brand_context = self._brand_voice.to_prompt_context() if self._brand_voice else ""
        return f"{brand_context}\nGenerate a professional response to this review: {review.text}"

    def _compute_reputation_score(
        self,
        reviews_summary: ReviewsSummary,
        sentiment_breakdown: SentimentBreakdown,
        negative_flags: list[NegativeReviewFlag],
    ) -> dict:
        rating_score = (reviews_summary.average_rating - 1.0) / 4.0 if reviews_summary.total_reviews else 0.5
        sentiment_score = (sentiment_breakdown.average_sentiment + 1.0) / 2.0
        volume_score = min(reviews_summary.total_reviews / 100.0, 1.0)
        response_readiness = 1.0 if not any(f.urgency == "critical" for f in negative_flags) else 0.5
        overall = rating_score * 0.35 + sentiment_score * 0.30 + volume_score * 0.15 + response_readiness * 0.20
        return {
            "overall": round(overall, 2),
            "breakdown": {
                "average_rating": round(rating_score, 2),
                "sentiment_quality": round(sentiment_score, 2),
                "review_volume": round(volume_score, 2),
                "response_readiness": round(response_readiness, 2),
            },
            "weights": {
                "average_rating": 0.35,
                "sentiment_quality": 0.30,
                "review_volume": 0.15,
                "response_readiness": 0.20,
            },
        }