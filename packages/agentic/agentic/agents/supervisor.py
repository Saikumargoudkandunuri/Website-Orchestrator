"""Supervisor Agent coordination module (M6 Build Phase F)."""
from __future__ import annotations

import uuid

from agentic.agents.blackboard import Blackboard
from agentic.agents.coordination_engine import CoordinationEngine, CoordinationMode
from agentic.agents.messaging import AgentMessage, FailureMessage, MessageType
from agentic.agents.mission_manager import MissionManager
from agentic.agents.repositories import MessageRepository
from agentic.agents.types import JsonObject, JsonValue, SpecialistAgent
from agentic.planning.models import ExecutionGraph, ExecutionNode
from agentic.runtime.runtime import AgentRuntime
from agentic.tools.selector import ExecutionPolicy
from growth.auth import GrowthIdentity


_TERMINAL_RUNTIME_STATES = ("completed", "failed", "blocked", "cancelled")


class SupervisorAgent:
    """Core Supervisor orchestrating specialized agents and Runtime-only execution."""

    def __init__(
        self,
        mission_manager: MissionManager,
        blackboard: Blackboard,
        coordination_engine: CoordinationEngine,
        message_repo: MessageRepository,
        runtime: AgentRuntime,
        specialists: list[SpecialistAgent],
    ) -> None:
        self.mission_manager = mission_manager
        self.blackboard = blackboard
        self.coordination_engine = coordination_engine
        self.message_repo = message_repo
        self.runtime = runtime
        self.specialists = specialists

    def execute_mission(
        self,
        tenant_id: str,
        goal_id: str,
        objective: str,
        identity: GrowthIdentity,
        policy: ExecutionPolicy,
    ) -> JsonObject:
        """Run planning, persisted collaboration, and delegated Runtime execution."""
        if identity.tenant_id != tenant_id or policy.tenant_id != tenant_id:
            raise ValueError("Mission identity and policy must match the tenant.")

        mission_id = f"msn_{uuid.uuid4().hex}"
        execution_id = f"exec_{mission_id}"
        trace_id = f"trace_{mission_id}"
        context: JsonObject = {"goal_id": goal_id, "objective": objective, "execution_id": execution_id}
        self.mission_manager.create_mission(tenant_id, mission_id, goal_id, {"objective": objective})
        self.mission_manager.transition_state(tenant_id, mission_id, "planning", execution_id=execution_id)

        proposals = self._collect_specialist_proposals(tenant_id, mission_id, trace_id, context)
        self.mission_manager.transition_state(tenant_id, mission_id, "assigned", execution_id=execution_id)
        approved_proposals = self.coordination_engine.gather_votes_on_proposals(
            tenant_id,
            mission_id,
            self.specialists,
            proposals,
            CoordinationMode.CONSENSUS,
        )

        if not approved_proposals:
            failure = {"mission_id": mission_id, "state": "failed", "reason": "No approved proposals from specialists."}
            self._persist_message(tenant_id, mission_id, trace_id, "supervisor", "supervisor", MessageType.FAILURE, failure)
            self.mission_manager.transition_state(tenant_id, mission_id, "failed", reason="no_approved_proposals")
            return failure

        plan_data = self._build_plan(goal_id, approved_proposals)
        self.mission_manager.transition_state(tenant_id, mission_id, "executing", execution_id=execution_id)
        self.runtime.start_plan(execution_id, tenant_id, plan_data, identity, policy)

        state = "ready"
        last_executed: JsonValue = None
        while state not in _TERMINAL_RUNTIME_STATES:
            result = self.runtime.execute_next_node(execution_id, tenant_id, identity, policy)
            state = str(result["state"])
            last_executed = result.get("executed_node")
            self.coordination_engine.record_decision(
                tenant_id,
                mission_id,
                "runtime",
                {"event": "runtime_step", "state": state, "executed_node": last_executed},
            )

        final_state = "completed" if state == "completed" else "failed"
        self.mission_manager.transition_state(tenant_id, mission_id, final_state, reason="runtime_terminal", execution_id=execution_id)
        final_status: JsonObject = {"state": final_state, "runtime_state": state, "last_executed": last_executed}
        self.blackboard.publish_fact(tenant_id, mission_id, "final_status", final_status, "supervisor")
        self._persist_message(tenant_id, mission_id, trace_id, "supervisor", "mission", MessageType.COMPLETION, final_status)
        return {"mission_id": mission_id, "state": final_state, "execution_id": execution_id}

    def _collect_specialist_proposals(
        self,
        tenant_id: str,
        mission_id: str,
        trace_id: str,
        context: JsonObject,
    ) -> list[JsonObject]:
        proposals: list[JsonObject] = []
        for specialist in self.specialists:
            correlation_id = f"corr_{uuid.uuid4().hex}"
            request_body: JsonObject = {"task": context["objective"], "goal_id": context["goal_id"]}
            self._persist_message(
                tenant_id,
                mission_id,
                trace_id,
                "supervisor",
                specialist.name,
                MessageType.REQUEST,
                request_body,
                correlation_id,
            )
            try:
                reasoning = specialist.reason(context)
            except Exception as exc:
                failure_body: JsonObject = {"agent": specialist.name, "error": str(exc)}
                self._persist_message(
                    tenant_id,
                    mission_id,
                    trace_id,
                    specialist.name,
                    "supervisor",
                    MessageType.FAILURE,
                    failure_body,
                    correlation_id,
                )
                raise RuntimeError(f"Specialist '{specialist.name}' failed to provide reasoning.") from exc

            self._persist_message(
                tenant_id,
                mission_id,
                trace_id,
                specialist.name,
                "supervisor",
                MessageType.EVIDENCE,
                reasoning,
                correlation_id,
            )
            self.blackboard.publish_fact(tenant_id, mission_id, f"proposal_{specialist.name}", reasoning, specialist.name)
            raw_proposals = reasoning.get("proposals")
            if isinstance(raw_proposals, list):
                proposals.extend(proposal for proposal in raw_proposals if isinstance(proposal, dict))
        return proposals

    def _build_plan(self, goal_id: str, approved_proposals: list[JsonObject]) -> JsonObject:
        nodes: dict[str, ExecutionNode] = {}
        for index, proposal in enumerate(approved_proposals):
            node_id = f"node_{index + 1}"
            raw_inputs = proposal.get("inputs")
            required_inputs: JsonObject = raw_inputs if isinstance(raw_inputs, dict) else {}
            nodes[node_id] = ExecutionNode(
                id=node_id,
                goal_id=goal_id,
                action_type=str(proposal["action"]),
                risk_level=str(proposal.get("risk_level", "low")),
                approval_required=bool(proposal.get("approval_required", False)),
                required_inputs=required_inputs,
            )
        graph = ExecutionGraph(nodes=nodes, edges=[])
        return {"goal_id": goal_id, "graph": graph.model_dump(mode="json")}

    def _persist_message(
        self,
        tenant_id: str,
        mission_id: str,
        trace_id: str,
        sender: str,
        recipient: str,
        message_type: MessageType,
        body: JsonObject,
        correlation_id: str | None = None,
    ) -> None:
        message = AgentMessage(
            mission_id=mission_id,
            tenant_id=tenant_id,
            sender=sender,
            recipient=recipient,
            message_type=message_type,
            body=body,
            trace_id=trace_id,
            correlation_id=correlation_id or f"corr_{uuid.uuid4().hex}",
        )
        self.message_repo.save_message(tenant_id, mission_id, message.id, message.model_dump(mode="json"))
