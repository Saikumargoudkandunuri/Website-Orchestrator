"""Shared helpers for rendering a :class:`PromptContext` into prompt text.

Keeps the concrete prompt templates small and consistent: they compose a
capability-specific instruction with a compact, human-readable rendering of the
already-extracted page context (never raw HTML).
"""

from __future__ import annotations

from intelligence.prompts.base_prompt_template import PromptContext

__all__ = ["render_context", "JSON_ONLY_INSTRUCTION"]

#: Appended to every system prompt so providers without a strict JSON mode still
#: return parseable JSON (the parser also tolerates markdown fences).
JSON_ONLY_INSTRUCTION = (
    "Respond with a single valid JSON object only. No prose, no markdown fences."
)


def render_context(ctx: PromptContext, *, include_content: bool = True) -> str:
    """Render the relevant, already-extracted page context as compact text."""
    lines: list[str] = []
    lines.append(f"URL: {ctx.page_url}")
    if ctx.page_type:
        lines.append(f"Page type: {ctx.page_type}")
    if ctx.language:
        lines.append(f"Language: {ctx.language}")
    if ctx.title:
        lines.append(f"Title: {ctx.title}")
    if ctx.meta_description:
        lines.append(f"Meta description: {ctx.meta_description}")
    if ctx.slug:
        lines.append(f"Slug: {ctx.slug}")
    if ctx.primary_focus_keyphrase:
        lines.append(f"Focus keyphrase: {ctx.primary_focus_keyphrase}")
    if ctx.secondary_keyphrases:
        lines.append("Secondary keyphrases: " + ", ".join(ctx.secondary_keyphrases))
    if ctx.top_keywords:
        lines.append("Top observed keywords: " + ", ".join(ctx.top_keywords[:15]))
    if ctx.headings:
        lines.append("Headings: " + " | ".join(ctx.headings[:20]))
    lines.append(f"Word count: {ctx.word_count}")
    if include_content and ctx.first_paragraph:
        lines.append(f"First paragraph: {ctx.first_paragraph}")
    if include_content and ctx.content_excerpt:
        lines.append(f"Content excerpt: {ctx.content_excerpt}")
    return "\n".join(lines)
