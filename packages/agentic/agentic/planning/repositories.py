"""Repositories for the planning subsystem (M6 Build Phase B)."""
from __future__ import annotations

import datetime
from typing import Iterator

from sqlalchemy import JSON, Boolean, DateTime, Float, Index, Integer, String, select
from sqlalchemy.orm import Mapped, mapped_column

from brain.db import BrainBase
from intelligence.repositories._session import SessionMixin
from agentic.planning.models import ExecutionGraph, Plan
from agentic.planning.simulation import SimulationOutcome


class PlanRecord(BrainBase):
    """SQLAlchemy storage record for Plan."""
    
    __tablename__ = "agentic_plans"
    
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    goal_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )


class ExecutionGraphRecord(BrainBase):
    """SQLAlchemy storage record for ExecutionGraph."""
    
    __tablename__ = "agentic_execution_graphs"
    
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    plan_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )


class SimulationRecord(BrainBase):
    """SQLAlchemy storage record for SimulationOutcome."""
    
    __tablename__ = "agentic_simulations"
    
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    plan_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )


class PlanRepository(SessionMixin):
    """Persistence repository for Plans."""
    
    def save(self, plan: Plan) -> None:
        """Save a new Plan snapshot or update active status."""
        with self._session() as session:
            record = session.get(PlanRecord, plan.id)
            if not record:
                record = PlanRecord(
                    id=plan.id,
                    tenant_id=plan.tenant_id,
                    site_id=plan.site_id,
                    goal_id=plan.goal_id,
                    version=plan.version,
                    is_active=plan.is_active,
                    payload=plan.model_dump(mode="json"),
                )
                session.add(record)
            else:
                record.is_active = plan.is_active
                record.payload = plan.model_dump(mode="json")
            session.commit()
            
    def get(self, tenant_id: str, plan_id: str) -> Plan | None:
        """Load a Plan by ID."""
        with self._session() as session:
            record = session.get(PlanRecord, plan_id)
            if not record or record.tenant_id != tenant_id:
                return None
            return Plan.model_validate(record.payload)
            
    def get_latest_for_goal(self, tenant_id: str, goal_id: str) -> Plan | None:
        """Get the latest version of a plan for a goal."""
        with self._session() as session:
            stmt = (
                select(PlanRecord)
                .where(PlanRecord.tenant_id == tenant_id, PlanRecord.goal_id == goal_id)
                .order_by(PlanRecord.version.desc())
                .limit(1)
            )
            record = session.execute(stmt).scalar_one_or_none()
            if not record:
                return None
            return Plan.model_validate(record.payload)


class ExecutionGraphRepository(SessionMixin):
    """Persistence repository for ExecutionGraphs."""
    
    def save(self, plan_id: str, graph: ExecutionGraph, tenant_id: str, site_id: str) -> None:
        """Save an ExecutionGraph linked to a Plan."""
        graph_id = f"graph_{plan_id}"
        with self._session() as session:
            record = session.get(ExecutionGraphRecord, graph_id)
            if not record:
                record = ExecutionGraphRecord(
                    id=graph_id,
                    tenant_id=tenant_id,
                    site_id=site_id,
                    plan_id=plan_id,
                    payload=graph.model_dump(mode="json"),
                )
                session.add(record)
            else:
                record.payload = graph.model_dump(mode="json")
            session.commit()
            
    def get_for_plan(self, tenant_id: str, plan_id: str) -> ExecutionGraph | None:
        """Retrieve an ExecutionGraph by plan ID."""
        graph_id = f"graph_{plan_id}"
        with self._session() as session:
            record = session.get(ExecutionGraphRecord, graph_id)
            if not record or record.tenant_id != tenant_id:
                return None
            return ExecutionGraph.model_validate(record.payload)


class SimulationRepository(SessionMixin):
    """Persistence repository for SimulationOutcomes."""
    
    def save(self, plan_id: str, outcome: SimulationOutcome, tenant_id: str, site_id: str) -> None:
        """Save a SimulationOutcome linked to a Plan."""
        sim_id = f"sim_{plan_id}"
        with self._session() as session:
            record = session.get(SimulationRecord, sim_id)
            if not record:
                record = SimulationRecord(
                    id=sim_id,
                    tenant_id=tenant_id,
                    site_id=site_id,
                    plan_id=plan_id,
                    payload=outcome.model_dump(mode="json"),
                )
                session.add(record)
            else:
                record.payload = outcome.model_dump(mode="json")
            session.commit()
            
    def get_for_plan(self, tenant_id: str, plan_id: str) -> SimulationOutcome | None:
        """Retrieve a SimulationOutcome by plan ID."""
        sim_id = f"sim_{plan_id}"
        with self._session() as session:
            record = session.get(SimulationRecord, sim_id)
            if not record or record.tenant_id != tenant_id:
                return None
            return SimulationOutcome.model_validate(record.payload)
