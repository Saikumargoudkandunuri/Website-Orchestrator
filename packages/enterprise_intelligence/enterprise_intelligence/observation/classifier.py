"""EventClassifier — deterministic rule-based classification (Phase 1).

Assigns category and severity to raw adapter observations using typed rules.
No AI calls — this is arithmetic classification only.
"""

from __future__ import annotations

from enterprise_intelligence.observation.models import (
    EventCategory,
    EventSeverity,
    ObservationEvent,
)

__all__ = ["EventClassifier"]


# Severity thresholds per category (configurable defaults)
_SEVERITY_RULES: dict[EventCategory, dict[str, float]] = {
    EventCategory.RANKING: {"critical_drop": 10, "warning_drop": 3},
    EventCategory.TECHNICAL: {"critical_score": 0.3, "warning_score": 0.6},
    EventCategory.BACKLINK: {"critical_loss_pct": 0.20, "warning_loss_pct": 0.05},
    EventCategory.ANALYTICS: {"critical_drop_pct": 0.30, "warning_drop_pct": 0.10},
    EventCategory.REPUTATION: {"critical_sentiment": 0.3, "warning_sentiment": 0.5},
    EventCategory.COST: {"critical_increase_pct": 0.50, "warning_increase_pct": 0.20},
}


class EventClassifier:
    """Deterministic classifier assigning severity to observation events.

    Severity is computed from the event's ``data`` payload using typed
    threshold rules per category.  No AI provider is involved.
    """

    def classify(self, event: ObservationEvent) -> ObservationEvent:
        """Return a copy of *event* with severity (re-)computed from data thresholds."""
        severity = self._compute_severity(event)
        return event.model_copy(update={"severity": severity})

    def _compute_severity(self, event: ObservationEvent) -> EventSeverity:
        rules = _SEVERITY_RULES.get(event.category)
        if not rules:
            return EventSeverity.INFO

        data = event.data

        if event.category == EventCategory.RANKING:
            drop = abs(data.get("position_change", 0))
            if drop >= rules["critical_drop"]:
                return EventSeverity.CRITICAL
            if drop >= rules["warning_drop"]:
                return EventSeverity.WARNING
            return EventSeverity.INFO

        if event.category == EventCategory.TECHNICAL:
            score = data.get("health_score", 1.0)
            if score <= rules["critical_score"]:
                return EventSeverity.CRITICAL
            if score <= rules["warning_score"]:
                return EventSeverity.WARNING
            return EventSeverity.INFO

        if event.category == EventCategory.BACKLINK:
            loss_pct = data.get("loss_percentage", 0.0)
            if loss_pct >= rules["critical_loss_pct"]:
                return EventSeverity.CRITICAL
            if loss_pct >= rules["warning_loss_pct"]:
                return EventSeverity.WARNING
            return EventSeverity.INFO

        if event.category == EventCategory.ANALYTICS:
            drop_pct = abs(data.get("change_percentage", 0.0))
            if drop_pct >= rules["critical_drop_pct"]:
                return EventSeverity.CRITICAL
            if drop_pct >= rules["warning_drop_pct"]:
                return EventSeverity.WARNING
            return EventSeverity.INFO

        if event.category == EventCategory.REPUTATION:
            sentiment = data.get("sentiment_score", 1.0)
            if sentiment <= rules["critical_sentiment"]:
                return EventSeverity.CRITICAL
            if sentiment <= rules["warning_sentiment"]:
                return EventSeverity.WARNING
            return EventSeverity.INFO

        if event.category == EventCategory.COST:
            increase = data.get("increase_percentage", 0.0)
            if increase >= rules["critical_increase_pct"]:
                return EventSeverity.CRITICAL
            if increase >= rules["warning_increase_pct"]:
                return EventSeverity.WARNING
            return EventSeverity.INFO

        return EventSeverity.INFO
