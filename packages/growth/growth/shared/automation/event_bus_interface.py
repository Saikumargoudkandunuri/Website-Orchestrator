"""Typed event bus interface and DomainEvent model (§4.10, §9).

Engines emit DomainEvents at natural points in their own workflow.
The Automation Engine only *subscribes* — it never polls for state changes.

This is the cross-cutting event contract extending Milestone 1/2/3's existing
domain-event points with new event types for Milestone 4.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Protocol, runtime_checkable

from pydantic import BaseModel, Field

__all__ = [
    "DomainEvent",
    "EventHandler",
    "EventBus",
    "InMemoryEventBus",
    # Known event types as constants
    "EVENT_CRAWL_COMPLETED",
    "EVENT_AUDIT_COMPLETED",
    "EVENT_ISSUE_CRITICAL_DETECTED",
    "EVENT_RANKING_DROPPED",
    "EVENT_OPPORTUNITY_DETECTED",
    "EVENT_CONTENT_ASSET_PUBLISHED",
    "EVENT_TRAFFIC_DECREASED",
    "EVENT_REPORT_GENERATED",
    "EVENT_REPORT_GENERATION_FAILED",
    "EVENT_RANK_TRACKING_JOB_COMPLETED",
    "EVENT_RANK_TRACKING_JOB_FAILED",
    "EVENT_ANALYTICS_SNAPSHOT_CAPTURED",
    "EVENT_REVIEW_RECEIVED",
    "EVENT_NEGATIVE_REVIEW_DETECTED",
]

# --- Known event type constants ---
EVENT_CRAWL_COMPLETED = "crawl.completed"
EVENT_AUDIT_COMPLETED = "audit.completed"
EVENT_ISSUE_CRITICAL_DETECTED = "issue.critical_detected"
EVENT_RANKING_DROPPED = "ranking.dropped"
EVENT_OPPORTUNITY_DETECTED = "opportunity.detected"
EVENT_CONTENT_ASSET_PUBLISHED = "content_asset.published"
EVENT_TRAFFIC_DECREASED = "traffic.decreased"
EVENT_REPORT_GENERATED = "report.generated"
EVENT_REPORT_GENERATION_FAILED = "report.generation_failed"
EVENT_RANK_TRACKING_JOB_COMPLETED = "rank_tracking_job.completed"
EVENT_RANK_TRACKING_JOB_FAILED = "rank_tracking_job.failed"
EVENT_ANALYTICS_SNAPSHOT_CAPTURED = "analytics.snapshot_captured"
EVENT_REVIEW_RECEIVED = "review.received"
EVENT_NEGATIVE_REVIEW_DETECTED = "review.negative_detected"


class DomainEvent(BaseModel):
    """A typed domain event emitted by any engine (§4.10).

    The Automation Engine subscribes to these — it never polls other engines.

    Structured, serializable, and enumerable so a visual builder can be built
    against it later without backend changes.
    """

    event_type: str  # one of the EVENT_* constants above
    payload: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    site_id: str
    tenant_id: str = ""
    organization_id: str | None = None
    client_id: str | None = None
    source_engine: str | None = None  # which engine emitted this event


EventHandler = Callable[[DomainEvent], None]


@runtime_checkable
class EventBus(Protocol):
    """Typed event bus interface (§4.10)."""

    def publish(self, event: DomainEvent) -> None:
        """Publish a domain event to all registered subscribers."""
        ...

    def subscribe(
        self,
        event_type: str,
        handler: EventHandler,
    ) -> None:
        """Subscribe a handler to events of ``event_type``."""
        ...

    def subscribe_all(self, handler: EventHandler) -> None:
        """Subscribe a handler to ALL event types."""
        ...


class InMemoryEventBus:
    """Simple in-memory event bus for tests and single-process deployments.

    Not suitable for multi-process deployments — use a real message broker
    (Redis, RabbitMQ, etc.) for production via the EventBus interface.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = {}
        self._wildcard_handlers: list[EventHandler] = []
        # For test assertions
        self.published_events: list[DomainEvent] = []

    def publish(self, event: DomainEvent) -> None:
        self.published_events.append(event)
        # Notify type-specific handlers
        for handler in self._handlers.get(event.event_type, []):
            handler(event)
        # Notify wildcard handlers
        for handler in self._wildcard_handlers:
            handler(event)

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    def subscribe_all(self, handler: EventHandler) -> None:
        self._wildcard_handlers.append(handler)

    def clear(self) -> None:
        """Clear all subscriptions and events (for test teardown)."""
        self._handlers.clear()
        self._wildcard_handlers.clear()
        self.published_events.clear()
