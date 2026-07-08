"""Keyword analysis (§4.4). Observed density/placement + inferred AI targeting.

Density and placement are computed deterministically from the crawled text
(acceptance #3) — these are the hard ground truth the ``keyword_sanity_validator``
checks AI claims against. The focus keyphrase, intent, and gaps are inferred via
the ``keyword_analysis`` AI capability (skipped when no runner is injected).
"""

from __future__ import annotations

from intelligence.models.keyword_intelligence import (
    KeywordIntelligenceSection,
    KeywordPlacement,
    NamedEntity,
    SearchIntent,
)
from intelligence.services.base import AnalysisContext, AnalyzerService
from intelligence.services.text_extraction import keyword_density

__all__ = ["KeywordAnalysisService"]


class KeywordAnalysisService(AnalyzerService):
    section = "keyword_intelligence"

    def analyze(self, ctx: AnalysisContext) -> None:
        section = KeywordIntelligenceSection()
        # --- Observed: density (deterministic) ---
        density = keyword_density(ctx.extracted.words)
        section.keyword_density = density
        top_keywords = list(density.keys())

        # --- Inferred: AI targeting ---
        if ctx.runner is not None:
            ctx.prompt_context.top_keywords = top_keywords
            from intelligence.validation.context import ValidationContext

            vctx = ValidationContext(
                capability="keyword_analysis",
                observed_text=ctx.extracted.text,
                top_keywords=top_keywords,
            )
            result = ctx.runner.run(
                "keyword_analysis", ctx.prompt_context,
                page_id=ctx.page_id, validation_context=vctx,
            )
            ctx.warnings.extend(result.warnings)
            payload = result.payload
            if payload:
                section.primary_focus_keyphrase = payload.get("primary_focus_keyphrase")
                section.secondary_keyphrases = payload.get("secondary_keyphrases", [])
                section.related_semantic_keywords = payload.get("related_semantic_keywords", [])
                section.keyword_variations = payload.get("keyword_variations", [])
                section.missing_important_keywords = payload.get("missing_important_keywords", [])
                intent = payload.get("search_intent")
                if intent in {i.value for i in SearchIntent}:
                    section.search_intent = SearchIntent(intent)
                section.named_entities = [
                    NamedEntity(**e) if isinstance(e, dict) else NamedEntity(text=str(e))
                    for e in payload.get("named_entities", [])
                    if isinstance(e, dict)
                ]

        # --- Observed: placement (deterministic, uses focus keyphrase if known) ---
        section.keyword_placement = self._placement(ctx, section.primary_focus_keyphrase)
        ctx.ko.keyword_intelligence = section
        # Feed the focus keyphrase forward so downstream prompts can use it.
        ctx.prompt_context.primary_focus_keyphrase = section.primary_focus_keyphrase
        ctx.prompt_context.secondary_keyphrases = section.secondary_keyphrases

    def _placement(self, ctx: AnalysisContext, focus: str | None) -> KeywordPlacement:
        if not focus:
            return KeywordPlacement()
        f = focus.lower()
        page = ctx.page
        title = (page.title or "").lower()
        meta = (page.meta_description or "").lower()
        first_100 = " ".join(ctx.extracted.words[:100])
        h1 = " ".join(t for lvl, t in ctx.extracted.headings if lvl == 1).lower()
        return KeywordPlacement(
            in_title=f in title,
            in_h1=f in h1,
            in_first_100_words=f in first_100,
            in_meta_description=f in meta,
            in_url=self._slugify(f) in ctx.ko.identity.slug,
        )

    @staticmethod
    def _slugify(text: str) -> str:
        return "-".join(t for t in text.lower().split() if t)
