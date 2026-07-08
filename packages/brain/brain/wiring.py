"""Brain container — wires repositories, services, and dependencies (Milestone 5).

Mirrors the ``EnginesContainer`` and ``GrowthContainer`` pattern: everything is
constructed here; routers and services receive the container from ``app.state``
and never construct their own dependencies.

Composed into the application's root container alongside (not inside)
``GrowthContainer`` and the M3 Engine Registry.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from brain.db import create_brain_tables
from brain.knowledge_graph.builder import KnowledgeGraphBuilder
from brain.providers.registry import PlatformAIProviderRegistry, build_default_provider_registry
from brain.scheduler.repositories import AutomationRuleRepository, ExecutionLogRepository, ScheduleRepository
from brain.scheduler.service import PlatformScheduler
from brain.repositories import KnowledgeGraphRepository, SiteSynthesisRepository
from brain.services import SeoBrain
from brain.decision.repositories import DecisionRepository, HistoricalOutcomeRepository
from brain.decision.engine import DecisionEngine, HistoricalOutcomeTracker

__all__ = [
    "BrainContainer",
    "build_brain_container",
    "build_default_brain",
]


@dataclass
class BrainContainer:
    """Brain-layer repositories, services, and dependencies."""

    tenant_id: str
    synthesis_repo: SiteSynthesisRepository
    kg_repo: KnowledgeGraphRepository
    seo_brain: SeoBrain
    decision_repo: DecisionRepository
    historical_repo: HistoricalOutcomeRepository
    decision_engine: DecisionEngine
    outcome_tracker: HistoricalOutcomeTracker
    provider_registry: PlatformAIProviderRegistry
    
    schedule_repo: ScheduleRepository
    rule_repo: AutomationRuleRepository
    log_repo: ExecutionLogRepository
    scheduler: PlatformScheduler


def build_brain_container(
    session_source: Session | sessionmaker[Session] | object,
    tenant_id: str,
    *,
    m3_repos: dict[str, Any] | None = None,
    m4_repos: dict[str, Any] | None = None,
) -> BrainContainer:
    """Build a BrainContainer from a session source.

    ``m3_repos`` and ``m4_repos`` are dicts mapping repo attribute names
    (as used by ``SeoBrain.M3_ENGINES`` / ``M4_ENGINES``) to repository
    instances. In production these are sourced from ``EnginesContainer``
    and ``GrowthContainer``; tests can pass mocks.
    """
    synthesis_repo = SiteSynthesisRepository(session_source, tenant_id=tenant_id)
    kg_repo = KnowledgeGraphRepository(session_source, tenant_id=tenant_id)

    seo_brain = SeoBrain(
        m3_repos=m3_repos or {},
        m4_repos=m4_repos or {},
        synthesis_repo=synthesis_repo,
        kg_repo=kg_repo,
    )
    
    decision_repo = DecisionRepository(session_source, tenant_id=tenant_id)
    historical_repo = HistoricalOutcomeRepository(session_source, tenant_id=tenant_id)
    
    decision_engine = DecisionEngine(decision_repo, historical_repo)
    outcome_tracker = HistoricalOutcomeTracker(historical_repo)
    provider_registry = build_default_provider_registry()
    
    schedule_repo = ScheduleRepository(session_source, tenant_id=tenant_id)
    rule_repo = AutomationRuleRepository(session_source, tenant_id=tenant_id)
    log_repo = ExecutionLogRepository(session_source, tenant_id=tenant_id)
    scheduler = PlatformScheduler(schedule_repo, rule_repo, log_repo)

    return BrainContainer(
        tenant_id=tenant_id,
        synthesis_repo=synthesis_repo,
        kg_repo=kg_repo,
        seo_brain=seo_brain,
        decision_repo=decision_repo,
        historical_repo=historical_repo,
        decision_engine=decision_engine,
        outcome_tracker=outcome_tracker,
        provider_registry=provider_registry,
        schedule_repo=schedule_repo,
        rule_repo=rule_repo,
        log_repo=log_repo,
        scheduler=scheduler,
    )


from functools import lru_cache

@lru_cache(maxsize=1)
def build_default_brain() -> BrainContainer:
    """Build the production BrainContainer from Core settings."""
    from core.config import get_settings
    from digital_twin.db import create_db_engine, make_session_factory

    settings = get_settings()
    engine = create_db_engine(settings.database_url)
    create_brain_tables(engine)
    session_factory = make_session_factory(engine)
    return build_brain_container(session_factory, settings.tenant_id)
