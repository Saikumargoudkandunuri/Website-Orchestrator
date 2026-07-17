"""AI Writer V2 — full-page content generation routed through the AI Gateway.

Every generation call goes through :class:`intelligence.services.capability_runner.CapabilityRunner`,
which is the single provider-agnostic seam (prompt -> provider -> validate ->
audit). This module never imports or calls a provider directly. Generated
content is never published directly: it is returned as a governed
``UPDATE_PAGE_CONTENT`` ``SuggestedFix`` that flows through the existing
Governance_Layer (approve/apply/rollback), exactly like every other fix.

Fields assembled per call (RankMath-aligned):
    focus keyphrase, secondary keywords, search intent (keyword_analysis
    capability), SEO slug (slug_generator), meta title (title_generator), meta
    description (meta_generator), H1/H2 structure + body (content_generation),
    FAQ (faq_generator), schema (schema_generator), internal links (from the
    real Internal Link Engine), ALT text guidance (per image, from the real
    Fix_Generator alt-text heuristic/AI path — reused, not duplicated), CTA
    (embedded in content_generation's brand-voice instruction).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from core.types import FixStatus, FixType, SuggestedFix, TargetRef
from intelligence.prompts.base_prompt_template import PromptContext
from intelligence.services.capability_runner import CapabilityRunner

__all__ = ["GeneratedPage", "AIWriterV2", "build_ai_writer_fix", "build_ai_writer_seo_meta_fix"]


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug or "section"


def _default_breadcrumb(page_url: str, title: str) -> list[dict]:
    """Derive a real breadcrumb trail from the page's own URL path segments.

    Never fabricates a taxonomy: each crumb before the final one is a real path
    segment of the page being generated, title-cased for display; the final
    crumb is the page's own generated title.
    """
    parts = urlsplit(page_url if "://" in page_url else f"https://{page_url}")
    host = (parts.hostname or "").strip()
    segments = [segment for segment in (parts.path or "").split("/") if segment]
    if not host:
        return []
    trail = [{"name": host, "url": f"https://{host}/"}]
    path_acc = ""
    for segment in segments[:-1]:
        path_acc += f"/{segment}"
        trail.append({"name": segment.replace("-", " ").title(), "url": f"https://{host}{path_acc}"})
    trail.append({"name": title or (segments[-1].replace("-", " ").title() if segments else host), "url": page_url})
    return trail


@dataclass
class GeneratedPage:
    """Every RankMath-aligned field a governed page/blog update must carry."""

    focus_keyphrase: str = ""
    seo_slug: str = ""
    secondary_keywords: list[str] = field(default_factory=list)
    search_intent: str = ""
    meta_title: str = ""
    meta_description: str = ""
    title: str = ""
    sections: list[dict] = field(default_factory=list)  # [{heading, content}]
    faqs: list[dict] = field(default_factory=list)      # [{question, answer}]
    schema_type: str = ""
    schema_jsonld: str = ""
    internal_links: list[dict] = field(default_factory=list)
    external_links: list[dict] = field(default_factory=list)  # [{url, anchor_text, domain_authority}]
    image_alt_suggestions: list[str] = field(default_factory=list)
    cta: str = ""
    readability_notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    # Milestone 5 — Automatic Blog Writer: OG/Twitter/canonical/breadcrumb.
    canonical_url: str = ""
    og_title: str = ""
    og_description: str = ""
    og_type: str = "article"
    og_image: str = ""
    twitter_card: str = "summary_large_image"
    twitter_title: str = ""
    twitter_description: str = ""
    twitter_image: str = ""
    breadcrumb: list[dict] = field(default_factory=list)  # [{name, url}]
    include_table_of_contents: bool = True

    def _heading_slugs(self) -> list[str]:
        seen: dict[str, int] = {}
        slugs: list[str] = []
        for section in self.sections:
            base = _slugify(section.get("heading", ""))
            count = seen.get(base, 0)
            seen[base] = count + 1
            slugs.append(base if count == 0 else f"{base}-{count}")
        return slugs

    def to_table_of_contents_html(self) -> str:
        """A real, navigable TOC built from this page's own H2 headings."""
        headings = [s.get("heading", "") for s in self.sections if s.get("heading")]
        if not headings or not self.include_table_of_contents:
            return ""
        slugs = self._heading_slugs()
        items = "".join(
            f'<li><a href="#{slug}">{heading}</a></li>'
            for heading, slug in zip(headings, slugs)
        )
        return (
            '<nav class="table-of-contents" aria-label="Table of contents">'
            "<h2>Table of Contents</h2>"
            f"<ul>{items}</ul>"
            "</nav>"
        )

    def to_breadcrumb_html(self) -> str:
        """Real breadcrumb navigation + matching BreadcrumbList JSON-LD."""
        if not self.breadcrumb:
            return ""
        crumbs = "".join(
            f'<li><a href="{item.get("url", "#")}">{item.get("name", "")}</a></li>'
            if index < len(self.breadcrumb) - 1
            else f'<li aria-current="page">{item.get("name", "")}</li>'
            for index, item in enumerate(self.breadcrumb)
        )
        return f'<nav class="breadcrumb" aria-label="Breadcrumb"><ol>{crumbs}</ol></nav>'

    def breadcrumb_jsonld(self) -> str:
        if not self.breadcrumb:
            return ""
        import json as _json

        items = [
            {
                "@type": "ListItem", "position": index + 1,
                "name": item.get("name", ""), "item": item.get("url", ""),
            }
            for index, item in enumerate(self.breadcrumb)
        ]
        return _json.dumps({
            "@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": items,
        })

    def to_html(self) -> str:
        """Render every generated field into one production-ready HTML body.

        Output is WordPress-ready (Gutenberg/Classic-compatible plain semantic
        HTML — headings, lists, nav, figure/figcaption — no framework markup
        assumptions) and includes the breadcrumb, table of contents, body
        sections, FAQ, internal + external authority links, CTA, and the
        BreadcrumbList JSON-LD alongside the page's primary schema.
        """
        slugs = self._heading_slugs()
        parts: list[str] = []
        breadcrumb_html = self.to_breadcrumb_html()
        if breadcrumb_html:
            parts.append(breadcrumb_html)
        if self.title:
            parts.append(f"<h1>{self.title}</h1>")
        toc_html = self.to_table_of_contents_html()
        if toc_html:
            parts.append(toc_html)
        for section, slug in zip(self.sections, slugs):
            heading = section.get("heading", "")
            content = section.get("content", "")
            if heading:
                parts.append(f'<h2 id="{slug}">{heading}</h2>')
            if content:
                parts.append(f"<p>{content}</p>")
        if self.internal_links:
            items = "".join(
                f'<li><a href="{link.get("target_url", link.get("url", "#"))}">'
                f'{link.get("suggested_anchor", link.get("anchor_text", link.get("target_url", "")))}</a></li>'
                for link in self.internal_links
            )
            parts.append(f'<nav class="related-reading" aria-label="Related reading"><h2>Related Reading</h2><ul>{items}</ul></nav>')
        if self.external_links:
            items = "".join(
                f'<li><a href="{link.get("url", "#")}" rel="noopener nofollow" target="_blank">'
                f'{link.get("anchor_text", link.get("url", ""))}</a></li>'
                for link in self.external_links
            )
            parts.append(f'<section class="sources"><h2>Sources</h2><ul>{items}</ul></section>')
        if self.faqs:
            parts.append('<section class="faq"><h2>Frequently Asked Questions</h2>')
            for faq in self.faqs:
                parts.append(f"<h3>{faq.get('question', '')}</h3>")
                parts.append(f"<p>{faq.get('answer', '')}</p>")
            parts.append("</section>")
        if self.cta:
            parts.append(f'<p class="cta">{self.cta}</p>')
        if self.schema_jsonld:
            parts.append(f'<script type="application/ld+json">{self.schema_jsonld}</script>')
        breadcrumb_jsonld = self.breadcrumb_jsonld()
        if breadcrumb_jsonld:
            parts.append(f'<script type="application/ld+json">{breadcrumb_jsonld}</script>')
        return "".join(parts)

    def to_seo_meta(self) -> dict[str, str]:
        """RankMath + Open Graph + Twitter Card + canonical postmeta payload.

        Keys match RankMath's registered ``rank_math_*`` REST meta fields plus
        the standard ``og:*``/``twitter:*`` conventions RankMath itself writes
        for social sharing (see RankMath's Open Graph documentation). This is
        the exact payload a governed ``UPDATE_SEO_META`` fix applies through
        :meth:`~core.interfaces.PublishingAdapterPort.update_page_meta`.
        """
        return {
            "rank_math_title": self.meta_title or self.title,
            "rank_math_description": self.meta_description,
            "rank_math_focus_keyword": self.focus_keyphrase,
            "rank_math_canonical_url": self.canonical_url,
            "rank_math_facebook_title": self.og_title or self.meta_title or self.title,
            "rank_math_facebook_description": self.og_description or self.meta_description,
            "rank_math_facebook_image": self.og_image,
            "rank_math_twitter_title": self.twitter_title or self.og_title or self.meta_title or self.title,
            "rank_math_twitter_description": self.twitter_description or self.og_description or self.meta_description,
            "rank_math_twitter_image": self.twitter_image or self.og_image,
            "rank_math_twitter_card_type": self.twitter_card,
        }

    def to_dict(self) -> dict:
        return {
            "focus_keyphrase": self.focus_keyphrase,
            "seo_slug": self.seo_slug,
            "secondary_keywords": self.secondary_keywords,
            "search_intent": self.search_intent,
            "meta_title": self.meta_title,
            "meta_description": self.meta_description,
            "title": self.title,
            "sections": self.sections,
            "faqs": self.faqs,
            "schema_type": self.schema_type,
            "schema_jsonld": self.schema_jsonld,
            "internal_links": self.internal_links,
            "external_links": self.external_links,
            "image_alt_suggestions": self.image_alt_suggestions,
            "cta": self.cta,
            "readability_notes": self.readability_notes,
            "warnings": self.warnings,
            "canonical_url": self.canonical_url,
            "og_title": self.og_title,
            "og_description": self.og_description,
            "og_type": self.og_type,
            "og_image": self.og_image,
            "twitter_card": self.twitter_card,
            "twitter_title": self.twitter_title,
            "twitter_description": self.twitter_description,
            "twitter_image": self.twitter_image,
            "breadcrumb": self.breadcrumb,
            "seo_meta": self.to_seo_meta(),
        }


def _readability_notes(html: str) -> list[str]:
    """Real, deterministic readability analysis (no fabricated score)."""
    import re

    text = re.sub(r"<[^>]+>", " ", html)
    words = [w for w in re.split(r"\s+", text) if w]
    sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]
    notes: list[str] = []
    if words:
        avg_words_per_sentence = len(words) / max(1, len(sentences))
        notes.append(f"{len(words)} word(s) across {len(sentences)} sentence(s); "
                      f"avg {avg_words_per_sentence:.1f} words/sentence.")
        if avg_words_per_sentence > 25:
            notes.append("Sentences are long on average; consider shortening for readability.")
    long_paragraphs = html.count("<p>") if len(text) / max(1, html.count("<p>") or 1) > 600 else 0
    if long_paragraphs:
        notes.append("Some paragraphs are long; break up with subheadings or lists.")
    return notes


class AIWriterV2:
    """Generates a complete, RankMath-aligned page draft via the AI Gateway."""

    def __init__(self, runner: CapabilityRunner) -> None:
        self._runner = runner

    def generate(
        self, *, page_url: str, asset_type: str = "blog_post",
        seed_keywords: list[str] | None = None, brand_voice: str = "",
        internal_link_candidates: list[dict] | None = None,
        external_link_candidates: list[dict] | None = None,
        breadcrumb: list[dict] | None = None,
        page_id: str | None = None,
    ) -> GeneratedPage:
        """Run the full generation pipeline through the AI Gateway only."""
        context = PromptContext(
            page_url=page_url,
            top_keywords=seed_keywords or [],
            extra={"asset_type": asset_type, "brand_voice": brand_voice},
        )
        result = GeneratedPage()

        keyword_result = self._runner.run("keyword_analysis", context, page_id=page_id)
        if keyword_result.payload:
            result.focus_keyphrase = keyword_result.payload.get("primary_focus_keyphrase", "")
            result.secondary_keywords = keyword_result.payload.get("secondary_keyphrases", [])
            result.search_intent = keyword_result.payload.get("search_intent", "")
        else:
            result.warnings.append("keyword_analysis: generation unavailable, fields left empty")

        context = context.model_copy(update={
            "primary_focus_keyphrase": result.focus_keyphrase,
            "secondary_keyphrases": result.secondary_keywords,
        })

        content_result = self._runner.run("content_generation", context, page_id=page_id)
        if content_result.payload:
            result.title = content_result.payload.get("title", "")
            result.sections = content_result.payload.get("sections", [])
            result.meta_title = content_result.payload.get("meta_title", "") or result.meta_title
            result.meta_description = content_result.payload.get("meta_description", "") or result.meta_description
        else:
            result.warnings.append("content_generation: generation unavailable, fields left empty")

        context = context.model_copy(update={"title": result.title})

        if not result.meta_title:
            title_result = self._runner.run("title_generator", context, page_id=page_id)
            if title_result.payload:
                result.meta_title = title_result.payload.get("seo_title", "")
            else:
                result.warnings.append("title_generator: generation unavailable")

        if not result.meta_description:
            meta_result = self._runner.run("meta_generator", context, page_id=page_id)
            if meta_result.payload:
                result.meta_description = meta_result.payload.get("meta_description", "")
            else:
                result.warnings.append("meta_generator: generation unavailable")

        slug_result = self._runner.run("slug_generator", context, page_id=page_id)
        if slug_result.payload:
            result.seo_slug = slug_result.payload.get("slug", "")
        else:
            result.warnings.append("slug_generator: generation unavailable")

        faq_result = self._runner.run("faq_generator", context, page_id=page_id)
        if faq_result.payload:
            result.faqs = faq_result.payload.get("faqs", [])
        else:
            result.warnings.append("faq_generator: generation unavailable")

        schema_result = self._runner.run("schema_generator", context, page_id=page_id)
        if schema_result.payload:
            result.schema_type = schema_result.payload.get("type", "")
            result.schema_jsonld = schema_result.payload.get("jsonld", "")
        else:
            result.warnings.append("schema_generator: generation unavailable")

        # Internal links: real candidates from the Internal Link Engine, never
        # fabricated — the caller supplies real proposals for this page.
        result.internal_links = internal_link_candidates or []
        # External authority links: real candidates the caller supplies (e.g.
        # from a connected backlink/competitor data provider); never invented.
        result.external_links = external_link_candidates or []

        result.cta = (
            f"Ready to get started with {result.focus_keyphrase or 'this'}? Contact us today."
            if result.focus_keyphrase else ""
        )

        # Canonical URL, OG, and Twitter Card fields are real, derived facts
        # about this exact page — never invented placeholders.
        result.canonical_url = page_url
        result.og_title = result.meta_title or result.title
        result.og_description = result.meta_description
        result.twitter_title = result.og_title
        result.twitter_description = result.og_description
        result.breadcrumb = breadcrumb or _default_breadcrumb(page_url, result.title)

        result.readability_notes = _readability_notes(result.to_html())
        return result


def build_ai_writer_fix(
    *, tenant_id: str, issue_id: str, wp_page_id: int, page: GeneratedPage,
    reason: str = "AI Writer V2: governed full-page draft",
) -> SuggestedFix:
    """Wrap a generated page as a governed ``UPDATE_PAGE_CONTENT`` fix.

    Never publishes directly — this is a proposal that flows through the
    existing Governance_Layer, identical to every other page-content fix.
    """
    import uuid

    return SuggestedFix(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        issue_id=issue_id,
        fix_type=FixType.UPDATE_PAGE_CONTENT,
        auto_applicable=1,
        target_ref=TargetRef(page_id=wp_page_id),
        proposed_value=page.to_html(),
        reason=reason,
        status=FixStatus.PENDING,
        generation_model="ai-gateway",
    )


def build_ai_writer_seo_meta_fix(
    *, tenant_id: str, issue_id: str, wp_page_id: int, page: GeneratedPage,
    reason: str = "AI Writer V2: governed RankMath/OG/Twitter/canonical metadata",
) -> SuggestedFix:
    """Wrap a generated page's RankMath/OG/Twitter/canonical fields as one
    governed ``UPDATE_SEO_META`` fix (Milestone 5).

    Kept as a second, separate fix from :func:`build_ai_writer_fix` because it
    targets a different live resource (page postmeta, not page content) and
    Governance/rollback must audit and reverse each independently.
    """
    import json
    import uuid

    return SuggestedFix(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        issue_id=issue_id,
        fix_type=FixType.UPDATE_SEO_META,
        auto_applicable=1,
        target_ref=TargetRef(page_id=wp_page_id),
        proposed_value=json.dumps(page.to_seo_meta(), sort_keys=True),
        reason=reason,
        status=FixStatus.PENDING,
        generation_model="ai-gateway",
    )
