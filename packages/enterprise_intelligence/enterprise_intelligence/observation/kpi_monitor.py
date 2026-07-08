"""KpiMonitoring — threshold-based KPI alerting (Phase 1).

Deterministic threshold checks — no AI calls.
"""

from __future__ import annotations

from enterprise_intelligence.observation.models import EventSeverity, KpiAlert

__all__ = ["KpiMonitor"]


class KpiThreshold:
    """A configured KPI threshold."""

    def __init__(
        self,
        kpi_name: str,
        warning_threshold: float,
        critical_threshold: float,
        direction: str = "below",
    ) -> None:
        self.kpi_name = kpi_name
        self.warning = warning_threshold
        self.critical = critical_threshold
        self.direction = direction  # "below" = alert when value drops below; "above" = alert when rises above


class KpiMonitor:
    """Monitor KPIs against configured thresholds.

    Each KPI has a warning and critical threshold.  Alerts fire when a
    metric value breaches the threshold in the configured direction.
    """

    def __init__(self, thresholds: list[KpiThreshold] | None = None) -> None:
        self._thresholds: dict[str, KpiThreshold] = {}
        for t in (thresholds or []):
            self._thresholds[t.kpi_name] = t

    def add_threshold(self, threshold: KpiThreshold) -> None:
        """Register a KPI threshold."""
        self._thresholds[threshold.kpi_name] = threshold

    def check(self, kpi_name: str, value: float) -> KpiAlert | None:
        """Check a KPI value against its configured threshold.

        Returns ``None`` if no alert fires.
        """
        threshold = self._thresholds.get(kpi_name)
        if not threshold:
            return None

        if threshold.direction == "below":
            if value <= threshold.critical:
                return KpiAlert(
                    kpi_name=kpi_name,
                    current_value=value,
                    threshold=threshold.critical,
                    direction="below",
                    severity=EventSeverity.CRITICAL,
                )
            if value <= threshold.warning:
                return KpiAlert(
                    kpi_name=kpi_name,
                    current_value=value,
                    threshold=threshold.warning,
                    direction="below",
                    severity=EventSeverity.WARNING,
                )
        elif threshold.direction == "above":
            if value >= threshold.critical:
                return KpiAlert(
                    kpi_name=kpi_name,
                    current_value=value,
                    threshold=threshold.critical,
                    direction="above",
                    severity=EventSeverity.CRITICAL,
                )
            if value >= threshold.warning:
                return KpiAlert(
                    kpi_name=kpi_name,
                    current_value=value,
                    threshold=threshold.warning,
                    direction="above",
                    severity=EventSeverity.WARNING,
                )

        return None

    def check_all(self, metrics: dict[str, float]) -> list[KpiAlert]:
        """Check all provided metrics against their thresholds."""
        alerts: list[KpiAlert] = []
        for name, value in metrics.items():
            alert = self.check(name, value)
            if alert:
                alerts.append(alert)
        return alerts
