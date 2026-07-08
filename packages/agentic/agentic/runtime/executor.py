"""Executor for executing individual plan nodes (M6 Build Phase D)."""
from __future__ import annotations

import time
from typing import Any, Callable

from agentic.planning.models import ExecutionNode
from agentic.tools.registry import ToolRegistry


class Executor:
    """Resolves and executes tools registered in the ToolRegistry."""
    
    def __init__(
        self,
        registry: ToolRegistry,
        handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] | None = None,
    ) -> None:
        self.registry = registry
        self.handlers = handlers or {}
        
    def execute_node(
        self,
        node: ExecutionNode,
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Execute one plan node's tool with resolved parameters.
        """
        tool_name = node.action_type or ""
        metadata = self.registry.get_by_name(tool_name)
        if not metadata:
            raise ValueError(f"Tool '{tool_name}' not found in registry.")

        # Resolve handler or use a default mock execution
        handler = self.handlers.get(tool_name)
        if handler:
            try:
                return handler(inputs)
            except Exception as e:
                raise RuntimeError(f"Tool execution failed: {e}") from e
        else:
            # Default mock output matching the tool
            time.sleep(0.01)  # Simulate small delay
            return {
                "status": "success",
                "tool_executed": tool_name,
                "node_id": node.id,
                "output_data": f"Executed tool {tool_name} successfully.",
            }
