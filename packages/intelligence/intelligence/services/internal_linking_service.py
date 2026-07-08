"""Internal SEO (§4.7, §13.2). Observed link graph + proposed internal/external links."""

from __future__ import annotations

from urllib.parse import urlsplit

from intelligence.identifiers import element_id_for
from intelligence.models.internal_seo import (
    BrokenLink,
    InternalLink,
    InternalSeoSection,
    SuggestedExternalLink,
    SuggestedInternalLink,
)
from intelligence.services.base import AnalysisContext, AnalyzerService

__all__ = ["InternalLinkingService"]


class InternalLinkingService(AnalyzerService):
    section = "internal_seo"

    def analyze(self, ctx: AnalysisContext) -> None:
        page = ctx.page
        host = urlsplit(page.url).netloc
        internal: list[InternalLink] = []
        broken: list[BrokenLink] = []
        for link in page.links:
            same_domain = urlsplit(link.url).netloc in ("", host)
            if same_domain:
                internal.append(
                    InternalLink(
                        target_url=link.url,
                        anchor_text=None,
                        element_id=element_id_for(ctx.page_id, "link", link.url),
                    )
                )
            if link.status_code is not None and 400 <= link.status_code <= 599:
                broken.append(
                    BrokenLink(
                        url=link.url,
                        status_code=link.status_code,
                        element_id=element_id_for(ctx.page_id, "link", link.url),
                    )
                )

        section = InternalSeoSection(
            internal_links=internal, broken_links=broken, orphan_page=False
        )

        if ctx.runner is not None:
            ctx.prompt_context.known_internal_urls = ctx.known_urls
            result = ctx.runner.run(
                "internal_linking", ctx.prompt_context, page_id=ctx.page_id
            )
            ctx.warnings.extend(result.warnings)
            payload = result.payload
            if payload:
                section.suggested_internal_links = [
                    SuggestedInternalLink(
                        target_url=s.get("target_url"),
                        suggested_anchor_text=s.get("suggested_anchor_text", ""),
                        reasoning=s.get("reasoning"),
                        confidence=s.get("confidence"),
                    )
                    for s in payload.get("suggested_internal_links", [])
                    if isinstance(s, dict)
                ]
                section.suggested_external_links = [
                    SuggestedExternalLink(
                        anchor_text_context=s.get("anchor_text_context", ""),
                        suggested_target_url=s.get("suggested_target_url"),
                        suggested_target_description=s.get("suggested_target_description", ""),
                        reasoning=s.get("reasoning", ""),
                        authority_rationale=s.get("authority_rationale", ""),
                        confidence=s.get("confidence"),
                    )
                    for s in payload.get("suggested_external_links", [])
                    if isinstance(s, dict)
                ]

        ctx.ko.internal_seo = section
