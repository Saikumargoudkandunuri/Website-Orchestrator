"""Database schema for the Scheduler on BrainBase."""

from __future__ import annotations

import datetime

from sqlalchemy import JSON, Boolean, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from brain.db import BrainBase

__all__ = [
    "ScheduleRecord",
    "AutomationRuleRecord",
    "ExecutionLogRecord",
]


class ScheduleRecord(BrainBase):
    """Persistence for OrchestrationSchedule."""
    __tablename__ = "schedules"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False)
    site_id: Mapped[str] = mapped_column(String, nullable=False)
    
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    
    # JSON dump of the full model
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )

    __table_args__ = (
        Index("ix_schedules_tenant_site", "tenant_id", "site_id"),
    )


class AutomationRuleRecord(BrainBase):
    """Persistence for AutomationRule."""
    __tablename__ = "automation_rules"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False)
    site_id: Mapped[str] = mapped_column(String, nullable=False)
    
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    
    # JSON dump of the full model
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )

    __table_args__ = (
        Index("ix_automation_rules_tenant_site", "tenant_id", "site_id"),
    )


class ExecutionLogRecord(BrainBase):
    """Persistence for ExecutionLog."""
    __tablename__ = "execution_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False)
    site_id: Mapped[str] = mapped_column(String, nullable=False)
    
    source_id: Mapped[str] = mapped_column(String, nullable=False)
    source_type: Mapped[str] = mapped_column(String, nullable=False)
    
    status: Mapped[str] = mapped_column(String, nullable=False)
    
    # JSON dump of the full model
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    
    started_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_exec_logs_tenant_site", "tenant_id", "site_id"),
        Index("ix_exec_logs_source", "source_id"),
    )
