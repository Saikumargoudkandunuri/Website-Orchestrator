"""Dependency Injection wiring for reflection and learning (M6 Build Phase E)."""
from __future__ import annotations

from dataclasses import dataclass
from sqlalchemy.orm import Session, sessionmaker

from agentic.memory.memory_manager import MemoryManager
from agentic.reflection.repositories import (
    ReflectionRepository,
    ProviderScoreRepository,
    ToolScoreRepository,
    ConfidenceCalibrationRepository,
)
from agentic.reflection.reflection_engine import ReflectionEngine
from agentic.reflection.experience_analyzer import ExperienceAnalyzer
from agentic.reflection.learning_engine import LearningEngine
from agentic.reflection.strategy_optimizer import StrategyOptimizer
from agentic.reflection.provider_learning import ProviderLearning
from agentic.reflection.tool_learning import ToolLearning
from agentic.reflection.confidence_engine import ConfidenceEngine


@dataclass
class ReflectionContainer:
    """Container holding learning and reflection services."""
    tenant_id: str
    reflection_repo: ReflectionRepository
    provider_score_repo: ProviderScoreRepository
    tool_score_repo: ToolScoreRepository
    confidence_repo: ConfidenceCalibrationRepository
    
    reflection_engine: ReflectionEngine
    experience_analyzer: ExperienceAnalyzer
    learning_engine: LearningEngine
    strategy_optimizer: StrategyOptimizer
    provider_learning: ProviderLearning
    tool_learning: ToolLearning
    confidence_engine: ConfidenceEngine


def build_reflection_container(
    session_source: Session | sessionmaker[Session] | object,
    tenant_id: str,
    memory_manager: MemoryManager,
) -> ReflectionContainer:
    """Build and wire the agentic reflection/learning container."""
    reflection_repo = ReflectionRepository(session_source, tenant_id=tenant_id)
    provider_score_repo = ProviderScoreRepository(session_source, tenant_id=tenant_id)
    tool_score_repo = ToolScoreRepository(session_source, tenant_id=tenant_id)
    confidence_repo = ConfidenceCalibrationRepository(session_source, tenant_id=tenant_id)
    
    reflection_engine = ReflectionEngine(reflection_repo, memory_manager)
    experience_analyzer = ExperienceAnalyzer(memory_manager)
    learning_engine = LearningEngine(memory_manager)
    strategy_optimizer = StrategyOptimizer()
    provider_learning = ProviderLearning(provider_score_repo)
    tool_learning = ToolLearning(tool_score_repo)
    confidence_engine = ConfidenceEngine(confidence_repo)
    
    return ReflectionContainer(
        tenant_id=tenant_id,
        reflection_repo=reflection_repo,
        provider_score_repo=provider_score_repo,
        tool_score_repo=tool_score_repo,
        confidence_repo=confidence_repo,
        reflection_engine=reflection_engine,
        experience_analyzer=experience_analyzer,
        learning_engine=learning_engine,
        strategy_optimizer=strategy_optimizer,
        provider_learning=provider_learning,
        tool_learning=tool_learning,
        confidence_engine=confidence_engine,
    )
