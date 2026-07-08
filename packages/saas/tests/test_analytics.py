"""Unit tests for System 3 Modern Analytics Platform."""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone

from saas.analytics.models import MetricAggregation, AlertRule
from saas.analytics.repositories import AnalyticsRepository
from saas.analytics.services import (
    AnalyticsAggregatorService,
    ReportGeneratorService,
    KPIEvaluatorService,
    AlertRuleService,
)


class TestAnalyticsSystem:
    def test_analytics_aggregation(self, db_session_factory):
        repo = AnalyticsRepository(db_session_factory, tenant_id="t1")
        service = AnalyticsAggregatorService(repo)

        agg = service.aggregate_hourly_metric("t1", "avg_response_time", [120.0, 180.0, 150.0])
        assert agg is not None
        assert agg.value == 150.0
        assert agg.metric_name == "avg_response_time"

        # Query back
        end = datetime.now(timezone.utc)
        start = end - timedelta(hours=1)
        res = repo.get_time_series("t1", "avg_response_time", start, end)
        assert len(res) == 1
        assert res[0].value == 150.0

        # Tenant isolation
        assert len(repo.get_time_series("t2", "avg_response_time", start, end)) == 0

    def test_report_pdf_generation(self):
        generator = ReportGeneratorService()
        metrics = [{"name": "Organic Traffic", "value": 5000}]
        pdf_bytes = generator.generate_pdf_report("t1", "Monthly Performance Review", metrics)
        
        report_text = pdf_bytes.decode("utf-8")
        assert "Monthly Performance Review" in report_text
        assert "Organic Traffic: 5000" in report_text

    def test_kpi_health_evaluation(self):
        kpi = KPIEvaluatorService()
        # Perfect metrics
        h1 = kpi.compute_site_health(error_rate=0.0, response_time_ms=200.0)
        assert h1 == 100.0

        # Highly degraded metrics
        h2 = kpi.compute_site_health(error_rate=0.10, response_time_ms=1200.0)
        # Penalty = (0.1 * 50) + (1000 / 10) = 5 + 100 = 105. Health should cap at 0.0
        assert h2 == 0.0

    def test_alert_rule_trigger(self, db_session_factory):
        repo = AnalyticsRepository(db_session_factory, tenant_id="t1")
        service = AlertRuleService(repo)

        r1 = service.create_rule("t1", "error_rate", 0.05, "above")
        r2 = service.create_rule("t1", "speed", 200.0, "below")

        # Evaluate metric: error_rate 0.08 triggers r1
        triggered1 = service.evaluate_metric("t1", "error_rate", 0.08)
        assert r1.id in triggered1

        # Evaluate metric: error_rate 0.02 does not trigger r1
        triggered2 = service.evaluate_metric("t1", "error_rate", 0.02)
        assert r1.id not in triggered2
