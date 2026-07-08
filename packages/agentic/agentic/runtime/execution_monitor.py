"""Execution Monitor for runtime telemetry (M6 Build Phase D)."""
from __future__ import annotations

import time
from typing import Any

from core.logging import get_logger

_log = get_logger("agentic_execution")


class ExecutionMonitor:
    """Real-time telemetry monitor for node/plan executions."""
    
    def record_node_start(
        self,
        tenant_id: str,
        execution_id: str,
        node_id: str,
        tool_name: str,
    ) -> float:
        start_time = time.time()
        _log.info(
            "Node execution started",
            tenant_id=tenant_id,
            execution_id=execution_id,
            node_id=node_id,
            tool=tool_name,
            start_time=start_time,
        )
        return start_time
        
    def record_node_finish(
        self,
        tenant_id: str,
        execution_id: str,
        node_id: str,
        tool_name: str,
        start_time: float,
        success: bool,
        error: str | None = None,
        tokens_used: int = 0,
        cost_dollars: float = 0.0,
    ) -> dict[str, Any]:
        end_time = time.time()
        duration = end_time - start_time
        
        metrics = {
            "node_id": node_id,
            "tool": tool_name,
            "duration": duration,
            "success": success,
            "error": error,
            "tokens_used": tokens_used,
            "cost_dollars": cost_dollars,
        }
        
        _log.info(
            "Node execution completed",
            tenant_id=tenant_id,
            execution_id=execution_id,
            metrics=metrics,
        )
        return metrics
