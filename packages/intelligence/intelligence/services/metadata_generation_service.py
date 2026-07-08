"""Metadata generation (§4.5, §13.2). Observed current values + proposed AI values.

Runs after keyword analysis so the focus keyphrase informs the meta/title/slug
proposals. Populates ``seo_title``, ``meta_description``, ``canonical`` current
values from the crawl, and proposes new values plus a slug and OG social fields
via the ``meta_generator`` / ``title_generator`` / ``slug_generator`` capabilities.
"""

from __future__ import annotations

from intelligence.models.metadata_intelligence import MetadataField
from intelligence.services.base import AnalysisContext, AnalyzerService

__all__ = ["MetadataGenerationService"]

_META_MIN, _META_MAX = 120, 160
_TITLE_MIN, _TITLE_MAX = 30, 60


class MetadataGenerationService(AnalyzerService):
    section = "metadata"

    def analyze(self, ctx: AnalysisContext) -> None:
        meta = ctx.ko.metadata
        page = ctx.page

        # --- Observed current values ---
        meta.seo_title.current_value = page.title
        meta.seo_title.character_count = len(page.title) if page.title else 0
        meta.meta_description.current_value = page.meta_description
        meta.meta_description.character_count = (
            len(page.meta_description) if page.meta_description else 0
        )
        meta.canonical.current_value = ctx.ko.identity.canonical_url

        if ctx.runner is None:
            return

        # --- Proposed values (AI) ---
        meta_res = ctx.runner.run("meta_generator", ctx.prompt_context, page_id=ctx.page_id)
        ctx.warnings.extend(meta_res.warnings)
        if meta_res.payload:
            self._apply(
                meta.meta_description,
                meta_res.payload.get("meta_description"),
                meta_res.payload.get("reasoning"),
                _META_MIN, _META_MAX,
            )

        title_res = ctx.runner.run("title_generator", ctx.prompt_context, page_id=ctx.page_id)
        ctx.warnings.extend(title_res.warnings)
        if title_res.payload:
            self._apply(
                meta.seo_title,
                title_res.payload.get("seo_title"),
                title_res.payload.get("reasoning"),
                _TITLE_MIN, _TITLE_MAX,
            )

        slug_res = self._run_slug(ctx)
        if slug_res:
            self._apply(ctx.ko.identity.proposed_slug, slug_res[0], slug_res[1], 3, 75)

        # OG social fields default from the proposed/observed metadata.
        og = meta.open_graph
        og.og_title.proposed_value = meta.seo_title.proposed_value or page.title
        og.og_description.proposed_value = (
            meta.meta_description.proposed_value or page.meta_description
        )

    def _run_slug(self, ctx: AnalysisContext):
        from intelligence.validation.context import ValidationContext

        vctx = ValidationContext(
            capability="slug_generator", existing_slugs=ctx.existing_slugs
        )
        res = ctx.runner.run(
            "slug_generator", ctx.prompt_context, page_id=ctx.page_id,
            validation_context=vctx,
        )
        ctx.warnings.extend(res.warnings)
        if res.payload:
            return res.payload.get("slug"), res.payload.get("reasoning")
        return None

    @staticmethod
    def _apply(
        field: MetadataField, value: str | None, reasoning: str | None,
        lo: int, hi: int,
    ) -> None:
        if not value:
            return
        field.proposed_value = value
        field.proposed_reasoning = reasoning
        field.character_count = len(value)
        field.within_recommended_length = lo <= len(value) <= hi
