"""Repositories for Scheduler models."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from intelligence.repositories._session import SessionMixin
from brain.scheduler.db import AutomationRuleRecord, ExecutionLogRecord, ScheduleRecord
from brain.scheduler.models import AutomationRule, ExecutionLog, OrchestrationSchedule

__all__ = [
    "ScheduleRepository",
    "AutomationRuleRepository",
    "ExecutionLogRepository",
]


class ScheduleRepository(SessionMixin):
    """Persistence for OrchestrationSchedule."""

    def save(self, schedule: OrchestrationSchedule) -> None:
        with self.session() as session:
            record = session.get(ScheduleRecord, schedule.id)
            if not record:
                record = ScheduleRecord(
                    id=schedule.id,
                    tenant_id=schedule.tenant_id,
                    site_id=schedule.site_id,
                    is_active=schedule.is_active,
                    payload=schedule.model_dump(mode="json"),
                )
                session.add(record)
            else:
                record.is_active = schedule.is_active
                record.payload = schedule.model_dump(mode="json")
            session.commit()

    def get_all_for_site(
        self, tenant_id: str, site_id: str, active_only: bool = False
    ) -> list[OrchestrationSchedule]:
        with self.session() as session:
            stmt = select(ScheduleRecord).where(
                ScheduleRecord.tenant_id == tenant_id,
                ScheduleRecord.site_id == site_id,
            )
            if active_only:
                stmt = stmt.where(ScheduleRecord.is_active.is_(True))
            records = session.execute(stmt).scalars().all()
            return [OrchestrationSchedule.model_validate(r.payload) for r in records]


class AutomationRuleRepository(SessionMixin):
    """Persistence for AutomationRule."""

    def save(self, rule: AutomationRule) -> None:
        with self.session() as session:
            record = session.get(AutomationRuleRecord, rule.id)
            if not record:
                record = AutomationRuleRecord(
                    id=rule.id,
                    tenant_id=rule.tenant_id,
                    site_id=rule.site_id,
                    is_active=rule.is_active,
                    payload=rule.model_dump(mode="json"),
                )
                session.add(record)
            else:
                record.is_active = rule.is_active
                record.payload = rule.model_dump(mode="json")
            session.commit()

    def get_all_for_site(
        self, tenant_id: str, site_id: str, active_only: bool = False
    ) -> list[AutomationRule]:
        with self.session() as session:
            stmt = select(AutomationRuleRecord).where(
                AutomationRuleRecord.tenant_id == tenant_id,
                AutomationRuleRecord.site_id == site_id,
            )
            if active_only:
                stmt = stmt.where(AutomationRuleRecord.is_active.is_(True))
            records = session.execute(stmt).scalars().all()
            return [AutomationRule.model_validate(r.payload) for r in records]


class ExecutionLogRepository(SessionMixin):
    """Persistence for ExecutionLog."""

    def save(self, log: ExecutionLog) -> None:
        with self.session() as session:
            record = session.get(ExecutionLogRecord, log.id)
            if not record:
                record = ExecutionLogRecord(
                    id=log.id,
                    tenant_id=log.tenant_id,
                    site_id=log.site_id,
                    source_id=log.source_id,
                    source_type=log.source_type,
                    status=log.status,
                    started_at=log.started_at,
                    payload=log.model_dump(mode="json"),
                )
                session.add(record)
            else:
                record.status = log.status
                record.payload = log.model_dump(mode="json")
            session.commit()

    def get_recent(self, tenant_id: str, site_id: str, limit: int = 50) -> list[ExecutionLog]:
        with self.session() as session:
            stmt = (
                select(ExecutionLogRecord)
                .where(
                    ExecutionLogRecord.tenant_id == tenant_id,
                    ExecutionLogRecord.site_id == site_id,
                )
                .order_by(ExecutionLogRecord.started_at.desc())
                .limit(limit)
            )
            records = session.execute(stmt).scalars().all()
            return [ExecutionLog.model_validate(r.payload) for r in records]
