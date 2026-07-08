"""Analytics DB models and Pydantic schemas for System 3."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

try:
    from sqlalchemy import JSON
except ImportError:
    from sqlalchemy import Text as JSON

from saas.db import SaaSBase

__all__ = [
    "AnalyticsWidgetRow",
    "ReportTemplateRow",
    "MetricAggregationRow",
    "ScheduledExportRow",
    "AlertRuleRow",
    "AnalyticsWidget",
    "ReportTemplate",
    "MetricAggregation",
    "ScheduledExport",
    "AlertRule",
]


class AnalyticsWidgetRow(SaaSBase):
    """SQLAlchemy Row mapping a customized Dashboard Widget."""

    __tablename__ = "saas_analytics_widgets"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    dashboard_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    widget_type: Mapped[str] = mapped_column(String, nullable=False)  # "chart", "gauge", "table"
    metrics_json: Mapped[dict] = mapped_column(JSON, nullable=False)  # target metrics to display


class ReportTemplateRow(SaaSBase):
    """SQLAlchemy Row mapping a Report Layout Template."""

    __tablename__ = "saas_report_templates"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    layout_json: Mapped[dict] = mapped_column(JSON, nullable=False)


class MetricAggregationRow(SaaSBase):
    """SQLAlchemy Row mapping pre-aggregated time-series hourly values."""

    __tablename__ = "saas_metric_aggregations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    metric_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class ScheduledExportRow(SaaSBase):
    """SQLAlchemy Row mapping automated PDF/CSV report scheduling definitions."""

    __tablename__ = "saas_scheduled_exports"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    template_id: Mapped[str] = mapped_column(String, nullable=False)
    cron_expression: Mapped[str] = mapped_column(String, nullable=False)
    delivery_targets: Mapped[dict] = mapped_column(JSON, nullable=False)  # email destinations, webhooks
    last_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)


class AlertRuleRow(SaaSBase):
    """SQLAlchemy Row mapping threshold-based alerting configurations."""

    __tablename__ = "saas_alert_rules"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    metric_name: Mapped[str] = mapped_column(String, nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    comparison: Mapped[str] = mapped_column(String, nullable=False)  # "above", "below"
    channels_json: Mapped[dict] = mapped_column(JSON, nullable=False)  # e.g. slack, email


# ---- Pydantic schemas ----

class AnalyticsWidget(BaseModel):
    id: str
    tenant_id: str
    dashboard_id: str
    widget_type: str
    metrics_json: dict[str, Any] = Field(default_factory=dict)


class ReportTemplate(BaseModel):
    id: str
    tenant_id: str
    name: str
    layout_json: dict[str, Any] = Field(default_factory=dict)


class MetricAggregation(BaseModel):
    id: str
    tenant_id: str
    metric_name: str
    value: float
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ScheduledExport(BaseModel):
    id: str
    tenant_id: str
    template_id: str
    cron_expression: str
    delivery_targets: dict[str, Any] = Field(default_factory=dict)
    last_run_at: datetime | None = None


class AlertRule(BaseModel):
    id: str
    tenant_id: str
    metric_name: str
    threshold: float
    comparison: str
    channels_json: dict[str, Any] = Field(default_factory=dict)
