"""Analytics Services for System 3."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

from saas.analytics.models import MetricAggregation, AlertRule
from saas.analytics.repositories import AnalyticsRepository

__all__ = [
    "AnalyticsAggregatorService",
    "ReportGeneratorService",
    "KPIEvaluatorService",
    "AlertRuleService",
]

logger = logging.getLogger(__name__)


class AnalyticsAggregatorService:
    """Service summarizing raw system logs into aggregated metrics."""

    def __init__(self, repo: AnalyticsRepository) -> None:
        self._repo = repo

    def aggregate_hourly_metric(self, tenant_id: str, name: str, values: list[float]) -> MetricAggregation | None:
        """Run statistical rollup (average value) and write aggregation record."""
        if not values:
            return None
        avg_val = sum(values) / len(values)
        agg = MetricAggregation(
            id=str(uuid4()),
            tenant_id=tenant_id,
            metric_name=name,
            value=avg_val,
            timestamp=datetime.now(timezone.utc),
        )
        self._repo.save_aggregation(agg)
        return agg


class ReportGeneratorService:
    """Renders structured reports into static download/export payloads."""

    def generate_pdf_report(self, tenant_id: str, title: str, metrics: list[dict[str, Any]]) -> bytes:
        """Compile mock PDF report payload."""
        report_data = f"Report: {title}\nTenant: {tenant_id}\nGenerated: {datetime.now(timezone.utc)}\n"
        for m in metrics:
            report_data += f"- {m.get('name')}: {m.get('value')}\n"
        return report_data.encode("utf-8")


class KPIEvaluatorService:
    """Evaluates business KPIs and aggregates health ratings."""

    def compute_site_health(self, error_rate: float, response_time_ms: float) -> float:
        """Calculate generic health score ranging from 0.0 to 100.0."""
        # Simple weighted penalty
        penalty = (error_rate * 50.0) + (max(0.0, response_time_ms - 200.0) / 10.0)
        return max(0.0, min(100.0, 100.0 - penalty))


class AlertRuleService:
    """Evaluates metrics against threshold alert rules."""

    def __init__(self, repo: AnalyticsRepository) -> None:
        self._repo = repo

    def create_rule(self, tenant_id: str, metric: str, threshold: float, comparison: str) -> AlertRule:
        rule = AlertRule(
            id=str(uuid4()),
            tenant_id=tenant_id,
            metric_name=metric,
            threshold=threshold,
            comparison=comparison,
            channels_json={"slack": True, "email": True},
        )
        self._repo.save_alert_rule(rule)
        return rule

    def evaluate_metric(self, tenant_id: str, metric: str, current_value: float) -> list[str]:
        """Check current value against registered alert rules.

        Returns a list of fired alert IDs.
        """
        rules = self._repo.list_alert_rules(tenant_id)
        triggered = []
        for r in rules:
            if r.metric_name != metric:
                continue
            if r.comparison == "above" and current_value > r.threshold:
                triggered.append(r.id)
            elif r.comparison == "below" and current_value < r.threshold:
                triggered.append(r.id)
        return triggered
