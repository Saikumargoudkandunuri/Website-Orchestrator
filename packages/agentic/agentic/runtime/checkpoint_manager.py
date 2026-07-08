"""Checkpoint Manager for persisting execution progress (M6 Build Phase D)."""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class ExecutionCheckpoint(BaseModel):
    """Snapshot of plan execution progress."""
    execution_id: str
    tenant_id: str
    current_node_id: str | None = None
    completed_node_ids: list[str] = Field(default_factory=list)
    outputs: dict[str, Any] = Field(default_factory=dict)
    state: str = "created"


class CheckpointManager:
    """Manages checkpoint saving and recovery to prevent re-executing steps."""
    
    def __init__(self, repository: Any) -> None:
        self._repo = repository
        
    def save_checkpoint(self, checkpoint: ExecutionCheckpoint) -> None:
        """Save a checkpoint snapshot."""
        self._repo.save(checkpoint)
        
    def load_checkpoint(self, tenant_id: str, execution_id: str) -> ExecutionCheckpoint | None:
        """Retrieve a checkpoint snapshot."""
        return self._repo.load(tenant_id, execution_id)
