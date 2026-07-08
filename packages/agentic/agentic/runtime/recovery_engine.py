"""Recovery Engine for retrying and handling errors (M6 Build Phase D)."""
from __future__ import annotations

from typing import Any

from agentic.planning.models import ExecutionNode


class RecoveryEngine:
    """Handles retries and decides if errors are transient or permanent."""
    
    def should_retry(
        self,
        node: ExecutionNode,
        current_retries: int,
        error: Exception,
    ) -> bool:
        """
        Check if the node execution should be retried.
        """
        # Read max_retries parameter from requirements or default to 3
        max_retries = node.required_inputs.get("max_retries", 3)
        return current_retries < max_retries

    def get_retry_delay(self, node: ExecutionNode, current_retries: int) -> float:
        """Calculate exponential backoff retry delay."""
        return float(2 ** current_retries)
