"""Deterministic content score (§13.2, §13.4).

The Rank-Math-style 0-100 content score is a **pure computation** over already-
observed/inferred fields — never an AI call — so it is fully deterministic and
transparent: every factor is listed with its pass/fail, weight, and explanation.
``scoring_version`` is bumped when the factor set/weights change.
"""

from __future__ import annotations

from datetime import datetime, timezone

from intelligence.models.content_intelligence import ContentScore, ContentScoreFactor
from intelligence.services.base import AnalysisContext, AnalyzerService

__all__ = ["ContentScoreService", "SCORING_VERSION"]

SCORING_VERSION = "1.0.0"


class ContentScoreService(AnalyzerService):
    section = "content_score"

    def analyze(self, ctx: AnalysisContext) -> None:
        ko = ctx.ko
        kw = ko.keyword_intelligence
        focus = (kw.primary_focus_keyphrase or "").strip()
        placement = kw.keyword_placement
        meta = ko.metadata
        content = ko.content_intelligence

        factors: list[ContentScoreFactor] = [
            self._factor(
                "focus_keyphrase_in_title", placement.in_title, 0.15,
                "Focus keyphrase appears in the SEO title",
            ),
            self._factor(
                "keyphrase_in_first_paragraph", placement.in_first_100_words, 0.1,
                "Focus keyphrase appears early in the content",
            ),
            self._factor(
                "keyphrase_in_meta_description", placement.in_meta_description, 0.1,
                "Focus keyphrase appears in the meta description",
            ),
            self._factor(
                "keyphrase_in_url", placement.in_url, 0.05,
                "Focus keyphrase appears in the URL",
            ),
            self._factor(
                "meta_description_present",
                bool((meta.meta_description.current_value or meta.meta_description.proposed_value)),
                0.1, "A meta description is present or proposed",
            ),
            self._factor(
                "content_length", content.word_count >= 300, 0.15,
                "Content has at least 300 words",
            ),
            self._factor(
                "single_h1", content.h1_analysis.count == 1, 0.1,
                "Page has exactly one H1",
            ),
            self._factor(
                "has_headings", len(content.heading_structure) >= 2, 0.05,
                "Page uses a heading structure",
            ),
            self._factor(
                "internal_links_present", len(ko.internal_seo.internal_links) > 0, 0.05,
                "Page has internal links",
            ),
            self._factor(
                "image_alt_present",
                self._all_images_have_alt(ko), 0.1,
                "All images have alt text",
            ),
            self._factor(
                "url_length_ok", ko.identity.url_analysis.length_characters <= 100, 0.05,
                "URL length is reasonable (<=100 chars)",
            ),
        ]
        # Focus keyphrase must exist for keyphrase factors to be meaningful.
        if not focus:
            for f in factors:
                if f.factor_name.startswith("keyphrase_") or f.factor_name.startswith("focus_"):
                    f.passed = False
                    f.explanation += " (no focus keyphrase set)"

        earned = sum(f.weight for f in factors if f.passed)
        total = sum(f.weight for f in factors) or 1.0
        score = int(round(100 * earned / total))

        ko.content_intelligence.content_score = ContentScore(
            score=score,
            breakdown=factors,
            computed_at=datetime.now(timezone.utc),
            scoring_version=SCORING_VERSION,
        )

    @staticmethod
    def _factor(name: str, passed: bool, weight: float, explanation: str) -> ContentScoreFactor:
        return ContentScoreFactor(
            factor_name=name, passed=passed, weight=weight, explanation=explanation
        )

    @staticmethod
    def _all_images_have_alt(ko) -> bool:
        images = ko.image_intelligence.images
        if not images:
            return True
        return all((img.current_alt_text or "").strip() for img in images)
