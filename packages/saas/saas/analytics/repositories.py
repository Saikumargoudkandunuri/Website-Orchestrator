"""Analytics Repositories for System 3."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from sqlalchemy import select, delete

from intelligence.repositories._session import SessionMixin
from saas.analytics.models import (
    MetricAggregationRow,
    AlertRuleRow,
    MetricAggregation,
    AlertRule,
)

__all__ = ["AnalyticsRepository"]


class AnalyticsRepository(SessionMixin):
    """SaaS Analytics Repository managing time-series hourly values and alert rules."""

    def save_aggregation(self, agg: MetricAggregation) -> None:
        tenant = self._resolve_tenant(agg.tenant_id)
        with self._session() as session:
            session.add(MetricAggregationRow(
                id=agg.id,
                tenant_id=tenant,
                metric_name=agg.metric_name,
                value=agg.value,
                timestamp=agg.timestamp,
            ))
            session.commit()

    def get_time_series(self, tenant_id: str, metric_name: str, start: datetime, end: datetime) -> list[MetricAggregation]:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            rows = session.execute(
                select(MetricAggregationRow).where(
                    MetricAggregationRow.tenant_id == tenant,
                    MetricAggregationRow.metric_name == metric_name,
                    MetricAggregationRow.timestamp >= start,
                    MetricAggregationRow.timestamp <= end,
                ).order_by(MetricAggregationRow.timestamp.asc())
            ).scalars().all()
            return [
                MetricAggregation(
                    id=r.id,
                    tenant_id=r.tenant_id,
                    metric_name=r.metric_name,
                    value=r.value,
                    timestamp=r.timestamp,
                )
                for r in rows
            ]

    def save_alert_rule(self, rule: AlertRule) -> None:
        tenant = self._resolve_tenant(rule.tenant_id)
        with self._session() as session:
            existing = session.get(AlertRuleRow, rule.id)
            if existing:
                existing.threshold = rule.threshold
                existing.comparison = rule.comparison
                existing.channels_json = rule.channels_json
            else:
                session.add(AlertRuleRow(
                    id=rule.id,
                    tenant_id=tenant,
                    metric_name=rule.metric_name,
                    threshold=rule.threshold,
                    comparison=rule.comparison,
                    channels_json=rule.channels_json,
                ))
            session.commit()

    def list_alert_rules(self, tenant_id: str) -> list[AlertRule]:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            rows = session.execute(
                select(AlertRuleRow).where(AlertRuleRow.tenant_id == tenant)
            ).scalars().all()
            return [
                AlertRule(
                    id=r.id,
                    tenant_id=r.tenant_id,
                    metric_name=r.metric_name,
                    threshold=r.threshold,
                    comparison=r.comparison,
                    channels_json=r.channels_json,
                )
                for r in rows
            ]
