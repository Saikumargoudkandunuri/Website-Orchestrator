"""Agent Runtime orchestration engine (M6 Build Phase D)."""
from __future__ import annotations

import uuid
from typing import Any

from agentic.memory.models import ExperienceEpisode, ReflectionLesson
from agentic.memory.memory_manager import MemoryManager
from agentic.planning.models import ExecutionGraph, ExecutionNode
from agentic.tools.selector import ExecutionPolicy
from agentic.runtime.checkpoint_manager import CheckpointManager, ExecutionCheckpoint
from agentic.runtime.executor import Executor
from agentic.runtime.governance_gate import GovernanceGate
from agentic.runtime.execution_monitor import ExecutionMonitor
from agentic.runtime.recovery_engine import RecoveryEngine
from agentic.runtime.repositories import CheckpointRepository, ExecutionRepository, ExecutionMetricsRepository
from agentic.runtime.state_machine import ExecutionState, validate_transition
from growth.auth import GrowthIdentity


class AgentRuntime:
    """Deterministic orchestrator managing plan step executions and status changes."""
    
    def __init__(
        self,
        execution_repo: ExecutionRepository,
        checkpoint_repo: CheckpointRepository,
        metrics_repo: ExecutionMetricsRepository,
        executor: Executor,
        governance_gate: GovernanceGate,
        monitor: ExecutionMonitor,
        recovery_engine: RecoveryEngine,
        memory_manager: MemoryManager,
    ) -> None:
        self.execution_repo = execution_repo
        self.checkpoint_manager = CheckpointManager(checkpoint_repo)
        self.metrics_repo = metrics_repo
        self.executor = executor
        self.governance_gate = governance_gate
        self.monitor = monitor
        self.recovery_engine = recovery_engine
        self.memory_manager = memory_manager
        
    def start_plan(
        self,
        execution_id: str,
        tenant_id: str,
        plan_data: dict[str, Any],
        identity: GrowthIdentity,
        policy: ExecutionPolicy,
    ) -> dict[str, Any]:
        """Initialize plan execution state and checkpoint."""
        # Save initial execution state
        self.execution_repo.save_execution(
            tenant_id=tenant_id,
            execution_id=execution_id,
            state=ExecutionState.READY.value,
            plan_data=plan_data,
        )
        
        # Save initial checkpoint
        checkpoint = ExecutionCheckpoint(
            execution_id=execution_id,
            tenant_id=tenant_id,
            state=ExecutionState.READY.value,
        )
        self.checkpoint_manager.save_checkpoint(checkpoint)
        
        # Log metadata to metrics
        self.metrics_repo.save_metrics(
            tenant_id=tenant_id,
            execution_id=execution_id,
            metric_id=str(uuid.uuid4()),
            data={"event": "plan_started", "policy": policy.model_dump(mode="json")},
        )
        
        return {"execution_id": execution_id, "state": ExecutionState.READY.value}
        
    def pause_plan(self, execution_id: str, tenant_id: str) -> dict[str, Any]:
        execution = self.execution_repo.get_execution(tenant_id, execution_id)
        if not execution:
            raise ValueError(f"Execution plan '{execution_id}' not found.")
            
        current_state = ExecutionState(execution["state"])
        if not validate_transition(current_state, ExecutionState.PAUSED):
            raise ValueError(f"Cannot pause execution from state '{current_state}'.")
            
        self.execution_repo.save_execution(
            tenant_id=tenant_id,
            execution_id=execution_id,
            state=ExecutionState.PAUSED.value,
            plan_data=execution["plan"],
        )
        
        # Update checkpoint state
        checkpoint = self.checkpoint_manager.load_checkpoint(tenant_id, execution_id)
        if checkpoint:
            checkpoint.state = ExecutionState.PAUSED.value
            self.checkpoint_manager.save_checkpoint(checkpoint)
            
        return {"execution_id": execution_id, "state": ExecutionState.PAUSED.value}

    def resume_plan(
        self,
        execution_id: str,
        tenant_id: str,
        identity: GrowthIdentity,
    ) -> dict[str, Any]:
        execution = self.execution_repo.get_execution(tenant_id, execution_id)
        if not execution:
            raise ValueError(f"Execution plan '{execution_id}' not found.")
            
        current_state = ExecutionState(execution["state"])
        if not validate_transition(current_state, ExecutionState.RUNNING):
            raise ValueError(f"Cannot resume execution from state '{current_state}'.")
            
        self.execution_repo.save_execution(
            tenant_id=tenant_id,
            execution_id=execution_id,
            state=ExecutionState.RUNNING.value,
            plan_data=execution["plan"],
        )
        
        # Update checkpoint state
        checkpoint = self.checkpoint_manager.load_checkpoint(tenant_id, execution_id)
        if checkpoint:
            checkpoint.state = ExecutionState.RUNNING.value
            self.checkpoint_manager.save_checkpoint(checkpoint)
            
        return {"execution_id": execution_id, "state": ExecutionState.RUNNING.value}

    def cancel_plan(self, execution_id: str, tenant_id: str) -> dict[str, Any]:
        execution = self.execution_repo.get_execution(tenant_id, execution_id)
        if not execution:
            raise ValueError(f"Execution plan '{execution_id}' not found.")
            
        current_state = ExecutionState(execution["state"])
        if not validate_transition(current_state, ExecutionState.CANCELLED):
            raise ValueError(f"Cannot cancel execution from state '{current_state}'.")
            
        self.execution_repo.save_execution(
            tenant_id=tenant_id,
            execution_id=execution_id,
            state=ExecutionState.CANCELLED.value,
            plan_data=execution["plan"],
        )
        
        checkpoint = self.checkpoint_manager.load_checkpoint(tenant_id, execution_id)
        if checkpoint:
            checkpoint.state = ExecutionState.CANCELLED.value
            self.checkpoint_manager.save_checkpoint(checkpoint)
            
        return {"execution_id": execution_id, "state": ExecutionState.CANCELLED.value}

    def execute_next_node(
        self,
        execution_id: str,
        tenant_id: str,
        identity: GrowthIdentity,
        policy: ExecutionPolicy,
    ) -> dict[str, Any]:
        """Determines and executes the next node in the DAG plan."""
        execution = self.execution_repo.get_execution(tenant_id, execution_id)
        if not execution:
            raise ValueError(f"Execution plan '{execution_id}' not found.")
            
        checkpoint = self.checkpoint_manager.load_checkpoint(tenant_id, execution_id)
        if not checkpoint:
            raise ValueError(f"No checkpoint found for execution '{execution_id}'.")
            
        if checkpoint.state in (ExecutionState.COMPLETED.value, ExecutionState.FAILED.value, ExecutionState.CANCELLED.value):
            return {"execution_id": execution_id, "state": checkpoint.state, "executed_node": None}

        # Parse DAG execution graph from stored plan
        graph_dict = execution["plan"].get("graph", {})
        graph = ExecutionGraph.model_validate(graph_dict)
        
        # Identify nodes whose dependencies are satisfied
        completed = set(checkpoint.completed_node_ids)
        next_node: ExecutionNode | None = None
        
        # Topological search for next eligible node
        for node in graph.nodes.values():
            if node.id in completed:
                continue
            # Check dependencies
            dependencies_satisfied = True
            for edge in graph.edges:
                if edge.to_node == node.id and edge.from_node not in completed:
                    dependencies_satisfied = False
                    break
            if dependencies_satisfied:
                next_node = node
                break
                
        if not next_node:
            # No nodes left; plan complete
            self.execution_repo.save_execution(
                tenant_id=tenant_id,
                execution_id=execution_id,
                state=ExecutionState.COMPLETED.value,
                plan_data=execution["plan"],
            )
            checkpoint.state = ExecutionState.COMPLETED.value
            self.checkpoint_manager.save_checkpoint(checkpoint)
            return {"execution_id": execution_id, "state": ExecutionState.COMPLETED.value, "executed_node": None}

        checkpoint.current_node_id = next_node.id
        checkpoint.state = ExecutionState.RUNNING.value
        self.checkpoint_manager.save_checkpoint(checkpoint)
        
        # 1. Governance Gate Check
        gov_ok, gov_reason = self.governance_gate.check_governance(
            node=next_node,
            identity=identity,
            policy=policy,
            tenant_id=tenant_id,
        )
        if not gov_ok:
            checkpoint.state = ExecutionState.BLOCKED.value
            self.checkpoint_manager.save_checkpoint(checkpoint)
            self.execution_repo.save_execution(
                tenant_id=tenant_id,
                execution_id=execution_id,
                state=ExecutionState.BLOCKED.value,
                plan_data=execution["plan"],
            )
            # Log failure in execution metrics
            self.metrics_repo.save_metrics(
                tenant_id=tenant_id,
                execution_id=execution_id,
                metric_id=str(uuid.uuid4()),
                data={"event": "node_governance_failure", "node_id": next_node.id, "reason": gov_reason},
            )
            return {"execution_id": execution_id, "state": ExecutionState.BLOCKED.value, "executed_node": next_node.id, "error": gov_reason}

        # 2. Execution Telemetry Start
        start_time = self.monitor.record_node_start(
            tenant_id=tenant_id,
            execution_id=execution_id,
            node_id=next_node.id,
            tool_name=next_node.action_type or "",
        )
        
        # 3. Execution attempts with retries
        current_retries = 0
        success = False
        result = {}
        error_msg = None
        
        while not success:
            try:
                result = self.executor.execute_node(next_node, next_node.required_inputs)
                success = True
            except Exception as e:
                error_msg = str(e)
                if self.recovery_engine.should_retry(next_node, current_retries, e):
                    current_retries += 1
                    # exponential backoff delay is calculated but we avoid actual sleep in tests
                else:
                    break
                    
        # 4. Telemetry Finish
        metrics = self.monitor.record_node_finish(
            tenant_id=tenant_id,
            execution_id=execution_id,
            node_id=next_node.id,
            tool_name=next_node.action_type or "",
            start_time=start_time,
            success=success,
            error=error_msg,
        )
        self.metrics_repo.save_metrics(
            tenant_id=tenant_id,
            execution_id=execution_id,
            metric_id=str(uuid.uuid4()),
            data=metrics,
        )

        if success:
            checkpoint.completed_node_ids.append(next_node.id)
            checkpoint.outputs[next_node.id] = result
            checkpoint.current_node_id = None
            checkpoint.state = ExecutionState.READY.value
            self.checkpoint_manager.save_checkpoint(checkpoint)
            
            # Write success episode to memory
            episode = ExperienceEpisode(
                tenant_id=tenant_id,
                site_id=next_node.required_inputs.get("site_id", "default_site"),
                actor=identity.principal_id,
                goal_id=execution["plan"].get("goal_id"),
                execution_graph_id=execution_id,
                actions=[{"node_id": next_node.id, "action": next_node.action_type}],
                results=[result],
                success=True,
            )
            self.memory_manager.episodic.record_episode(episode)
            
            return {"execution_id": execution_id, "state": ExecutionState.READY.value, "executed_node": next_node.id, "result": result}
        else:
            checkpoint.state = ExecutionState.FAILED.value
            self.checkpoint_manager.save_checkpoint(checkpoint)
            self.execution_repo.save_execution(
                tenant_id=tenant_id,
                execution_id=execution_id,
                state=ExecutionState.FAILED.value,
                plan_data=execution["plan"],
            )
            
            # Write failure Reflection Lesson to memory
            lesson = ReflectionLesson(
                tenant_id=tenant_id,
                lesson=f"Execution of node '{next_node.id}' using tool '{next_node.action_type}' failed permanently.",
                confidence=1.0,
                evidence=[error_msg or "Unknown error"],
                related_executions=[execution_id],
            )
            self.memory_manager.reflection.record_lesson(lesson)
            
            return {"execution_id": execution_id, "state": ExecutionState.FAILED.value, "executed_node": next_node.id, "error": error_msg}
