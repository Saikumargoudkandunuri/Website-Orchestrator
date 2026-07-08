"""Coordination Engine for explainable multi-agent collaboration (M6 Build Phase F)."""
from __future__ import annotations

import uuid
from enum import Enum

from agentic.agents.repositories import AgentHistoryRepository
from agentic.agents.types import JsonObject, SpecialistAgent


class CoordinationMode(str, Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    VOTING = "voting"
    CONSENSUS = "consensus"
    SUPERVISOR_OVERRIDE = "supervisor_override"
    CONFLICT_RESOLUTION = "conflict_resolution"
    DEPENDENCY_WAITING = "dependency_waiting"
    DYNAMIC_REASSIGNMENT = "dynamic_reassignment"
    LOAD_BALANCING = "load_balancing"


class CoordinationEngine:
    """Coordinates specialist agents, voting, consensus, overrides, and reassignment."""

    def __init__(self, history_repo: AgentHistoryRepository) -> None:
        self._history_repo = history_repo

    def record_decision(self, tenant_id: str, mission_id: str, agent_id: str, decision: JsonObject) -> None:
        event_id = f"hist_{uuid.uuid4().hex}"
        self._history_repo.save_event(tenant_id, mission_id, event_id, agent_id, decision)

    def gather_votes_on_proposals(
        self,
        tenant_id: str,
        mission_id: str,
        voter_agents: list[SpecialistAgent],
        proposals: list[JsonObject],
        mode: CoordinationMode = CoordinationMode.VOTING,
    ) -> list[JsonObject]:
        """Persist every vote and approve proposals that reach majority consensus."""
        approved_proposals: list[JsonObject] = []
        for proposal in proposals:
            action = str(proposal.get("action", ""))
            votes: list[JsonObject] = []
            for agent in voter_agents:
                supports_tool = action in agent.tools
                supports_capability = any(capability in action for capability in agent.capabilities)
                approved = supports_tool or supports_capability or agent.confidence >= 0.5
                vote: JsonObject = {"agent": agent.name, "proposal_action": action, "approved": approved, "mode": mode.value}
                votes.append(vote)
                self.record_decision(tenant_id, mission_id, agent.name, {"event": "proposal_vote", "vote": vote})
            approvals = sum(1 for vote in votes if vote["approved"] is True)
            decision: JsonObject = {
                "event": "coordination_decision",
                "mode": mode.value,
                "proposal": proposal,
                "approvals": approvals,
                "voters": len(voter_agents),
            }
            if approvals >= max(1, (len(voter_agents) // 2) + 1):
                approved_proposals.append(proposal)
                decision["decision"] = "approved"
            else:
                decision["decision"] = "rejected"
            self.record_decision(tenant_id, mission_id, "coordination_engine", decision)
        return approved_proposals

    def choose_least_loaded_agent(self, agents: list[SpecialistAgent], active_counts: dict[str, int]) -> SpecialistAgent:
        selected = min(agents, key=lambda agent: (active_counts.get(agent.name, 0), agent.latency_ms, agent.cost))
        return selected

    def resolve_conflict(self, tenant_id: str, mission_id: str, proposals: list[JsonObject], supervisor_reason: str) -> JsonObject:
        if not proposals:
            raise ValueError("Cannot resolve conflict without proposals.")
        selected = max(proposals, key=lambda proposal: float(proposal.get("confidence", 0.0) or 0.0))
        self.record_decision(
            tenant_id,
            mission_id,
            "supervisor",
            {
                "event": "conflict_resolution",
                "mode": CoordinationMode.SUPERVISOR_OVERRIDE.value,
                "reason": supervisor_reason,
                "selected": selected,
            },
        )
        return selected
