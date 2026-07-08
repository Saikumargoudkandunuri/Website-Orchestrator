"""Dependency Injection wiring for the agentic runtime (M6 Build Phase D)."""
from __future__ import annotations

from dataclasses import dataclass
from sqlalchemy.orm import Session, sessionmaker

from agentic.memory.memory_manager import MemoryManager
from agentic.tools.registry import ToolRegistry
from agentic.runtime.executor import Executor
from agentic.runtime.governance_gate import GovernanceGate
from agentic.runtime.execution_monitor import ExecutionMonitor
from agentic.runtime.recovery_engine import RecoveryEngine
from agentic.runtime.repositories import (
    CheckpointRepository,
    ExecutionRepository,
    ExecutionMetricsRepository,
)
from agentic.runtime.checkpoint_manager import CheckpointManager
from agentic.runtime.runtime import AgentRuntime


@dataclass
class RuntimeContainer:
    """Container holding agentic runtime services."""
    tenant_id: str
    execution_repo: ExecutionRepository
    checkpoint_repo: CheckpointRepository
    metrics_repo: ExecutionMetricsRepository
    checkpoint_manager: CheckpointManager
    executor: Executor
    governance_gate: GovernanceGate
    monitor: ExecutionMonitor
    recovery_engine: RecoveryEngine
    runtime: AgentRuntime


def build_runtime_container(
    session_source: Session | sessionmaker[Session] | object,
    tenant_id: str,
    registry: ToolRegistry,
    memory_manager: MemoryManager,
    handlers: dict | None = None,
) -> RuntimeContainer:
    """Build and wire the agentic execution runtime container."""
    execution_repo = ExecutionRepository(session_source, tenant_id=tenant_id)
    checkpoint_repo = CheckpointRepository(session_source, tenant_id=tenant_id)
    metrics_repo = ExecutionMetricsRepository(session_source, tenant_id=tenant_id)
    
    checkpoint_manager = CheckpointManager(checkpoint_repo)
    executor = Executor(registry, handlers=handlers)
    governance_gate = GovernanceGate()
    monitor = ExecutionMonitor()
    recovery_engine = RecoveryEngine()
    
    runtime = AgentRuntime(
        execution_repo=execution_repo,
        checkpoint_repo=checkpoint_repo,
        metrics_repo=metrics_repo,
        executor=executor,
        governance_gate=governance_gate,
        monitor=monitor,
        recovery_engine=recovery_engine,
        memory_manager=memory_manager,
    )
    
    return RuntimeContainer(
        tenant_id=tenant_id,
        execution_repo=execution_repo,
        checkpoint_repo=checkpoint_repo,
        metrics_repo=metrics_repo,
        checkpoint_manager=checkpoint_manager,
        executor=executor,
        governance_gate=governance_gate,
        monitor=monitor,
        recovery_engine=recovery_engine,
        runtime=runtime,
    )
