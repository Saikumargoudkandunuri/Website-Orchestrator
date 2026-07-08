"""PredictiveAlerts — the only observation component using AI (Phase 1).

This is allowed to use the AIProvider to flag "this looks like it's heading
toward a problem."  It **never** autonomously acts — it produces an
ObservationEvent with a prediction, consumed by Phase 3 Goal Generation.
"""

from __future__ import annotations

import json
from typing import Any

from enterprise_intelligence.observation.models import (
    EventCategory,
    EventSeverity,
    ObservationEvent,
)
from intelligence.ai.provider_interface import (
    AICompletionRequest,
    AIProvider,
)
from core.results import Err

__all__ = ["PredictiveAlerts"]


class PredictiveAlerts:
    """Generate predictive alerts using AI analysis of trend data.

    The only Phase 1 component allowed to call the AIProvider.  Produces
    observation events — never actions.
    """

    def __init__(self, provider: AIProvider) -> None:
        self._provider = provider

    def predict(
        self,
        tenant_id: str,
        site_id: str,
        metric_name: str,
        recent_values: list[float],
        context: dict[str, Any] | None = None,
    ) -> ObservationEvent | None:
        """Analyse a metric trend and produce a predictive alert if warranted.

        Returns ``None`` if no alert is warranted or the AI call fails.
        """
        if len(recent_values) < 5:
            return None

        system_prompt = (
            "You are a data analyst. Given a time-series of metric values, "
            "determine if the trend is heading toward a problem. Respond with "
            "JSON: {\"alert\": true/false, \"severity\": \"info\"/\"warning\"/\"critical\", "
            "\"reason\": \"explanation\", \"confidence\": 0.0-1.0}"
        )

        user_prompt = (
            f"Metric: {metric_name}\n"
            f"Recent values (oldest first): {recent_values}\n"
            f"Context: {json.dumps(context or {})}\n"
            "Is this trend heading toward a problem?"
        )

        request = AICompletionRequest(
            prompt=user_prompt,
            system_prompt=system_prompt,
            json_mode=True,
            metadata={"capability": "predictive_alert"},
        )

        result = self._provider.complete(request)
        if isinstance(result, Err):
            return None

        try:
            data = json.loads(result.value.raw_text)
            if not data.get("alert", False):
                return None

            severity_map = {
                "critical": EventSeverity.CRITICAL,
                "warning": EventSeverity.WARNING,
                "info": EventSeverity.INFO,
            }

            return ObservationEvent(
                tenant_id=tenant_id,
                site_id=site_id,
                category=EventCategory.ANALYTICS,
                severity=severity_map.get(data.get("severity", "info"), EventSeverity.INFO),
                source_engine="predictive_alerts",
                source_ref=f"prediction:{metric_name}",
                title=f"Predictive alert: {metric_name}",
                description=data.get("reason", "Trend heading toward a problem"),
                data={
                    "metric_name": metric_name,
                    "recent_values": recent_values,
                    "prediction_type": "trend_alert",
                },
                confidence=float(data.get("confidence", 0.5)),
            )
        except (json.JSONDecodeError, ValueError, TypeError):
            return None
