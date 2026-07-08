"""Execution State Machine for the Agentic Runtime (M6 Build Phase D)."""
from __future__ import annotations

from enum import Enum


class ExecutionState(str, Enum):
    """States of an execution plan or plan node."""
    CREATED = "created"
    READY = "ready"
    WAITING = "waiting"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    ROLLBACK = "rollback"
    COMPLETED = "completed"


#: Valid transitions per state
VALID_TRANSITIONS: dict[ExecutionState, set[ExecutionState]] = {
    ExecutionState.CREATED: {ExecutionState.READY, ExecutionState.CANCELLED},
    ExecutionState.READY: {ExecutionState.RUNNING, ExecutionState.PAUSED, ExecutionState.CANCELLED, ExecutionState.BLOCKED},
    ExecutionState.WAITING: {ExecutionState.RUNNING, ExecutionState.PAUSED, ExecutionState.CANCELLED},
    ExecutionState.RUNNING: {ExecutionState.SUCCEEDED, ExecutionState.FAILED, ExecutionState.BLOCKED, ExecutionState.PAUSED, ExecutionState.CANCELLED},
    ExecutionState.BLOCKED: {ExecutionState.RUNNING, ExecutionState.CANCELLED, ExecutionState.PAUSED},
    ExecutionState.PAUSED: {ExecutionState.RUNNING, ExecutionState.CANCELLED},
    ExecutionState.SUCCEEDED: {ExecutionState.COMPLETED, ExecutionState.ROLLBACK},
    ExecutionState.FAILED: {ExecutionState.ROLLBACK},
    ExecutionState.CANCELLED: set(),
    ExecutionState.ROLLBACK: {ExecutionState.FAILED, ExecutionState.COMPLETED},
    ExecutionState.COMPLETED: set(),
}


def validate_transition(from_state: ExecutionState, to_state: ExecutionState) -> bool:
    """Check if transitioning from_state to to_state is valid."""
    if from_state == to_state:
        return True
    return to_state in VALID_TRANSITIONS.get(from_state, set())
