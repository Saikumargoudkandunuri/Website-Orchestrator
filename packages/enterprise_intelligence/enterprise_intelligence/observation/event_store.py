"""EventStore — append-only, tenant-scoped persistence of observation events (Phase 1).

Follows the same ``SessionMixin`` + append-only versioned pattern established
in M2's ``KnowledgeObjectRepository`` and M3's ``EngineRepoMixin``.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, func

from intelligence.repositories._session import SessionMixin
from enterprise_intelligence.db import ObservationEventRow, CorrelatedEventGroupRow
from enterprise_intelligence.observation.models import (
    ObservationEvent,
    CorrelatedEventGroup,
)

__all__ = ["EventStore"]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EventStore(SessionMixin):
    """Append-only, tenant-scoped repository for observation events.

    Every write is an insert — events are never updated or deleted,
    matching the platform's append-only discipline since M2.
    """

    def save_event(self, event: ObservationEvent) -> None:
        """Persist an observation event (append-only)."""
        tenant = self._resolve_tenant(event.tenant_id)
        with self._session() as session:
            row = ObservationEventRow(
                id=event.id,
                tenant_id=tenant,
                site_id=event.site_id,
                category=event.category.value,
                severity=event.severity.value,
                source_engine=event.source_engine,
                source_ref=event.source_ref,
                title=event.title,
                description=event.description,
                data=event.data,
                confidence=event.confidence,
                created_at=event.created_at,
                version=event.version,
            )
            session.add(row)
            session.commit()

    def get_event(self, tenant_id: str, event_id: str) -> ObservationEvent | None:
        """Retrieve a single event by ID."""
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            row = session.execute(
                select(ObservationEventRow).where(
                    ObservationEventRow.tenant_id == tenant,
                    ObservationEventRow.id == event_id,
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            return self._row_to_event(row)

    def list_events(
        self,
        tenant_id: str,
        *,
        site_id: str | None = None,
        category: str | None = None,
        limit: int = 100,
    ) -> list[ObservationEvent]:
        """List events for a tenant, optionally filtered."""
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            stmt = select(ObservationEventRow).where(
                ObservationEventRow.tenant_id == tenant,
            )
            if site_id:
                stmt = stmt.where(ObservationEventRow.site_id == site_id)
            if category:
                stmt = stmt.where(ObservationEventRow.category == category)
            stmt = stmt.order_by(ObservationEventRow.created_at.desc()).limit(limit)
            rows = session.execute(stmt).scalars().all()
            return [self._row_to_event(r) for r in rows]

    def count_events(self, tenant_id: str) -> int:
        """Count total events for a tenant."""
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            result = session.execute(
                select(func.count(ObservationEventRow.id)).where(
                    ObservationEventRow.tenant_id == tenant,
                )
            ).scalar()
            return result or 0

    def save_correlation(self, group: CorrelatedEventGroup) -> None:
        """Persist a correlated event group."""
        tenant = self._resolve_tenant(group.tenant_id)
        with self._session() as session:
            row = CorrelatedEventGroupRow(
                id=group.id,
                tenant_id=tenant,
                event_ids=group.event_ids,
                correlation_type=group.correlation_type,
                confidence=group.confidence,
                created_at=group.created_at,
            )
            session.add(row)
            session.commit()

    def list_correlations(
        self, tenant_id: str, *, limit: int = 50
    ) -> list[CorrelatedEventGroup]:
        """List correlated event groups."""
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            stmt = (
                select(CorrelatedEventGroupRow)
                .where(CorrelatedEventGroupRow.tenant_id == tenant)
                .order_by(CorrelatedEventGroupRow.created_at.desc())
                .limit(limit)
            )
            rows = session.execute(stmt).scalars().all()
            return [
                CorrelatedEventGroup(
                    id=r.id,
                    tenant_id=r.tenant_id,
                    event_ids=r.event_ids,
                    correlation_type=r.correlation_type,
                    confidence=r.confidence,
                    created_at=r.created_at,
                )
                for r in rows
            ]

    @staticmethod
    def _row_to_event(row: ObservationEventRow) -> ObservationEvent:
        from enterprise_intelligence.observation.models import EventCategory, EventSeverity

        return ObservationEvent(
            id=row.id,
            tenant_id=row.tenant_id,
            site_id=row.site_id,
            category=EventCategory(row.category),
            severity=EventSeverity(row.severity),
            source_engine=row.source_engine,
            source_ref=row.source_ref,
            title=row.title,
            description=row.description,
            data=row.data,
            confidence=row.confidence,
            created_at=row.created_at,
            version=row.version,
        )
