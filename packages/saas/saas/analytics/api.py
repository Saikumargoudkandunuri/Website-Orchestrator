"""FastAPI Router endpoints for System 3 Modern Analytics Platform."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from saas.analytics.models import AlertRule, MetricAggregation
from saas.analytics.services import (
    AnalyticsAggregatorService,
    ReportGeneratorService,
    KPIEvaluatorService,
    AlertRuleService,
)

__all__ = ["build_analytics_router"]


class MetricQueryRequest(BaseModel):
    metric_name: str
    start_time: datetime
    end_time: datetime


class ExportReportRequest(BaseModel):
    title: str
    metrics: list[dict[str, Any]]


class AlertRuleCreateRequest(BaseModel):
    metric_name: str
    threshold: float
    comparison: str


def build_analytics_router(
    aggregator: AnalyticsAggregatorService,
    generator: ReportGeneratorService,
    kpi: KPIEvaluatorService,
    alerts: AlertRuleService,
) -> APIRouter:
    router = APIRouter(prefix="/v1/analytics", tags=["Modern Analytics"])

    @router.get("/dashboards/{id}")
    def get_dashboard(id: str, tenant_id: str) -> dict[str, Any]:
        # Return mock layout + computed summary
        return {
            "dashboard_id": id,
            "tenant_id": tenant_id,
            "status": "active",
            "widgets": [
                {"i": "traffic", "type": "chart", "h": 2},
                {"i": "health", "type": "gauge", "h": 1},
            ],
            "computed_health": kpi.compute_site_health(0.02, 180.0),
        }

    @router.post("/query", response_model=list[MetricAggregation])
    def query_metrics(req: MetricQueryRequest, tenant_id: str) -> list[MetricAggregation]:
        return aggregator._repo.get_time_series(
            tenant_id=tenant_id,
            metric_name=req.metric_name,
            start=req.start_time,
            end=req.end_time,
        )

    @router.post("/exports")
    def export_report(req: ExportReportRequest, tenant_id: str) -> Response:
        pdf_bytes = generator.generate_pdf_report(tenant_id, req.title, req.metrics)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=report_{tenant_id}.pdf"},
        )

    @router.get("/alerts", response_model=list[AlertRule])
    def list_alerts(tenant_id: str) -> list[AlertRule]:
        return alerts._repo.list_alert_rules(tenant_id)

    @router.post("/alerts", response_model=AlertRule)
    def create_alert(req: AlertRuleCreateRequest, tenant_id: str) -> AlertRule:
        return alerts.create_rule(
            tenant_id=tenant_id,
            metric=req.metric_name,
            threshold=req.threshold,
            comparison=req.comparison,
        )

    return router
