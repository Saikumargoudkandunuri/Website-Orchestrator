"""Dependency Injection wiring for the multi-agent system (M6 Build Phase F)."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session, sessionmaker

from agentic.agents.agent_registry import AgentRegistry
from agentic.agents.blackboard import Blackboard
from agentic.agents.coordination_engine import CoordinationEngine
from agentic.agents.failure_recovery import FailureRecovery
from agentic.agents.mission_manager import MissionManager
from agentic.agents.mission_monitor import MissionMonitor
from agentic.agents.repositories import (
    AgentHistoryRepository,
    AgentRepository,
    BlackboardRepository,
    MessageRepository,
    MissionMetricsRepository,
    MissionRepository,
)
from agentic.agents.specialists.analytics_agent import AnalyticsAgent
from agentic.agents.specialists.automation_agent import AutomationAgent
from agentic.agents.specialists.content_agent import ContentAgent
from agentic.agents.specialists.decision_agent import DecisionAgent
from agentic.agents.specialists.growth_agent import GrowthAgent
from agentic.agents.specialists.knowledge_agent import KnowledgeAgent
from agentic.agents.specialists.memory_agent import MemoryAgent
from agentic.agents.specialists.research_agent import ResearchAgent
from agentic.agents.specialists.seo_agent import SeoAgent
from agentic.agents.specialists.technical_agent import TechnicalAgent
from agentic.agents.supervisor import SupervisorAgent
from agentic.agents.types import SpecialistAgent
from agentic.runtime.runtime import AgentRuntime


@dataclass
class AgentContainer:
    """DI container holding agentic collaboration services."""
    tenant_id: str
    mission_repo: MissionRepository
    blackboard_repo: BlackboardRepository
    message_repo: MessageRepository
    agent_repo: AgentRepository
    agent_history_repo: AgentHistoryRepository
    mission_metrics_repo: MissionMetricsRepository
    agent_registry: AgentRegistry
    blackboard: Blackboard
    coordination_engine: CoordinationEngine
    mission_manager: MissionManager
    mission_monitor: MissionMonitor
    failure_recovery: FailureRecovery
    seo_agent: SeoAgent
    content_agent: ContentAgent
    technical_agent: TechnicalAgent
    growth_agent: GrowthAgent
    analytics_agent: AnalyticsAgent
    automation_agent: AutomationAgent
    knowledge_agent: KnowledgeAgent
    decision_agent: DecisionAgent
    memory_agent: MemoryAgent
    research_agent: ResearchAgent
    supervisor: SupervisorAgent


def build_agent_container(
    session_source: Session | sessionmaker[Session] | object,
    tenant_id: str,
    runtime: AgentRuntime,
) -> AgentContainer:
    """Wire repositories, managers, specialists, and Supervisor."""
    mission_repo = MissionRepository(session_source, tenant_id=tenant_id)
    blackboard_repo = BlackboardRepository(session_source, tenant_id=tenant_id)
    message_repo = MessageRepository(session_source, tenant_id=tenant_id)
    agent_repo = AgentRepository(session_source, tenant_id=tenant_id)
    agent_history_repo = AgentHistoryRepository(session_source, tenant_id=tenant_id)
    mission_metrics_repo = MissionMetricsRepository(session_source, tenant_id=tenant_id)

    agent_registry = AgentRegistry(agent_repo, tenant_id)
    blackboard = Blackboard(blackboard_repo)
    coordination_engine = CoordinationEngine(agent_history_repo)
    mission_manager = MissionManager(mission_repo)
    mission_monitor = MissionMonitor(mission_metrics_repo)
    failure_recovery = FailureRecovery(mission_manager, runtime)

    seo_agent = SeoAgent()
    content_agent = ContentAgent()
    technical_agent = TechnicalAgent()
    growth_agent = GrowthAgent()
    analytics_agent = AnalyticsAgent()
    automation_agent = AutomationAgent()
    knowledge_agent = KnowledgeAgent()
    decision_agent = DecisionAgent()
    memory_agent = MemoryAgent()
    research_agent = ResearchAgent()

    specialists: list[SpecialistAgent] = [
        seo_agent,
        content_agent,
        technical_agent,
        growth_agent,
        analytics_agent,
        automation_agent,
        knowledge_agent,
        decision_agent,
        memory_agent,
        research_agent,
    ]

    for specialist in specialists:
        agent_registry.register_specialist(specialist)

    supervisor = SupervisorAgent(
        mission_manager=mission_manager,
        blackboard=blackboard,
        coordination_engine=coordination_engine,
        message_repo=message_repo,
        runtime=runtime,
        specialists=specialists,
    )

    return AgentContainer(
        tenant_id=tenant_id,
        mission_repo=mission_repo,
        blackboard_repo=blackboard_repo,
        message_repo=message_repo,
        agent_repo=agent_repo,
        agent_history_repo=agent_history_repo,
        mission_metrics_repo=mission_metrics_repo,
        agent_registry=agent_registry,
        blackboard=blackboard,
        coordination_engine=coordination_engine,
        mission_manager=mission_manager,
        mission_monitor=mission_monitor,
        failure_recovery=failure_recovery,
        seo_agent=seo_agent,
        content_agent=content_agent,
        technical_agent=technical_agent,
        growth_agent=growth_agent,
        analytics_agent=analytics_agent,
        automation_agent=automation_agent,
        knowledge_agent=knowledge_agent,
        decision_agent=decision_agent,
        memory_agent=memory_agent,
        research_agent=research_agent,
        supervisor=supervisor,
    )
