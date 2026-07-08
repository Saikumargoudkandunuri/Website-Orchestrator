"""Platform Observability Aggregator (M5 Phase 4)."""

from __future__ import annotations

import logging
from typing import Any

from observability.models import AgentTrace

__all__ = ["PlatformObservabilityAggregator", "get_aggregator"]

logger = logging.getLogger("wo.observability")


class PlatformObservabilityAggregator:
    """Mocks a log aggregator for platform-wide observability."""

    def __init__(self) -> None:
        self.traces: dict[str, AgentTrace] = {}
        self.errors: list[dict[str, Any]] = []

    def start_trace(self, trace_id: str, tenant_id: str, site_id: str | None = None) -> AgentTrace:
        trace = AgentTrace(trace_id=trace_id, tenant_id=tenant_id, site_id=site_id)
        self.traces[trace_id] = trace
        return trace

    def record_error(self, error: Exception, trace_id: str | None = None, context: dict[str, Any] | None = None) -> None:
        """Record an application error, optionally linking to a trace."""
        record = {
            "error_type": type(error).__name__,
            "message": str(error),
            "trace_id": trace_id,
            "context": context or {},
        }
        self.errors.append(record)
        logger.error(f"Platform Error: {record}")
        
        if trace_id and trace_id in self.traces:
            self.traces[trace_id].add_event(
                subsystem="platform",
                action="unhandled_error",
                metadata=record,
                is_error=True,
            )


# A global singleton for the in-memory mock aggregator.
_AGGREGATOR = PlatformObservabilityAggregator()


def get_aggregator() -> PlatformObservabilityAggregator:
    """Return the global aggregator singleton."""
    return _AGGREGATOR
