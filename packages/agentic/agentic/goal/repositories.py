"""Goal Repository."""
from __future__ import annotations

import datetime
from typing import Protocol
from sqlalchemy import JSON, DateTime, Index, String, select
from sqlalchemy.orm import Mapped, mapped_column
from brain.db import BrainBase
from intelligence.repositories._session import SessionMixin
from agentic.goal.models import Goal


class GoalRecord(BrainBase):
    """SQLAlchemy record for storing Goal models."""
    
    __tablename__ = "agentic_goals"
    
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )


class GoalRepository(Protocol):
    """Storage protocol for Goals."""
    
    def save(self, goal: Goal) -> None:
        """Save a Goal to the store."""
        ...
        
    def get(self, tenant_id: str, goal_id: str) -> Goal | None:
        """Retrieve a Goal by its ID."""
        ...


class SqlAlchemyGoalRepository(SessionMixin):
    """SQLAlchemy implementation of GoalRepository."""
    
    def save(self, goal: Goal) -> None:
        with self._session() as session:
            record = session.get(GoalRecord, goal.id)
            if not record:
                record = GoalRecord(
                    id=goal.id,
                    tenant_id=goal.context.tenant_id,
                    payload=goal.model_dump(mode="json"),
                )
                session.add(record)
            else:
                record.payload = goal.model_dump(mode="json")
            session.commit()
            
    def get(self, tenant_id: str, goal_id: str) -> Goal | None:
        with self._session() as session:
            record = session.get(GoalRecord, goal_id)
            if not record or record.tenant_id != tenant_id:
                return None
            return Goal.model_validate(record.payload)


class InMemoryGoalRepository(GoalRepository):
    """In-memory implementation of GoalRepository for testing."""
    
    def __init__(self) -> None:
        self._store: dict[str, Goal] = {}
        
    def save(self, goal: Goal) -> None:
        self._store[goal.id] = goal
        
    def get(self, tenant_id: str, goal_id: str) -> Goal | None:
        goal = self._store.get(goal_id)
        if goal and goal.context.tenant_id == tenant_id:
            return goal
        return None
