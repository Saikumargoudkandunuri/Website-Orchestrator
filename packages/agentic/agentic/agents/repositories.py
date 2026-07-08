"""SQLAlchemy and Session repositories for multi-agent missions (M6 Build Phase F)."""
from __future__ import annotations

import datetime
from sqlalchemy import JSON, DateTime, String, select
from sqlalchemy.orm import Mapped, mapped_column

from brain.db import BrainBase
from intelligence.repositories._session import SessionMixin
from agentic.agents.types import JsonObject


class MissionRecord(BrainBase):
    """SQLAlchemy record for agentic missions."""
    __tablename__ = "agentic_missions"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    goal_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    execution_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    state: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )


class AgentRecord(BrainBase):
    """SQLAlchemy record for registered specialist agent metadata."""
    __tablename__ = "agentic_agent_registry"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )


class BlackboardEntryRecord(BrainBase):
    """SQLAlchemy record for append-only shared blackboard items."""
    __tablename__ = "agentic_blackboard"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    mission_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    key: Mapped[str] = mapped_column(String, nullable=False, index=True)
    version: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )


class MessageRecord(BrainBase):
    """SQLAlchemy record for typed inter-agent messages."""
    __tablename__ = "agentic_messages"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    mission_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )


class AgentHistoryRecord(BrainBase):
    """SQLAlchemy record for append-only agent decisions and events."""
    __tablename__ = "agentic_agent_history"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    mission_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )


class MissionMetricsRecord(BrainBase):
    """SQLAlchemy record for append-only mission observability metrics."""
    __tablename__ = "agentic_mission_metrics"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    mission_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )


class MissionRepository(SessionMixin):
    """Manages persisted mission snapshots with tenant scoping."""

    def save_mission(
        self,
        tenant_id: str,
        mission_id: str,
        goal_id: str,
        state: str,
        payload: JsonObject,
        execution_id: str | None = None,
    ) -> None:
        with self._session() as session:
            record = session.get(MissionRecord, mission_id)
            if not record:
                record = MissionRecord(
                    id=mission_id,
                    tenant_id=tenant_id,
                    goal_id=goal_id,
                    execution_id=execution_id,
                    state=state,
                    payload=payload,
                )
                session.add(record)
            elif record.tenant_id == tenant_id:
                record.state = state
                record.execution_id = execution_id or record.execution_id
                record.payload = payload
            session.commit()

    def get_mission(self, tenant_id: str, mission_id: str) -> JsonObject | None:
        with self._session() as session:
            record = session.get(MissionRecord, mission_id)
            if not record or record.tenant_id != tenant_id:
                return None
            return {
                "mission_id": mission_id,
                "goal_id": record.goal_id,
                "execution_id": record.execution_id,
                "state": record.state,
                "payload": record.payload,
            }


class AgentRepository(SessionMixin):
    """Persists tenant-scoped specialist metadata consulted by planners."""

    def save_agent(self, tenant_id: str, agent_id: str, payload: JsonObject) -> None:
        with self._session() as session:
            record_id = f"{tenant_id}:{agent_id}"
            record = session.get(AgentRecord, record_id)
            if not record:
                record = AgentRecord(id=record_id, tenant_id=tenant_id, agent_id=agent_id, payload=payload)
                session.add(record)
            elif record.tenant_id == tenant_id:
                record.payload = payload
            session.commit()

    def list_agents(self, tenant_id: str) -> list[JsonObject]:
        with self._session() as session:
            stmt = select(AgentRecord).where(AgentRecord.tenant_id == tenant_id)
            records = session.execute(stmt).scalars().all()
            return [r.payload for r in records]


class BlackboardRepository(SessionMixin):
    """Manages append-only shared blackboard facts."""

    def post_fact(self, tenant_id: str, mission_id: str, entry_id: str, key: str, version: int, payload: JsonObject) -> None:
        with self._session() as session:
            session.add(
                BlackboardEntryRecord(
                    id=entry_id,
                    mission_id=mission_id,
                    tenant_id=tenant_id,
                    key=key,
                    version=str(version),
                    payload=payload,
                )
            )
            session.commit()

    def get_facts(self, tenant_id: str, mission_id: str) -> list[JsonObject]:
        with self._session() as session:
            stmt = select(BlackboardEntryRecord).where(
                BlackboardEntryRecord.tenant_id == tenant_id,
                BlackboardEntryRecord.mission_id == mission_id,
            )
            records = session.execute(stmt).scalars().all()
            return [r.payload for r in records]


class MessageRepository(SessionMixin):
    """Manages append-only inter-agent message histories."""

    def save_message(self, tenant_id: str, mission_id: str, message_id: str, payload: JsonObject) -> None:
        with self._session() as session:
            session.add(MessageRecord(id=message_id, mission_id=mission_id, tenant_id=tenant_id, payload=payload))
            session.commit()

    def get_messages(self, tenant_id: str, mission_id: str) -> list[JsonObject]:
        with self._session() as session:
            stmt = select(MessageRecord).where(MessageRecord.tenant_id == tenant_id, MessageRecord.mission_id == mission_id)
            records = session.execute(stmt).scalars().all()
            return [r.payload for r in records]


class AgentHistoryRepository(SessionMixin):
    """Stores explainable agent decisions and coordination events."""

    def save_event(self, tenant_id: str, mission_id: str, event_id: str, agent_id: str, payload: JsonObject) -> None:
        with self._session() as session:
            session.add(
                AgentHistoryRecord(
                    id=event_id,
                    mission_id=mission_id,
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                    payload=payload,
                )
            )
            session.commit()

    def list_events(self, tenant_id: str, mission_id: str) -> list[JsonObject]:
        with self._session() as session:
            stmt = select(AgentHistoryRecord).where(
                AgentHistoryRecord.tenant_id == tenant_id,
                AgentHistoryRecord.mission_id == mission_id,
            )
            records = session.execute(stmt).scalars().all()
            return [r.payload for r in records]


class MissionMetricsRepository(SessionMixin):
    """Stores mission-level metrics emitted through the agentic layer."""

    def save_metric(self, tenant_id: str, mission_id: str, metric_id: str, payload: JsonObject) -> None:
        with self._session() as session:
            session.add(MissionMetricsRecord(id=metric_id, mission_id=mission_id, tenant_id=tenant_id, payload=payload))
            session.commit()

    def get_metrics(self, tenant_id: str, mission_id: str) -> list[JsonObject]:
        with self._session() as session:
            stmt = select(MissionMetricsRecord).where(
                MissionMetricsRecord.tenant_id == tenant_id,
                MissionMetricsRecord.mission_id == mission_id,
            )
            records = session.execute(stmt).scalars().all()
            return [r.payload for r in records]
