"""Shared analysis context passed to every analyzer service (§8.1).

Each analyzer takes this bundle, reads the raw crawl data / partial
KnowledgeObject / injected AI runner it needs, and populates its own section on
``ctx.ko`` in place. Deterministic analyzers ignore ``ctx.runner`` entirely.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.types import CrawledPage
from intelligence.models.knowledge_object import KnowledgeObject
from intelligence.prompts.base_prompt_template import PromptContext
from intelligence.services.capability_runner import CapabilityRunner
from intelligence.services.text_extraction import ExtractedContent

__all__ = ["AnalysisContext", "AnalyzerService"]


@dataclass
class AnalysisContext:
    tenant_id: str
    page_id: str
    page: CrawledPage
    extracted: ExtractedContent
    ko: KnowledgeObject
    prompt_context: PromptContext
    runner: CapabilityRunner | None = None  # None => AI-backed steps are skipped
    known_urls: list[str] = field(default_factory=list)
    existing_slugs: set[str] = field(default_factory=set)
    #: When set, only these capabilities/sections run (subset analysis, §10).
    enabled_sections: set[str] | None = None
    warnings: list[str] = field(default_factory=list)

    def section_enabled(self, name: str) -> bool:
        return self.enabled_sections is None or name in self.enabled_sections


class AnalyzerService:
    """Interface every analyzer implements."""

    #: Section name used for subset selection and ordering.
    section: str = ""

    def analyze(self, ctx: AnalysisContext) -> None:  # pragma: no cover - interface
        raise NotImplementedError
