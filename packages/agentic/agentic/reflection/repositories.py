"""SQLAlchemy and Session-based repositories for reflection & learning (M6 Build Phase E)."""
from __future__ import annotations

import datetime
from typing import Any
from sqlalchemy import JSON, DateTime, Float, String, select
from sqlalchemy.orm import Mapped, mapped_column

from brain.db import BrainBase
from intelligence.repositories._session import SessionMixin


class ReflectionReportRecord(BrainBase):
    """SQLAlchemy record for ReflectionReport."""
    __tablename__ = "agentic_reflection_reports"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    execution_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )


class ProviderScoreRecord(BrainBase):
    """SQLAlchemy record for ProviderScore."""
    __tablename__ = "agentic_provider_scores"
    provider_name: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, primary_key=True)
    success_rate: Mapped[float] = mapped_column(Float, default=1.0)
    avg_latency: Mapped[float] = mapped_column(Float, default=0.0)
    cost_factor: Mapped[float] = mapped_column(Float, default=1.0)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc),
    )


class ToolScoreRecord(BrainBase):
    """SQLAlchemy record for ToolScore."""
    __tablename__ = "agentic_tool_scores"
    tool_name: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, primary_key=True)
    success_rate: Mapped[float] = mapped_column(Float, default=1.0)
    avg_latency: Mapped[float] = mapped_column(Float, default=0.0)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc),
    )


class ConfidenceCalibrationRecord(BrainBase):
    """SQLAlchemy record for Confidence Calibration."""
    __tablename__ = "agentic_confidence_calibrations"
    category: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, primary_key=True)
    predicted_avg: Mapped[float] = mapped_column(Float, default=1.0)
    actual_avg: Mapped[float] = mapped_column(Float, default=1.0)
    calibration_factor: Mapped[float] = mapped_column(Float, default=1.0)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )


class ReflectionRepository(SessionMixin):
    """Saves and retrieves ReflectionReport records."""
    
    def save(self, tenant_id: str, report_id: str, execution_id: str, payload: dict[str, Any]) -> None:
        with self._session() as session:
            record = session.get(ReflectionReportRecord, report_id)
            if not record:
                record = ReflectionReportRecord(
                    id=report_id,
                    execution_id=execution_id,
                    tenant_id=tenant_id,
                    payload=payload,
                )
                session.add(record)
            else:
                record.payload = payload
            session.commit()
            
    def get_by_execution(self, tenant_id: str, execution_id: str) -> dict[str, Any] | None:
        with self._session() as session:
            stmt = select(ReflectionReportRecord).where(
                ReflectionReportRecord.tenant_id == tenant_id,
                ReflectionReportRecord.execution_id == execution_id,
            )
            record = session.execute(stmt).scalar_one_or_none()
            return record.payload if record else None


class ProviderScoreRepository(SessionMixin):
    """Manages provider scoring stats."""
    
    def save_score(self, tenant_id: str, provider_name: str, success_rate: float, avg_latency: float, payload: dict[str, Any]) -> None:
        with self._session() as session:
            record = session.get(ProviderScoreRecord, (provider_name, tenant_id))
            if not record:
                record = ProviderScoreRecord(
                    provider_name=provider_name,
                    tenant_id=tenant_id,
                    success_rate=success_rate,
                    avg_latency=avg_latency,
                    payload=payload,
                )
                session.add(record)
            else:
                record.success_rate = success_rate
                record.avg_latency = avg_latency
                record.payload = payload
            session.commit()
            
    def get_scores(self, tenant_id: str) -> list[dict[str, Any]]:
        with self._session() as session:
            stmt = select(ProviderScoreRecord).where(ProviderScoreRecord.tenant_id == tenant_id)
            records = session.execute(stmt).scalars().all()
            return [r.payload for r in records]

    def get_by_provider(self, tenant_id: str, provider_name: str) -> dict[str, Any] | None:
        with self._session() as session:
            record = session.get(ProviderScoreRecord, (provider_name, tenant_id))
            return record.payload if record else None


class ToolScoreRepository(SessionMixin):
    """Manages tool scoring stats."""
    
    def save_score(self, tenant_id: str, tool_name: str, success_rate: float, avg_latency: float, payload: dict[str, Any]) -> None:
        with self._session() as session:
            record = session.get(ToolScoreRecord, (tool_name, tenant_id))
            if not record:
                record = ToolScoreRecord(
                    tool_name=tool_name,
                    tenant_id=tenant_id,
                    success_rate=success_rate,
                    avg_latency=avg_latency,
                    payload=payload,
                )
                session.add(record)
            else:
                record.success_rate = success_rate
                record.avg_latency = avg_latency
                record.payload = payload
            session.commit()
            
    def get_scores(self, tenant_id: str) -> list[dict[str, Any]]:
        with self._session() as session:
            stmt = select(ToolScoreRecord).where(ToolScoreRecord.tenant_id == tenant_id)
            records = session.execute(stmt).scalars().all()
            return [r.payload for r in records]

    def get_by_tool(self, tenant_id: str, tool_name: str) -> dict[str, Any] | None:
        with self._session() as session:
            record = session.get(ToolScoreRecord, (tool_name, tenant_id))
            return record.payload if record else None


class ConfidenceCalibrationRepository(SessionMixin):
    """Manages predicted-vs-actual calibration metrics."""
    
    def save_calibration(self, tenant_id: str, category: str, predicted_avg: float, actual_avg: float, calibration_factor: float) -> None:
        with self._session() as session:
            record = session.get(ConfidenceCalibrationRecord, (category, tenant_id))
            if not record:
                record = ConfidenceCalibrationRecord(
                    category=category,
                    tenant_id=tenant_id,
                    predicted_avg=predicted_avg,
                    actual_avg=actual_avg,
                    calibration_factor=calibration_factor,
                )
                session.add(record)
            else:
                record.predicted_avg = predicted_avg
                record.actual_avg = actual_avg
                record.calibration_factor = calibration_factor
            session.commit()
            
    def get_calibration(self, tenant_id: str, category: str) -> dict[str, Any] | None:
        with self._session() as session:
            record = session.get(ConfidenceCalibrationRecord, (category, tenant_id))
            if not record:
                return None
            return {
                "category": record.category,
                "predicted_avg": record.predicted_avg,
                "actual_avg": record.actual_avg,
                "calibration_factor": record.calibration_factor,
            }
