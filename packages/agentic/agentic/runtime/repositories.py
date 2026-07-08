"""SQLAlchemy and Session-based repositories for runtime state (M6 Build Phase D)."""
from __future__ import annotations

import datetime
from typing import Any
from sqlalchemy import JSON, DateTime, String, select
from sqlalchemy.orm import Mapped, mapped_column

from brain.db import BrainBase
from intelligence.repositories._session import SessionMixin
from agentic.runtime.checkpoint_manager import ExecutionCheckpoint


class CheckpointRecord(BrainBase):
    """SQLAlchemy record for ExecutionCheckpoint."""
    __tablename__ = "agentic_checkpoints"
    id: Mapped[str] = mapped_column(String, primary_key=True)  # maps to execution_id
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )


class ExecutionRecordRow(BrainBase):
    """SQLAlchemy record for Execution state."""
    __tablename__ = "agentic_executions"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    state: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )


class ExecutionMetricsRecord(BrainBase):
    """SQLAlchemy record for Execution metrics."""
    __tablename__ = "agentic_execution_metrics"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    execution_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )


class CheckpointRepository(SessionMixin):
    """Saves and restores ExecutionCheckpoints."""
    
    def save(self, checkpoint: ExecutionCheckpoint) -> None:
        with self._session() as session:
            record = session.get(CheckpointRecord, checkpoint.execution_id)
            if not record:
                record = CheckpointRecord(
                    id=checkpoint.execution_id,
                    tenant_id=checkpoint.tenant_id,
                    payload=checkpoint.model_dump(mode="json"),
                )
                session.add(record)
            else:
                record.payload = checkpoint.model_dump(mode="json")
            session.commit()
            
    def load(self, tenant_id: str, execution_id: str) -> ExecutionCheckpoint | None:
        with self._session() as session:
            record = session.get(CheckpointRecord, execution_id)
            if not record or record.tenant_id != tenant_id:
                return None
            return ExecutionCheckpoint.model_validate(record.payload)


class ExecutionRepository(SessionMixin):
    """Manages active/historical agent executions."""
    
    def save_execution(self, tenant_id: str, execution_id: str, state: str, plan_data: dict[str, Any]) -> None:
        with self._session() as session:
            record = session.get(ExecutionRecordRow, execution_id)
            if not record:
                record = ExecutionRecordRow(
                    id=execution_id,
                    tenant_id=tenant_id,
                    state=state,
                    payload=plan_data,
                )
                session.add(record)
            else:
                record.state = state
                record.payload = plan_data
            session.commit()
            
    def get_execution(self, tenant_id: str, execution_id: str) -> dict[str, Any] | None:
        with self._session() as session:
            record = session.get(ExecutionRecordRow, execution_id)
            if not record or record.tenant_id != tenant_id:
                return None
            # Return dict with state and payload combined
            return {"execution_id": execution_id, "state": record.state, "plan": record.payload}


class ExecutionMetricsRepository(SessionMixin):
    """Telemetry log repository."""
    
    def save_metrics(self, tenant_id: str, execution_id: str, metric_id: str, data: dict[str, Any]) -> None:
        with self._session() as session:
            record = ExecutionMetricsRecord(
                id=metric_id,
                execution_id=execution_id,
                tenant_id=tenant_id,
                payload=data,
            )
            session.add(record)
            session.commit()
            
    def get_metrics(self, tenant_id: str, execution_id: str) -> list[dict[str, Any]]:
        with self._session() as session:
            stmt = select(ExecutionMetricsRecord).where(
                ExecutionMetricsRecord.tenant_id == tenant_id,
                ExecutionMetricsRecord.execution_id == execution_id,
            )
            records = session.execute(stmt).scalars().all()
            return [r.payload for r in records]
