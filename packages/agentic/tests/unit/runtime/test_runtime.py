"""Tests for the agentic runtime subsystem (M6 Build Phase D)."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from brain.db import BrainBase
from agentic.goal.models import RiskLevel
from agentic.planning.models import ExecutionEdge, ExecutionGraph, ExecutionNode
from agentic.tools.registry import build_default_tool_registry
from agentic.tools.selector import ExecutionPolicy
from agentic.memory.wiring import build_memory_container
from agentic.runtime.wiring import build_runtime_container
from agentic.runtime.state_machine import ExecutionState
from growth.auth import GrowthIdentity


@pytest.fixture
def db_session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Register tables
    from agentic.memory.repositories import (
        EpisodeRecord,
        SemanticFactRecord,
        WorkflowTemplateRecord,
        ReflectionLessonRecord,
        GoalMemoryRecordRow,
        MemoryIndexRecord,
    )
    from agentic.runtime.repositories import (
        CheckpointRecord,
        ExecutionRecordRow,
        ExecutionMetricsRecord,
    )
    BrainBase.metadata.create_all(engine)
    return sessionmaker(bind=engine)


@pytest.fixture
def default_identity():
    return GrowthIdentity(
        tenant_id="tenant_1",
        principal_id="test-editor",
        credential_type="api_key",
        roles=("owner",),
        permissions=("admin", "read", "write", "approve", "publish"),
    )


@pytest.fixture
def restricted_identity():
    return GrowthIdentity(
        tenant_id="tenant_1",
        principal_id="test-viewer",
        credential_type="api_key",
        roles=("viewer",),
        permissions=("read",),
    )


@pytest.fixture
def default_policy():
    return ExecutionPolicy(tenant_id="tenant_1", allowed_risk_level=RiskLevel.MEDIUM)


def test_state_machine_transitions():
    from agentic.runtime.state_machine import validate_transition
    assert validate_transition(ExecutionState.CREATED, ExecutionState.READY) is True
    assert validate_transition(ExecutionState.CREATED, ExecutionState.COMPLETED) is False
    assert validate_transition(ExecutionState.RUNNING, ExecutionState.SUCCEEDED) is True
    assert validate_transition(ExecutionState.COMPLETED, ExecutionState.RUNNING) is False


def test_governance_gate_risk_limit(db_session_factory, default_identity, default_policy):
    session = db_session_factory()
    memory_container = build_memory_container(session, "tenant_1")
    registry = build_default_tool_registry()
    runtime_container = build_runtime_container(session, "tenant_1", registry, memory_container.manager)
    
    # 1. High risk node should fail under Medium risk policy
    high_risk_node = ExecutionNode(
        id="node_high",
        goal_id="goal_1",
        action_type="wp_publish",
        risk_level=RiskLevel.HIGH,
    )
    gov_ok, reason = runtime_container.governance_gate.check_governance(
        high_risk_node,
        default_identity,
        default_policy,
        "tenant_1",
    )
    assert gov_ok is False
    assert "Risk limit exceeded" in reason


def test_governance_gate_permissions(db_session_factory, restricted_identity, default_policy):
    session = db_session_factory()
    memory_container = build_memory_container(session, "tenant_1")
    registry = build_default_tool_registry()
    runtime_container = build_runtime_container(session, "tenant_1", registry, memory_container.manager)
    
    # 2. Write action should fail for restricted identity (viewer)
    write_node = ExecutionNode(
        id="node_write",
        goal_id="goal_1",
        action_type="wp_publish",
        risk_level=RiskLevel.MEDIUM,
    )
    gov_ok, reason = runtime_container.governance_gate.check_governance(
        write_node,
        restricted_identity,
        default_policy,
        "tenant_1",
    )
    assert gov_ok is False
    assert "Permission violation" in reason


def test_governance_gate_approval_required(db_session_factory, default_identity, default_policy):
    session = db_session_factory()
    memory_container = build_memory_container(session, "tenant_1")
    registry = build_default_tool_registry()
    runtime_container = build_runtime_container(session, "tenant_1", registry, memory_container.manager)
    
    # 3. Node requiring approval fails without approved metadata
    approval_node = ExecutionNode(
        id="node_approval",
        goal_id="goal_1",
        action_type="seo_audit",
        approval_required=True,
    )
    gov_ok, reason = runtime_container.governance_gate.check_governance(
        approval_node,
        default_identity,
        default_policy,
        "tenant_1",
    )
    assert gov_ok is False
    assert "requires human approval" in reason


def test_plan_execution_loop(db_session_factory, default_identity, default_policy):
    session = db_session_factory()
    memory_container = build_memory_container(session, "tenant_1")
    registry = build_default_tool_registry()
    runtime_container = build_runtime_container(session, "tenant_1", registry, memory_container.manager)
    runtime = runtime_container.runtime
    
    # Define a clean 2-node DAG (node_1 -> node_2)
    node_1 = ExecutionNode(
        id="node_1",
        goal_id="goal_1",
        action_type="seo_audit",
        risk_level=RiskLevel.LOW,
    )
    node_2 = ExecutionNode(
        id="node_2",
        goal_id="goal_1",
        action_type="content_generator",
        risk_level=RiskLevel.MEDIUM,
    )
    edge = ExecutionEdge(from_node="node_1", to_node="node_2", dependency_type="sequential")
    graph = ExecutionGraph(
        nodes={"node_1": node_1, "node_2": node_2},
        edges=[edge],
    )
    plan_data = {"goal_id": "goal_1", "graph": graph.model_dump(mode="json")}
    
    # Start execution
    runtime.start_plan("exec_1", "tenant_1", plan_data, default_identity, default_policy)
    
    # First step runs node_1
    res1 = runtime.execute_next_node("exec_1", "tenant_1", default_identity, default_policy)
    assert res1["state"] == ExecutionState.READY.value
    assert res1["executed_node"] == "node_1"
    
    # Second step runs node_2
    res2 = runtime.execute_next_node("exec_1", "tenant_1", default_identity, default_policy)
    assert res2["state"] == ExecutionState.READY.value
    assert res2["executed_node"] == "node_2"
    
    # Third step completes plan
    res3 = runtime.execute_next_node("exec_1", "tenant_1", default_identity, default_policy)
    assert res3["state"] == ExecutionState.COMPLETED.value
    assert res3["executed_node"] is None
    
    # Verify episode was written to memory
    episodes = memory_container.manager.find_relevant_experiences("default_site")
    assert len(episodes) > 0
