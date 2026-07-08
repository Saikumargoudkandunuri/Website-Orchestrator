"""Failure Recovery engine for agent missions (M6 Build Phase F)."""
from __future__ import annotations

from agentic.agents.mission_manager import MissionManager
from agentic.agents.types import JsonObject
from agentic.runtime.runtime import AgentRuntime
from agentic.tools.selector import ExecutionPolicy
from growth.auth import GrowthIdentity


class FailureRecovery:
    """Restores mission state from existing Runtime checkpoints and requires caller identity."""

    def __init__(self, mission_manager: MissionManager, runtime: AgentRuntime) -> None:
        self.mission_manager = mission_manager
        self.runtime = runtime

    def recover_mission(
        self,
        tenant_id: str,
        mission_id: str,
        identity: GrowthIdentity,
        policy: ExecutionPolicy,
    ) -> JsonObject:
        """Recover a mission only through Runtime using the original tenant identity and policy."""
        mission = self.mission_manager.get_mission(tenant_id, mission_id)
        if not mission:
            raise ValueError(f"Mission '{mission_id}' not found.")
        if identity.tenant_id != tenant_id or policy.tenant_id != tenant_id:
            raise ValueError("Recovery identity and policy must match the mission tenant.")

        execution_id = f"exec_{mission_id}"
        checkpoint = self.runtime.checkpoint_manager.load_checkpoint(tenant_id, execution_id)
        if not checkpoint:
            self.mission_manager.transition_state(tenant_id, mission_id, "failed", reason="missing_checkpoint")
            return {"mission_id": mission_id, "recovered": False, "reason": "No execution checkpoint to resume from."}

        self.mission_manager.transition_state(tenant_id, mission_id, "recovering", reason="checkpoint_restore")
        state = checkpoint.state
        while state not in ("completed", "failed", "blocked", "cancelled"):
            result = self.runtime.execute_next_node(execution_id, tenant_id, identity, policy)
            state = str(result["state"])

        final_state = "completed" if state == "completed" else "failed"
        self.mission_manager.transition_state(tenant_id, mission_id, final_state, reason="recovery_finished")
        return {"mission_id": mission_id, "recovered": True, "state": final_state}
