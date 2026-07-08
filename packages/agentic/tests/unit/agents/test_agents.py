"""Unit and integration scenario tests for the multi-agent system (M6 Build Phase F)."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from brain.db import BrainBase
from agentic.goal.models import RiskLevel
from agentic.tools.registry import build_default_tool_registry
from agentic.tools.selector import ExecutionPolicy
from agentic.memory.wiring import build_memory_container
from agentic.runtime.wiring import build_runtime_container
from agentic.reflection.wiring import build_reflection_container
from agentic.agents.wiring import build_agent_container
from agentic.planning.models import ExecutionGraph, ExecutionNode
from growth.auth import GrowthIdentity


@pytest.fixture
def db_session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Register all tables
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
    from agentic.reflection.repositories import (
        ReflectionReportRecord,
        ProviderScoreRecord,
        ToolScoreRecord,
        ConfidenceCalibrationRecord,
    )
    from agentic.agents.repositories import (
        MissionRecord,
        BlackboardEntryRecord,
        MessageRecord,
    )
    BrainBase.metadata.create_all(engine)
    return sessionmaker(bind=engine)


@pytest.fixture
def default_identity():
    return GrowthIdentity(
        tenant_id="tenant_1",
        principal_id="test-supervisor",
        credential_type="api_key",
        roles=("owner",),
        permissions=("admin", "read", "write", "approve", "publish"),
    )


@pytest.fixture
def default_policy():
    return ExecutionPolicy(tenant_id="tenant_1", allowed_risk_level=RiskLevel.MEDIUM)


def test_organic_traffic_growth_scenario(db_session_factory, default_identity, default_policy):
    session = db_session_factory()
    memory_container = build_memory_container(session, "tenant_1")
    registry = build_default_tool_registry()
    runtime_container = build_runtime_container(session, "tenant_1", registry, memory_container.manager)
    agent_container = build_agent_container(session, "tenant_1", runtime_container.runtime)
    
    # Run the organic traffic mission
    res = agent_container.supervisor.execute_mission(
        tenant_id="tenant_1",
        goal_id="goal_traffic_30",
        objective="Increase organic traffic by 30%",
        identity=default_identity,
        policy=default_policy,
    )
    
    assert res["state"] == "completed"
    assert res["execution_id"] is not None
    
    # Verify Blackboard contains proposals published by SEO and Content agents
    facts = agent_container.blackboard._repo.get_facts("tenant_1", res["mission_id"])
    keys = {f["key"] for f in facts}
    assert "proposal_seo_agent" in keys
    assert "proposal_content_agent" in keys
    assert "final_status" in keys


def test_local_seo_scenario(db_session_factory, default_identity, default_policy):
    session = db_session_factory()
    memory_container = build_memory_container(session, "tenant_1")
    registry = build_default_tool_registry()
    runtime_container = build_runtime_container(session, "tenant_1", registry, memory_container.manager)
    agent_container = build_agent_container(session, "tenant_1", runtime_container.runtime)
    
    # Run local SEO mission
    res = agent_container.supervisor.execute_mission(
        tenant_id="tenant_1",
        goal_id="goal_local_seo",
        objective="Improve local SEO rankings",
        identity=default_identity,
        policy=default_policy,
    )
    
    assert res["state"] == "completed"


def test_tenant_isolation_concurrency(db_session_factory, default_identity, default_policy):
    session = db_session_factory()
    memory_container = build_memory_container(session, "tenant_1")
    registry = build_default_tool_registry()
    runtime_container = build_runtime_container(session, "tenant_1", registry, memory_container.manager)
    agent_container = build_agent_container(session, "tenant_1", runtime_container.runtime)
    
    # Trigger execution in Tenant 1
    res1 = agent_container.supervisor.execute_mission(
        tenant_id="tenant_1",
        goal_id="goal_t1",
        objective="Analyze Tenant 1 rankings",
        identity=default_identity,
        policy=default_policy,
    )
    
    # Trigger execution in Tenant 2 (with matching Tenant 2 identity/policy)
    t2_identity = GrowthIdentity(
        tenant_id="tenant_2",
        principal_id="test-supervisor",
        credential_type="api_key",
        roles=("owner",),
        permissions=("admin", "read", "write", "approve", "publish"),
    )
    t2_policy = ExecutionPolicy(tenant_id="tenant_2", allowed_risk_level=RiskLevel.MEDIUM)
    
    # Make t2 containers
    memory_container_t2 = build_memory_container(session, "tenant_2")
    runtime_container_t2 = build_runtime_container(session, "tenant_2", registry, memory_container_t2.manager)
    agent_container_t2 = build_agent_container(session, "tenant_2", runtime_container_t2.runtime)
    
    res2 = agent_container_t2.supervisor.execute_mission(
        tenant_id="tenant_2",
        goal_id="goal_t2",
        objective="Analyze Tenant 2 rankings",
        identity=t2_identity,
        policy=t2_policy,
    )
    
    # Verify no cross-talk: Tenant 1 cannot access Blackboard entries of Tenant 2
    t1_facts = agent_container.blackboard._repo.get_facts("tenant_1", res1["mission_id"])
    t2_facts = agent_container.blackboard._repo.get_facts("tenant_1", res2["mission_id"])
    assert len(t2_facts) == 0  # Tenant 1 has no visibility over Tenant 2 mission


def test_ranking_drop_recovery_scenario(db_session_factory, default_identity, default_policy):
    session = db_session_factory()
    memory_container = build_memory_container(session, "tenant_1")
    registry = build_default_tool_registry()
    runtime_container = build_runtime_container(session, "tenant_1", registry, memory_container.manager)
    agent_container = build_agent_container(session, "tenant_1", runtime_container.runtime)

    res = agent_container.supervisor.execute_mission(
        tenant_id="tenant_1",
        goal_id="goal_ranking_drop",
        objective="Recover from ranking drop",
        identity=default_identity,
        policy=default_policy,
    )

    assert res["state"] == "completed"
    facts = agent_container.blackboard._repo.get_facts("tenant_1", res["mission_id"])
    assert any(fact["key"] == "final_status" for fact in facts)


def test_provider_outage_retries_through_runtime(db_session_factory, default_identity, default_policy):
    session = db_session_factory()
    memory_container = build_memory_container(session, "tenant_1")
    registry = build_default_tool_registry()
    attempts = {"seo_audit": 0}

    def flaky_seo_handler(inputs: dict[str, object]) -> dict[str, object]:
        attempts["seo_audit"] += 1
        if attempts["seo_audit"] == 1:
            raise RuntimeError("temporary provider outage")
        return {"status": "success", "provider": "secondary", "inputs": inputs}

    runtime_container = build_runtime_container(
        session,
        "tenant_1",
        registry,
        memory_container.manager,
        handlers={"seo_audit": flaky_seo_handler},
    )
    agent_container = build_agent_container(session, "tenant_1", runtime_container.runtime)

    res = agent_container.supervisor.execute_mission(
        tenant_id="tenant_1",
        goal_id="goal_provider_outage",
        objective="Provider outage failover",
        identity=default_identity,
        policy=default_policy,
    )

    assert res["state"] == "completed"
    assert attempts["seo_audit"] >= 2


def test_agent_crash_checkpoint_restore(db_session_factory, default_identity, default_policy):
    session = db_session_factory()
    memory_container = build_memory_container(session, "tenant_1")
    registry = build_default_tool_registry()
    runtime_container = build_runtime_container(session, "tenant_1", registry, memory_container.manager)
    agent_container = build_agent_container(session, "tenant_1", runtime_container.runtime)

    mission_id = "msn_crash_restore"
    execution_id = f"exec_{mission_id}"
    graph = ExecutionGraph(
        nodes={
            "node_1": ExecutionNode(id="node_1", goal_id="goal_restore", action_type="seo_audit"),
            "node_2": ExecutionNode(id="node_2", goal_id="goal_restore", action_type="seo_audit"),
        }
    )
    plan_data = {"goal_id": "goal_restore", "graph": graph.model_dump(mode="json")}

    agent_container.mission_manager.create_mission("tenant_1", mission_id, "goal_restore", {"objective": "Agent crash checkpoint restore"})
    agent_container.mission_manager.transition_state("tenant_1", mission_id, "planning", execution_id=execution_id)
    agent_container.mission_manager.transition_state("tenant_1", mission_id, "assigned", execution_id=execution_id)
    agent_container.mission_manager.transition_state("tenant_1", mission_id, "executing", execution_id=execution_id)
    runtime_container.runtime.start_plan(execution_id, "tenant_1", plan_data, default_identity, default_policy)
    runtime_container.runtime.execute_next_node(execution_id, "tenant_1", default_identity, default_policy)
    agent_container.mission_manager.transition_state("tenant_1", mission_id, "failed", reason="agent_crash", execution_id=execution_id)

    res = agent_container.failure_recovery.recover_mission("tenant_1", mission_id, default_identity, default_policy)

    assert res["recovered"] is True
    assert res["state"] == "completed"
    checkpoint = runtime_container.checkpoint_manager.load_checkpoint("tenant_1", execution_id)
    assert checkpoint is not None
    assert checkpoint.completed_node_ids == ["node_1", "node_2"]


def test_human_approval_pause_resume(db_session_factory, default_identity, default_policy):
    session = db_session_factory()
    memory_container = build_memory_container(session, "tenant_1")
    registry = build_default_tool_registry()
    runtime_container = build_runtime_container(session, "tenant_1", registry, memory_container.manager)
    agent_container = build_agent_container(session, "tenant_1", runtime_container.runtime)

    mission_id = "msn_human_pause"
    execution_id = f"exec_{mission_id}"
    graph = ExecutionGraph(nodes={"node_1": ExecutionNode(id="node_1", goal_id="goal_human", action_type="seo_audit")})
    plan_data = {"goal_id": "goal_human", "graph": graph.model_dump(mode="json")}

    agent_container.mission_manager.create_mission("tenant_1", mission_id, "goal_human", {"objective": "Human approval required pause/resume"})
    agent_container.mission_manager.transition_state("tenant_1", mission_id, "planning", execution_id=execution_id)
    agent_container.mission_manager.transition_state("tenant_1", mission_id, "assigned", execution_id=execution_id)
    agent_container.mission_manager.transition_state("tenant_1", mission_id, "executing", execution_id=execution_id)
    runtime_container.runtime.start_plan(execution_id, "tenant_1", plan_data, default_identity, default_policy)

    pause_result = runtime_container.runtime.pause_plan(execution_id, "tenant_1")
    agent_container.mission_manager.transition_state("tenant_1", mission_id, "waiting", reason="human_approval_required")
    resume_result = runtime_container.runtime.resume_plan(execution_id, "tenant_1", default_identity)
    agent_container.mission_manager.transition_state("tenant_1", mission_id, "executing", reason="human_approval_granted")

    assert pause_result["state"] == "paused"
    assert resume_result["state"] == "running"
    mission = agent_container.mission_manager.get_mission("tenant_1", mission_id)
    assert mission is not None
    assert mission.state.value == "executing"
