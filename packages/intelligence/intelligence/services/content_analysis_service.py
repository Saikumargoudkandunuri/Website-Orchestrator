"""Content analysis (§4.6). Observed metrics + inferred AI coverage judgments."""

from __future__ import annotations

from intelligence.identifiers import element_id_for
from intelligence.models.content_intelligence import (
    ContentIntelligenceSection,
    HeadingAnalysis,
    HeadingNode,
)
from intelligence.services.base import AnalysisContext, AnalyzerService

__all__ = ["ContentAnalysisService"]

_WORDS_PER_MINUTE = 220.0


class ContentAnalysisService(AnalyzerService):
    section = "content_intelligence"

    def analyze(self, ctx: AnalysisContext) -> None:
        extracted = ctx.extracted
        word_count = ctx.page.word_count or len(extracted.words)
        section = ContentIntelligenceSection(
            word_count=word_count,
            reading_time_minutes=round(word_count / _WORDS_PER_MINUTE, 2),
            readability_score=self._readability(ctx),
            heading_structure=self._headings(ctx),
            h1_analysis=self._h1_analysis(ctx),
            first_paragraph=extracted.paragraphs[0] if extracted.paragraphs else None,
            last_paragraph=extracted.paragraphs[-1] if extracted.paragraphs else None,
            avg_sentence_length=self._avg_sentence_length(extracted.text),
            avg_paragraph_length=self._avg_paragraph_length(extracted.paragraphs),
        )
        # Threshold-based thin-content flag (observed); AI can confirm/override.
        section.thin_content = word_count < 300

        if ctx.runner is not None:
            result = ctx.runner.run(
                "content_analysis", ctx.prompt_context, page_id=ctx.page_id
            )
            ctx.warnings.extend(result.warnings)
            payload = result.payload
            if payload:
                if "thin_content" in payload:
                    section.thin_content = bool(payload["thin_content"])
                section.missing_topics = payload.get("missing_topics", [])
                section.topic_coverage_score = payload.get("topic_coverage_score")
                section.semantic_completeness_score = payload.get("semantic_completeness_score")

        ctx.ko.content_intelligence = section

    def _headings(self, ctx: AnalysisContext) -> list[HeadingNode]:
        nodes: list[HeadingNode] = []
        for level, text in ctx.extracted.headings:
            nodes.append(
                HeadingNode(
                    level=level,
                    text=text,
                    element_id=element_id_for(ctx.page_id, "heading", f"{level}:{text}"),
                )
            )
        return nodes

    def _h1_analysis(self, ctx: AnalysisContext) -> HeadingAnalysis:
        h1s = [t for lvl, t in ctx.extracted.headings if lvl == 1]
        issues: list[str] = []
        if len(h1s) == 0:
            issues.append("page has no H1")
        elif len(h1s) > 1:
            issues.append(f"page has {len(h1s)} H1s; exactly one is recommended")
        focus = (ctx.ko.keyword_intelligence.primary_focus_keyphrase or "").lower()
        matches = bool(focus) and any(focus in h.lower() for h in h1s)
        return HeadingAnalysis(count=len(h1s), matches_focus_keyphrase=matches, issues=issues)

    def _readability(self, ctx: AnalysisContext) -> float | None:
        from intelligence.services.text_extraction import flesch_reading_ease

        return flesch_reading_ease(ctx.extracted.text)

    @staticmethod
    def _avg_sentence_length(text: str) -> float | None:
        import re

        sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]
        words = re.findall(r"[a-zA-Z']+", text)
        if not sentences:
            return None
        return round(len(words) / len(sentences), 2)

    @staticmethod
    def _avg_paragraph_length(paragraphs: list[str]) -> float | None:
        if not paragraphs:
            return None
        total_words = sum(len(p.split()) for p in paragraphs)
        return round(total_words / len(paragraphs), 2)
