"""EventBus — publish/subscribe for observation events (Phase 1).

Extends M5's PlatformScheduler rule-evaluation pattern.  This is NOT a
second event bus — it reuses the pub/sub concept from the scheduler but
applies it to continuously-observed events rather than cron-triggered tasks.

The EventBus is *always-on*: subscribers register once and receive every
event published for their tenant.  The bus itself never acts on events —
it is a delivery mechanism only.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Callable, Protocol

from enterprise_intelligence.observation.models import ObservationEvent

__all__ = ["EventBus", "EventSubscriber"]

logger = logging.getLogger(__name__)


class EventSubscriber(Protocol):
    """Protocol for anything that wants to receive observation events."""

    def on_event(self, event: ObservationEvent) -> None:
        """Handle a single observation event.  Must not raise."""
        ...


class EventBus:
    """In-process pub/sub for observation events.

    Subscribers register for specific categories (or ``"*"`` for all).
    Publishing is synchronous and in-process — no external broker — consistent
    with the project's deterministic-first discipline.

    Thread-safety note: this is *not* thread-safe by design.  The platform's
    execution model is single-threaded async; if that changes, add a lock.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventSubscriber]] = defaultdict(list)
        self._published_count: int = 0

    def subscribe(self, category: str, subscriber: EventSubscriber) -> None:
        """Register *subscriber* for events of *category* (or ``"*"`` for all)."""
        self._subscribers[category].append(subscriber)
        logger.debug("Subscriber %s registered for category '%s'", subscriber, category)

    def publish(self, event: ObservationEvent) -> None:
        """Deliver *event* to all matching subscribers.

        Delivery order: category-specific subscribers first, then wildcard
        subscribers.  A subscriber that raises is logged and skipped — one
        bad subscriber must not prevent delivery to others.
        """
        self._published_count += 1
        targets = list(self._subscribers.get(event.category.value, []))
        targets.extend(self._subscribers.get("*", []))

        for subscriber in targets:
            try:
                subscriber.on_event(event)
            except Exception:
                logger.exception(
                    "Subscriber %s failed on event %s — skipping",
                    subscriber,
                    event.id,
                )

    @property
    def published_count(self) -> int:
        """Total events published through this bus instance."""
        return self._published_count

    @property
    def subscriber_count(self) -> int:
        """Total registered subscribers (including duplicates across categories)."""
        return sum(len(subs) for subs in self._subscribers.values())
