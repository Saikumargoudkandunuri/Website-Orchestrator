"""EventCorrelationEngine — link related events across sources (Phase 1).

Implements time-windowed grouping: events within a configurable window
sharing the same page cluster, keyword set, or site scope get correlated.
Deterministic — no AI calls.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from enterprise_intelligence.observation.models import (
    CorrelatedEventGroup,
    ObservationEvent,
)

__all__ = ["EventCorrelationEngine"]


class EventCorrelationEngine:
    """Correlate related observation events from different sources.

    Correlation criteria:
    1. Same tenant + site
    2. Within ``window_minutes`` of each other
    3. Sharing at least one common data key value (page_id, keyword, url)
    """

    def __init__(self, window_minutes: int = 60) -> None:
        self._window = timedelta(minutes=window_minutes)

    def correlate(self, events: list[ObservationEvent]) -> list[CorrelatedEventGroup]:
        """Find correlated groups in a batch of events.

        Returns groups with ≥2 members.  Each event may appear in at most
        one group (first match wins for simplicity).
        """
        if len(events) < 2:
            return []

        # Sort by time
        sorted_events = sorted(events, key=lambda e: e.created_at)

        # Group by tenant+site
        by_scope: dict[str, list[ObservationEvent]] = defaultdict(list)
        for ev in sorted_events:
            by_scope[f"{ev.tenant_id}:{ev.site_id}"].append(ev)

        groups: list[CorrelatedEventGroup] = []
        used_ids: set[str] = set()

        for scope_key, scope_events in by_scope.items():
            tenant_id = scope_events[0].tenant_id
            for i, anchor in enumerate(scope_events):
                if anchor.id in used_ids:
                    continue
                group_ids = [anchor.id]
                anchor_keys = self._extract_correlation_keys(anchor)
                if not anchor_keys:
                    continue

                for j in range(i + 1, len(scope_events)):
                    candidate = scope_events[j]
                    if candidate.id in used_ids:
                        continue
                    # Time window check
                    if candidate.created_at - anchor.created_at > self._window:
                        break
                    # Must be a different category (cross-source correlation)
                    if candidate.category == anchor.category:
                        continue
                    # Shared key check
                    cand_keys = self._extract_correlation_keys(candidate)
                    if anchor_keys & cand_keys:
                        group_ids.append(candidate.id)

                if len(group_ids) >= 2:
                    categories = set()
                    for eid in group_ids:
                        used_ids.add(eid)
                        for ev in scope_events:
                            if ev.id == eid:
                                categories.add(ev.category.value)
                                break
                    corr_type = "+".join(sorted(categories))
                    groups.append(
                        CorrelatedEventGroup(
                            tenant_id=tenant_id,
                            event_ids=group_ids,
                            correlation_type=corr_type,
                            confidence=min(1.0, 0.5 + 0.1 * len(group_ids)),
                            description=f"Correlated {len(group_ids)} events across {corr_type}",
                        )
                    )

        return groups

    @staticmethod
    def _extract_correlation_keys(event: ObservationEvent) -> set[str]:
        """Extract values used to correlate events (page_id, keyword, url)."""
        keys: set[str] = set()
        data = event.data
        for field in ("page_id", "page_ids", "keyword", "keywords", "url", "urls"):
            val = data.get(field)
            if isinstance(val, str) and val:
                keys.add(val)
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, str) and item:
                        keys.add(item)
        return keys
