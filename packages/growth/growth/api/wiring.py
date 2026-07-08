"""Composition helpers for the Milestone 4 Growth API."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from growth.agency_management.repositories import AgencyManagementRepository
from growth.agency_management.services import AgencyManagementService
from growth.auth import AuthProvider, ConfiguredAuthProvider
from growth.analytics_intelligence.repositories import AnalyticsRepository
from growth.analytics_intelligence.services import AnalyticsService
from growth.automation.repositories import AutomationRepository
from growth.automation.services import AutomationService
from growth.content_generation.repositories import ContentAssetRepository
from growth.content_generation.services import ContentGenerationService
from growth.content_optimization.repositories import ContentOptimizationRepository
from growth.content_optimization.services import ContentOptimizationService
from growth.db import create_growth_tables
from growth.local_seo.repositories import LocalSeoRepository
from growth.local_seo.services import LocalSeoService
from growth.outreach.repositories import OutreachRepository
from growth.outreach.services import OutreachService
from growth.rank_tracking.repositories import RankTrackingRepository
from growth.rank_tracking.services import RankTrackingService
from growth.reporting.repositories import ReportingRepository
from growth.reporting.services import ReportingService
from growth.reputation_management.repositories import ReputationRepository
from growth.reputation_management.services import ReputationService
from growth.shared.automation.automation_rule_engine import RecordingActionDispatcher
from growth.shared.automation.event_bus_interface import InMemoryEventBus
from growth.shared.jobs.fake_job_queue import FakeJobQueue
from growth.shared.provider_abstraction.fake_providers import (
    FakeAnalyticsDataProvider,
    FakeLocalSeoDataProvider,
    FakeOutreachDataProvider,
    FakeRankTrackingProvider,
    FakeReputationDataProvider,
)

__all__ = ["GrowthContainer", "build_growth_container", "build_default_growth"]


@dataclass
class GrowthContainer:
    """Growth-layer repositories, services, providers, and infrastructure."""

    tenant_id: str
    content_asset_repo: ContentAssetRepository
    content_optimization_repo: ContentOptimizationRepository
    local_seo_repo: LocalSeoRepository
    reputation_repo: ReputationRepository
    rank_tracking_repo: RankTrackingRepository
    reporting_repo: ReportingRepository
    analytics_repo: AnalyticsRepository
    outreach_repo: OutreachRepository
    automation_repo: AutomationRepository
    agency_repo: AgencyManagementRepository
    content_generation: ContentGenerationService
    content_optimization: ContentOptimizationService
    local_seo: LocalSeoService
    reputation: ReputationService
    rank_tracking: RankTrackingService
    reporting: ReportingService
    analytics: AnalyticsService
    outreach: OutreachService
    automation: AutomationService
    agency_management: AgencyManagementService
    job_queue: FakeJobQueue
    event_bus: InMemoryEventBus
    action_dispatcher: RecordingActionDispatcher
    ai_provider: Any
    auth_provider: AuthProvider


def build_growth_container(
    session_source: Session | sessionmaker[Session] | object,
    tenant_id: str,
    *,
    ai_provider: Any | None = None,
    auth_provider: AuthProvider | None = None,
) -> GrowthContainer:
    """Build a GrowthContainer from a SQLAlchemy session source."""
    from intelligence.ai.providers.fake_provider import FakeProvider

    provider = ai_provider or FakeProvider()
    auth = auth_provider or ConfiguredAuthProvider.for_test_tenant(tenant_id)
    job_queue = FakeJobQueue()
    event_bus = InMemoryEventBus()
    dispatcher = RecordingActionDispatcher()

    content_asset_repo = ContentAssetRepository(session_source, tenant_id=tenant_id)
    content_optimization_repo = ContentOptimizationRepository(session_source, tenant_id=tenant_id)
    local_seo_repo = LocalSeoRepository(session_source, tenant_id=tenant_id)
    reputation_repo = ReputationRepository(session_source, tenant_id=tenant_id)
    rank_tracking_repo = RankTrackingRepository(session_source, tenant_id=tenant_id)
    reporting_repo = ReportingRepository(session_source, tenant_id=tenant_id)
    analytics_repo = AnalyticsRepository(session_source, tenant_id=tenant_id)
    outreach_repo = OutreachRepository(session_source, tenant_id=tenant_id)
    automation_repo = AutomationRepository(session_source, tenant_id=tenant_id)
    agency_repo = AgencyManagementRepository(session_source, tenant_id=tenant_id)

    rank_tracking = RankTrackingService(FakeRankTrackingProvider(), rank_tracking_repo, job_queue)
    reporting = ReportingService(reporting_repo, job_queue, provider)
    automation = AutomationService(event_bus, automation_repo, dispatcher)

    return GrowthContainer(
        tenant_id=tenant_id,
        content_asset_repo=content_asset_repo,
        content_optimization_repo=content_optimization_repo,
        local_seo_repo=local_seo_repo,
        reputation_repo=reputation_repo,
        rank_tracking_repo=rank_tracking_repo,
        reporting_repo=reporting_repo,
        analytics_repo=analytics_repo,
        outreach_repo=outreach_repo,
        automation_repo=automation_repo,
        agency_repo=agency_repo,
        content_generation=ContentGenerationService(provider, content_asset_repo, tenant_id),
        content_optimization=ContentOptimizationService(),
        local_seo=LocalSeoService(FakeLocalSeoDataProvider()),
        reputation=ReputationService(FakeReputationDataProvider(), provider),
        rank_tracking=rank_tracking,
        reporting=reporting,
        analytics=AnalyticsService(FakeAnalyticsDataProvider()),
        outreach=OutreachService(FakeOutreachDataProvider()),
        automation=automation,
        agency_management=AgencyManagementService(agency_repo),
        job_queue=job_queue,
        event_bus=event_bus,
        action_dispatcher=dispatcher,
        ai_provider=provider,
        auth_provider=auth,
    )


def build_default_growth() -> GrowthContainer:
    """Build the production GrowthContainer from Core settings."""
    from core.config import get_settings
    from digital_twin.db import create_db_engine, make_session_factory

    settings = get_settings()
    engine = create_db_engine(settings.database_url)
    create_growth_tables(engine)
    session_factory = make_session_factory(engine)
    auth_provider = ConfiguredAuthProvider(
        jwt_secret=settings.growth_auth_jwt_secret.get_secret_value()
        if settings.growth_auth_jwt_secret is not None
        else None,
        api_keys=settings.growth_api_key_identities(),
        service_accounts=settings.growth_service_account_identities(),
    )
    return build_growth_container(
        session_factory,
        settings.tenant_id,
        auth_provider=auth_provider,
    )
