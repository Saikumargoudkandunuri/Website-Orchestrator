"""Analysis orchestrator — the single entry point for page analysis (§8.1).

Given a page's crawl data, it decides which analyzers run and **in what order**,
assembles their outputs into a new :class:`KnowledgeObject` version, applies the
human-override carry-forward (§13.3), and persists the result append-only.

Dependency order (explicit DAG, not implicit call order):

1. ``technical_seo`` / identity URL analysis  — observed, no dependencies
2. ``keyword_intelligence``                    — MUST precede metadata/content
   (focus keyphrase informs meta/title/slug and content-gap analysis)
3. ``content_intelligence``
4. ``metadata`` (meta/title/slug/OG)           — uses the focus keyphrase
5. ``internal_seo`` / ``image_intelligence`` / ``schema_intelligence`` / ``eeat``
6. ``content_score``                           — deterministic, over 1-5
7. ``ai_summary`` (seo_audit)                  — LAST, reasons over everything

AI-backed steps run only when an :class:`AIProvider` is injected; otherwise the
observed/deterministic sections are still produced (graceful degradation).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from core.types import CrawledPage
from intelligence.ai.prompt_registry import PromptRegistry, default_prompt_registry
from intelligence.ai.provider_interface import AIProvider
from intelligence.field_paths import get_by_path, set_by_path
from intelligence.identifiers import page_id_for
from intelligence.models.identity import IdentitySection, PageType
from intelligence.models.knowledge_object import KnowledgeObject
from intelligence.prompts.base_prompt_template import PromptContext
from intelligence.repositories.ai_invocation_repository import AIInvocationRepository
from intelligence.repositories.knowledge_object_repository import (
    KnowledgeObjectRepository,
)
from intelligence.repositories.page_snapshot_repository import PageSnapshotRepository
from intelligence.services.base import AnalysisContext, AnalyzerService
from intelligence.services.capability_runner import CapabilityRunner
from intelligence.services.content_analysis_service import ContentAnalysisService
from intelligence.services.content_score_service import ContentScoreService
from intelligence.services.eeat_analysis_service import EeatAnalysisService
from intelligence.services.image_intelligence_service import ImageIntelligenceService
from intelligence.services.internal_linking_service import InternalLinkingService
from intelligence.services.keyword_analysis_service import KeywordAnalysisService
from intelligence.services.metadata_generation_service import MetadataGenerationService
from intelligence.services.schema_intelligence_service import SchemaIntelligenceService
from intelligence.services.seo_audit_service import SeoAuditService
from intelligence.services.technical_seo_service import TechnicalSeoService
from intelligence.services.text_extraction import extract_content

__all__ = ["AnalysisOrchestrator", "DEFAULT_PIPELINE_ORDER"]

#: Analyzer services in strict dependency order (§8.1).
DEFAULT_PIPELINE_ORDER: tuple[type[AnalyzerService], ...] = (
    TechnicalSeoService,
    KeywordAnalysisService,
    ContentAnalysisService,
    MetadataGenerationService,
    InternalLinkingService,
    ImageIntelligenceService,
    SchemaIntelligenceService,
    EeatAnalysisService,
    ContentScoreService,
    SeoAuditService,  # LAST
)


class AnalysisOrchestrator:
    def __init__(
        self,
        *,
        knowledge_repo: KnowledgeObjectRepository,
        invocation_repo: AIInvocationRepository,
        snapshot_repo: PageSnapshotRepository | None = None,
        provider: AIProvider | None = None,
        prompt_registry: PromptRegistry | None = None,
        pipeline=None,
        tenant_id: str,
        max_retries: int = 2,
    ) -> None:
        from intelligence.validation.validation_pipeline import ValidationPipeline

        self._knowledge_repo = knowledge_repo
        self._invocation_repo = invocation_repo
        self._snapshot_repo = snapshot_repo
        self._provider = provider
        self._registry = prompt_registry or default_prompt_registry()
        self._pipeline = pipeline or ValidationPipeline()
        self._tenant_id = tenant_id
        self._max_retries = max_retries
        self._services = [cls() for cls in DEFAULT_PIPELINE_ORDER]

    # --- Public API ----------------------------------------------------------

    def run(
        self,
        page: CrawledPage,
        *,
        page_id: str | None = None,
        crawl_id: str | None = None,
        capabilities: list[str] | None = None,
        force_regenerate_overrides: bool = False,
    ) -> KnowledgeObject:
        """Analyze ``page`` and persist a new KnowledgeObject version."""
        pid = page_id or page_id_for(self._tenant_id, page.url)
        if self._snapshot_repo is not None:
            self._snapshot_repo.upsert(self._tenant_id, pid, page, crawl_id=crawl_id)

        version = self._knowledge_repo.next_version(self._tenant_id, pid)
        ko = self._base_knowledge_object(pid, page, version, crawl_id)

        extracted = extract_content(page.html)
        prompt_context = self._prompt_context(page, extracted)
        runner = self._build_runner()
        known_urls = (
            self._snapshot_repo.known_urls(self._tenant_id)
            if self._snapshot_repo is not None
            else []
        )
        enabled = set(capabilities) if capabilities else None

        ctx = AnalysisContext(
            tenant_id=self._tenant_id,
            page_id=pid,
            page=page,
            extracted=extracted,
            ko=ko,
            prompt_context=prompt_context,
            runner=runner,
            known_urls=known_urls,
            existing_slugs=self._existing_slugs(known_urls),
            enabled_sections=enabled,
        )

        for service in self._services:
            if ctx.section_enabled(service.section):
                service.analyze(ctx)

        self._carry_forward_overrides(ko, pid, force_regenerate_overrides)
        return self._knowledge_repo.save(self._tenant_id, ko)

    def run_for_snapshot(
        self, page_id: str, *, force_regenerate_overrides: bool = False,
        capabilities: list[str] | None = None,
    ) -> KnowledgeObject | None:
        """Re-analyze from the stored crawl snapshot (on-demand ``/analyze``)."""
        if self._snapshot_repo is None:
            return None
        page = self._snapshot_repo.get(self._tenant_id, page_id)
        if page is None:
            return None
        return self.run(
            page, page_id=page_id, capabilities=capabilities,
            force_regenerate_overrides=force_regenerate_overrides,
        )

    # --- Assembly helpers ----------------------------------------------------

    def _base_knowledge_object(
        self, page_id: str, page: CrawledPage, version: int, crawl_id: str | None
    ) -> KnowledgeObject:
        from urllib.parse import urlsplit

        path = urlsplit(page.url).path
        slug = path.rstrip("/").rsplit("/", 1)[-1] if path.strip("/") else ""
        return KnowledgeObject(
            id=uuid.uuid4().hex,
            page_id=page_id,
            tenant_id=self._tenant_id,
            version=version,
            crawl_id=crawl_id,
            created_at=datetime.now(timezone.utc),
            identity=IdentitySection(
                url=page.url,
                slug=slug,
                page_type=PageType.OTHER,
            ),
        )

    def _prompt_context(
        self, page: CrawledPage, extracted
    ) -> PromptContext:
        excerpt = extracted.text[:2000] if extracted.text else None
        return PromptContext(
            page_url=page.url,
            title=page.title,
            meta_description=page.meta_description,
            headings=[t for _lvl, t in extracted.headings],
            first_paragraph=extracted.paragraphs[0] if extracted.paragraphs else None,
            content_excerpt=excerpt,
            word_count=page.word_count or len(extracted.words),
            images=[
                {"element_id": "", "filename": img.filename, "alt": img.alt_text}
                for img in page.images
            ],
        )

    def _build_runner(self) -> CapabilityRunner | None:
        if self._provider is None:
            return None
        return CapabilityRunner(
            provider=self._provider,
            prompt_registry=self._registry,
            pipeline=self._pipeline,
            invocation_repo=self._invocation_repo,
            tenant_id=self._tenant_id,
            max_retries=self._max_retries,
        )

    @staticmethod
    def _existing_slugs(known_urls: list[str]) -> set[str]:
        from urllib.parse import urlsplit

        slugs: set[str] = set()
        for url in known_urls:
            path = urlsplit(url).path
            if path.strip("/"):
                slugs.add(path.rstrip("/").rsplit("/", 1)[-1])
        return slugs

    def _carry_forward_overrides(
        self, ko: KnowledgeObject, page_id: str, force: bool
    ) -> None:
        """Preserve human overrides from the prior version (§13.3).

        Any field path a human overrode on the previous version is copied forward
        unchanged (value + override registry entry) unless ``force`` is set.
        """
        if force:
            return
        prior = self._knowledge_repo.get_latest(self._tenant_id, page_id)
        if prior is None or not prior.overrides:
            return
        for path, override in prior.overrides.items():
            if override.source != "human":
                continue
            prior_value = get_by_path(prior, path)
            if prior_value is not None and set_by_path(ko, path, prior_value):
                ko.overrides[path] = override
                self._stamp_override_source(ko, path, override)

    @staticmethod
    def _stamp_override_source(ko: KnowledgeObject, path: str, override) -> None:
        """Reflect a human override on the parent MetadataField/OgImageField (§13.3)."""
        if "." not in path:
            return
        parent = get_by_path(ko, path.rsplit(".", 1)[0])
        if parent is not None and hasattr(parent, "override_source"):
            from intelligence.models.metadata_intelligence import OverrideSource

            parent.override_source = OverrideSource.HUMAN
            parent.overridden_at = override.overridden_at
            parent.overridden_by = override.overridden_by
