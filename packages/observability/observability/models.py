"""Observability models (M5 Phase 4)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

__all__ = ["AgentTrace", "TraceEvent"]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TraceEvent(BaseModel):
    """An event within a trace."""
    
    timestamp: datetime = Field(default_factory=_utc_now)
    subsystem: str  # 'digital_twin', 'intelligence', 'engines', 'growth', 'brain'
    action: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    is_error: bool = False


class AgentTrace(BaseModel):
    """A full end-to-end trace from observation (M1) through decision (M5)."""
    
    trace_id: str
    tenant_id: str
    site_id: str | None = None
    
    started_at: datetime = Field(default_factory=_utc_now)
    completed_at: datetime | None = None
    
    events: list[TraceEvent] = Field(default_factory=list)
    
    def add_event(self, subsystem: str, action: str, metadata: dict[str, Any] | None = None, is_error: bool = False) -> None:
        self.events.append(TraceEvent(
            subsystem=subsystem,
            action=action,
            metadata=metadata or {},
            is_error=is_error,
        ))
