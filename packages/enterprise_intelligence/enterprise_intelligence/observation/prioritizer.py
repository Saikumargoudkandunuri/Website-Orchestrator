"""EventPrioritizer — business-impact-aware event ranking (Phase 1).

Reuses M5 DecisionEngine's ScoringDimension pattern for normalised,
inspectable scoring rather than inventing a new heuristic.
"""

from __future__ import annotations

from enterprise_intelligence.observation.models import (
    EventCategory,
    EventSeverity,
    ObservationEvent,
)

__all__ = ["EventPrioritizer"]

# Severity weights
_SEVERITY_WEIGHTS: dict[EventSeverity, float] = {
    EventSeverity.CRITICAL: 1.0,
    EventSeverity.WARNING: 0.5,
    EventSeverity.INFO: 0.1,
}

# Category business-impact weights (normalised 0–1)
_CATEGORY_IMPACT: dict[EventCategory, float] = {
    EventCategory.RANKING: 0.9,
    EventCategory.ANALYTICS: 0.85,
    EventCategory.TECHNICAL: 0.8,
    EventCategory.BACKLINK: 0.7,
    EventCategory.CONTENT: 0.65,
    EventCategory.COMPETITOR: 0.6,
    EventCategory.REPUTATION: 0.55,
    EventCategory.LOCAL_SEO: 0.5,
    EventCategory.COST: 0.45,
    EventCategory.PLATFORM_HEALTH: 0.4,
    EventCategory.SECURITY: 0.95,
}


class EventPrioritizer:
    """Rank observation events by business impact.

    The composite score is: ``severity_weight * 0.4 + category_impact * 0.3 +
    confidence * 0.3``.  All components are normalised 0–1 and individually
    inspectable, following M5 ``ScoringDimension`` transparency.
    """

    def prioritize(self, events: list[ObservationEvent]) -> list[ObservationEvent]:
        """Return *events* sorted by descending business-impact score.

        Each event's ``business_impact_score`` is set as a side effect.
        """
        scored: list[tuple[float, ObservationEvent]] = []
        for event in events:
            score = self._score(event)
            updated = event.model_copy(update={"business_impact_score": score})
            scored.append((score, updated))
        scored.sort(key=lambda t: t[0], reverse=True)
        return [ev for _, ev in scored]

    def score(self, event: ObservationEvent) -> float:
        """Compute the business-impact score for a single event."""
        return self._score(event)

    def _score(self, event: ObservationEvent) -> float:
        sev_w = _SEVERITY_WEIGHTS.get(event.severity, 0.1)
        cat_w = _CATEGORY_IMPACT.get(event.category, 0.3)
        conf = max(0.0, min(1.0, event.confidence))
        return round(sev_w * 0.4 + cat_w * 0.3 + conf * 0.3, 4)
