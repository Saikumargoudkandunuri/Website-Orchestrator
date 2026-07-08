"""Engine container — wires repositories, registry, and AI provider (Milestone 3).

Mirrors Milestone 2's ``IntelligenceContainer`` pattern: everything is
constructed here; routers and services receive the container from
``app.state.engines`` and never construct their own dependencies.

The engines layer reuses Milestone 2's :class:`~intelligence.ai.provider_interface.AIProvider`
interface and :class:`~intelligence.ai.providers.fake_provider.FakeProvider` — the
same AI abstraction discipline applies here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from engines.backlink_intelligence.repositories import BacklinkIntelligenceReportRepository
from engines.competitor_intelligence.repositories import CompetitorIntelligenceReportRepository
from engines.content_intelligence.repositories import ContentEngineReportRepository
from engines.keyword_intelligence.repositories import KeywordEngineReportRepository
from engines.opportunity.repositories import OpportunityReportRepository
from engines.recommendation.repositories import RecommendationReportRepository
from engines.seo_scoring.repositories import SeoScoreReportRepository
from engines.shared.audit_job_repository import AuditJobRepository
from engines.shared.db import create_engine_tables
from engines.shared.engine_registry import EngineRegistry, default_engine_registry
from engines.shared.provider_abstraction.fake_seo_data_provider import (
    FakeBacklinkDataProvider,
    FakeCompetitorDataProvider,
)
from engines.site_architecture.repositories import SiteArchitectureReportRepository
from engines.technical_seo.repositories import TechnicalSeoAuditRepository
from engines.topical_authority.repositories import TopicalAuthorityReportRepository

__all__ = [
    "EnginesContainer",
    "build_engines_container",
    "build_default_engines",
]


@dataclass
class EnginesContainer:
    """All engine repositories + registry + AI/SEO provider dependencies."""

    tenant_id: str
    engine_registry: EngineRegistry

    # Per-page repositories
    technical_seo_repo: TechnicalSeoAuditRepository
    keyword_repo: KeywordEngineReportRepository
    content_repo: ContentEngineReportRepository
    seo_score_repo: SeoScoreReportRepository

    # Sitewide repositories
    site_arch_repo: SiteArchitectureReportRepository
    competitor_repo: CompetitorIntelligenceReportRepository
    backlink_repo: BacklinkIntelligenceReportRepository
    topical_authority_repo: TopicalAuthorityReportRepository
    opportunity_repo: OpportunityReportRepository
    recommendation_repo: RecommendationReportRepository

    # Audit job repository
    audit_job_repo: AuditJobRepository

    # Provider dependencies — injected so the orchestrator can pass them to services
    ai_provider: Any = None          # AIProvider (M2 interface)
    competitor_provider: Any = field(default_factory=FakeCompetitorDataProvider)
    backlink_provider: Any = field(default_factory=FakeBacklinkDataProvider)


def build_engines_container(
    session_source: Session | sessionmaker[Session] | object,
    tenant_id: str,
    *,
    ai_provider: Any = None,
    competitor_provider: Any = None,
    backlink_provider: Any = None,
    engine_registry: EngineRegistry | None = None,
) -> EnginesContainer:
    """Build an EnginesContainer from a session source.

    Tests pass an in-memory SQLite session; production passes the shared
    session factory from the application startup.
    """
    from intelligence.ai.providers.fake_provider import FakeProvider

    return EnginesContainer(
        tenant_id=tenant_id,
        engine_registry=engine_registry or default_engine_registry(),
        technical_seo_repo=TechnicalSeoAuditRepository(session_source, tenant_id=tenant_id),
        keyword_repo=KeywordEngineReportRepository(session_source, tenant_id=tenant_id),
        content_repo=ContentEngineReportRepository(session_source, tenant_id=tenant_id),
        seo_score_repo=SeoScoreReportRepository(session_source, tenant_id=tenant_id),
        site_arch_repo=SiteArchitectureReportRepository(session_source, tenant_id=tenant_id),
        competitor_repo=CompetitorIntelligenceReportRepository(session_source, tenant_id=tenant_id),
        backlink_repo=BacklinkIntelligenceReportRepository(session_source, tenant_id=tenant_id),
        topical_authority_repo=TopicalAuthorityReportRepository(session_source, tenant_id=tenant_id),
        opportunity_repo=OpportunityReportRepository(session_source, tenant_id=tenant_id),
        recommendation_repo=RecommendationReportRepository(session_source, tenant_id=tenant_id),
        audit_job_repo=AuditJobRepository(session_source, tenant_id=tenant_id),
        ai_provider=ai_provider or FakeProvider(),
        competitor_provider=competitor_provider or FakeCompetitorDataProvider(),
        backlink_provider=backlink_provider or FakeBacklinkDataProvider(),
    )


def build_default_engines() -> EnginesContainer:
    """Build the production container from Core_Package configuration.

    Provisions the engine tables on the configured datastore.  Raises if
    configuration/datastore is unavailable — the API factory catches that and
    simply does not mount the engine routers.
    """
    from core.config import get_settings
    from digital_twin.db import create_db_engine, make_session_factory

    settings = get_settings()
    engine = create_db_engine(settings.database_url)
    create_engine_tables(engine)
    session_factory = make_session_factory(engine)

    return build_engines_container(session_factory, settings.tenant_id)
