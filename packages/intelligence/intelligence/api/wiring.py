"""Composition helpers for the intelligence API (§10 integration).

Bundles the intelligence subsystems (repositories, provider, orchestrator) so the
FastAPI router can resolve them from ``app.state``. Mirrors Milestone 1's
container pattern: everything is constructed here and injected; the router holds
no construction logic. All dependencies are provider-agnostic — swapping the AI
provider is a :class:`ProviderConfig` change (§11.4).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session, sessionmaker

from intelligence.ai.prompt_registry import PromptRegistry, default_prompt_registry
from intelligence.ai.provider_factory import ProviderConfig, build_provider
from intelligence.ai.provider_interface import AIProvider
from intelligence.repositories.ai_invocation_repository import AIInvocationRepository
from intelligence.repositories.knowledge_object_repository import (
    KnowledgeObjectRepository,
)
from intelligence.repositories.page_snapshot_repository import PageSnapshotRepository
from intelligence.services.analysis_orchestrator import AnalysisOrchestrator
from intelligence.validation.validation_pipeline import ValidationPipeline

__all__ = ["IntelligenceContainer", "build_intelligence_container", "build_default_intelligence"]


@dataclass
class IntelligenceContainer:
    """Immutable bundle of intelligence subsystems for the API layer."""

    tenant_id: str
    knowledge_repo: KnowledgeObjectRepository
    invocation_repo: AIInvocationRepository
    snapshot_repo: PageSnapshotRepository
    provider: AIProvider
    prompt_registry: PromptRegistry
    pipeline: ValidationPipeline

    def orchestrator(self) -> AnalysisOrchestrator:
        return AnalysisOrchestrator(
            knowledge_repo=self.knowledge_repo,
            invocation_repo=self.invocation_repo,
            snapshot_repo=self.snapshot_repo,
            provider=self.provider,
            prompt_registry=self.prompt_registry,
            pipeline=self.pipeline,
            tenant_id=self.tenant_id,
        )


def build_intelligence_container(
    session_source: Session | sessionmaker[Session] | object,
    tenant_id: str,
    *,
    provider: AIProvider | None = None,
    provider_config: ProviderConfig | None = None,
) -> IntelligenceContainer:
    """Build a container from a session source and provider selection.

    Tests pass an in-memory ``session_source`` and a ``FakeProvider`` (or a fake
    ``ProviderConfig``); production passes the shared engine's session factory
    and a real :class:`ProviderConfig`.
    """
    chosen_provider = provider or build_provider(provider_config or ProviderConfig(name="fake"))
    return IntelligenceContainer(
        tenant_id=tenant_id,
        knowledge_repo=KnowledgeObjectRepository(session_source, tenant_id=tenant_id),
        invocation_repo=AIInvocationRepository(session_source, tenant_id=tenant_id),
        snapshot_repo=PageSnapshotRepository(session_source, tenant_id=tenant_id),
        provider=chosen_provider,
        prompt_registry=default_prompt_registry(),
        pipeline=ValidationPipeline(),
    )


def build_default_intelligence() -> IntelligenceContainer:
    """Build the production container from Core_Package configuration.

    Provisions the intelligence tables on the configured datastore and selects
    the AI provider from configuration (defaults to the deterministic fake when
    none is configured, so the endpoints work out-of-the-box without a live AI
    account). Raises if configuration/datastore is unavailable — the API factory
    catches that and simply does not mount the intelligence router.
    """
    from core.config import get_settings
    from digital_twin.db import create_db_engine, make_session_factory
    from intelligence.repositories import create_intelligence_tables

    settings = get_settings()
    engine = create_db_engine(settings.database_url)
    create_intelligence_tables(engine)
    session_factory = make_session_factory(engine)

    provider_name = getattr(settings, "intelligence_ai_provider", None) or "fake"
    provider_config = ProviderConfig(name=provider_name)
    return build_intelligence_container(
        session_factory, settings.tenant_id, provider_config=provider_config
    )
