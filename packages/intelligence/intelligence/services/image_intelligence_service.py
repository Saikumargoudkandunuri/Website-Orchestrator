"""Image intelligence (§4.8). Observed images + proposed AI alt text.

The proposed ``ai_suggested_alt_text`` reuses Milestone 1's ``update_alt_text``
fix pipeline once approved (via the M2 fix generators). A deterministic
``image_seo_score`` composites simple observed signals.
"""

from __future__ import annotations

from intelligence.identifiers import element_id_for
from intelligence.models.image_intelligence import (
    ImageIntelligenceSection,
    ImageRecord,
)
from intelligence.services.base import AnalysisContext, AnalyzerService

__all__ = ["ImageIntelligenceService"]


class ImageIntelligenceService(AnalyzerService):
    section = "image_intelligence"

    def analyze(self, ctx: AnalysisContext) -> None:
        records: list[ImageRecord] = []
        for image in ctx.page.images:
            element_id = element_id_for(ctx.page_id, "image", image.filename)
            records.append(
                ImageRecord(
                    element_id=element_id,
                    image_url=image.filename,
                    filename=image.filename,
                    current_alt_text=image.alt_text,
                    image_seo_score=self._score(image.alt_text, image.filename),
                )
            )

        missing = [r for r in records if not (r.current_alt_text or "").strip()]
        if ctx.runner is not None and missing:
            ctx.prompt_context.images = [
                {"element_id": r.element_id, "filename": r.filename, "alt": r.current_alt_text}
                for r in missing
            ]
            result = ctx.runner.run("image_alt", ctx.prompt_context, page_id=ctx.page_id)
            ctx.warnings.extend(result.warnings)
            payload = result.payload
            if payload:
                by_id = {r.element_id: r for r in records}
                proposals = payload.get("alt_texts", [])
                # Match by element_id when present, else fill missing in order.
                unmatched = [p for p in proposals if not p.get("element_id")]
                for p in proposals:
                    eid = p.get("element_id")
                    if eid and eid in by_id:
                        by_id[eid].ai_suggested_alt_text = p.get("alt_text")
                for record, p in zip(missing, unmatched):
                    if record.ai_suggested_alt_text is None:
                        record.ai_suggested_alt_text = p.get("alt_text")

        ctx.ko.image_intelligence = ImageIntelligenceSection(images=records)

    @staticmethod
    def _score(alt: str | None, filename: str) -> float:
        score = 0.0
        if (alt or "").strip():
            score += 0.7
        if filename and "-" in filename:  # descriptive, hyphenated filename
            score += 0.3
        return round(score, 2)
