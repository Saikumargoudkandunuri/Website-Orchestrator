"""Mission Manager for tracking mission lifecycle states (M6 Build Phase F)."""
from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field

from agentic.agents.repositories import MissionRepository
from agentic.agents.types import JsonObject, JsonValue


class MissionLifecycleState(str, Enum):
    CREATED = "created"
    PLANNING = "planning"
    ASSIGNED = "assigned"
    EXECUTING = "executing"
    WAITING = "waiting"
    RECOVERING = "recovering"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


_ALLOWED_TRANSITIONS: dict[MissionLifecycleState, set[MissionLifecycleState]] = {
    MissionLifecycleState.CREATED: {MissionLifecycleState.PLANNING, MissionLifecycleState.CANCELLED, MissionLifecycleState.FAILED},
    MissionLifecycleState.PLANNING: {MissionLifecycleState.ASSIGNED, MissionLifecycleState.WAITING, MissionLifecycleState.CANCELLED, MissionLifecycleState.FAILED},
    MissionLifecycleState.ASSIGNED: {MissionLifecycleState.EXECUTING, MissionLifecycleState.WAITING, MissionLifecycleState.CANCELLED, MissionLifecycleState.FAILED},
    MissionLifecycleState.EXECUTING: {MissionLifecycleState.WAITING, MissionLifecycleState.RECOVERING, MissionLifecycleState.COMPLETED, MissionLifecycleState.CANCELLED, MissionLifecycleState.FAILED},
    MissionLifecycleState.WAITING: {MissionLifecycleState.EXECUTING, MissionLifecycleState.RECOVERING, MissionLifecycleState.CANCELLED, MissionLifecycleState.FAILED},
    MissionLifecycleState.RECOVERING: {MissionLifecycleState.EXECUTING, MissionLifecycleState.COMPLETED, MissionLifecycleState.CANCELLED, MissionLifecycleState.FAILED},
    MissionLifecycleState.COMPLETED: set(),
    MissionLifecycleState.CANCELLED: set(),
    MissionLifecycleState.FAILED: {MissionLifecycleState.RECOVERING},
}


class MissionState(BaseModel):
    """Overall state tracking for an orchestrator mission."""
    id: str
    tenant_id: str
    goal_id: str
    state: MissionLifecycleState = MissionLifecycleState.CREATED
    execution_id: str | None = None
    payload: JsonObject = Field(default_factory=dict)
    transitions: list[JsonObject] = Field(default_factory=list)


MissionState.model_rebuild(_types_namespace={"JsonValue": JsonValue})


class MissionManager:
    """Manages mission states with persisted, validated transitions."""

    def __init__(self, repository: MissionRepository) -> None:
        self._repo = repository

    def create_mission(self, tenant_id: str, id: str, goal_id: str, payload: JsonObject) -> MissionState:
        mission = MissionState(id=id, tenant_id=tenant_id, goal_id=goal_id, payload=payload)
        mission.transitions.append({"from": None, "to": mission.state.value, "reason": "mission_created"})
        self._repo.save_mission(tenant_id, id, goal_id, mission.state.value, mission.model_dump(mode="json"))
        return mission

    def transition_state(
        self,
        tenant_id: str,
        id: str,
        to_state: str | MissionLifecycleState,
        reason: str = "state_transition",
        execution_id: str | None = None,
    ) -> None:
        existing = self.get_mission(tenant_id, id)
        if not existing:
            raise ValueError(f"Mission '{id}' not found.")
        target = MissionLifecycleState(to_state)
        if target not in _ALLOWED_TRANSITIONS[existing.state]:
            raise ValueError(f"Cannot transition mission from '{existing.state.value}' to '{target.value}'.")
        existing.transitions.append({"from": existing.state.value, "to": target.value, "reason": reason})
        existing.state = target
        existing.execution_id = execution_id or existing.execution_id
        existing.payload["state"] = target.value
        if existing.execution_id:
            existing.payload["execution_id"] = existing.execution_id
        self._repo.save_mission(
            tenant_id=tenant_id,
            mission_id=id,
            goal_id=existing.goal_id,
            state=target.value,
            payload=existing.model_dump(mode="json"),
            execution_id=existing.execution_id,
        )

    def get_mission(self, tenant_id: str, id: str) -> MissionState | None:
        existing = self._repo.get_mission(tenant_id, id)
        if not existing:
            return None
        payload = existing["payload"]
        if isinstance(payload, dict) and "id" in payload:
            return MissionState.model_validate(payload)
        return MissionState(
            id=id,
            tenant_id=tenant_id,
            goal_id=str(existing["goal_id"]),
            state=MissionLifecycleState(str(existing["state"])),
            execution_id=str(existing["execution_id"]) if existing.get("execution_id") else None,
            payload=payload if isinstance(payload, dict) else {},
        )
