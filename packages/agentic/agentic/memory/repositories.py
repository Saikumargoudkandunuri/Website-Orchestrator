"""Repositories for persistence of cognitive memory elements (M6 Build Phase C)."""
from __future__ import annotations

import datetime
from sqlalchemy import JSON, DateTime, Float, Index, String, select
from sqlalchemy.orm import Mapped, mapped_column

from brain.db import BrainBase
from intelligence.repositories._session import SessionMixin
from agentic.memory.models import (
    ExperienceEpisode,
    GoalMemoryRecord,
    MemoryIndex,
    ReflectionLesson,
    SemanticFact,
    WorkflowTemplate,
)


class EpisodeRecord(BrainBase):
    """SQLAlchemy record for ExperienceEpisode."""
    __tablename__ = "agentic_episodes"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )


class SemanticFactRecord(BrainBase):
    """SQLAlchemy record for SemanticFact."""
    __tablename__ = "agentic_semantic_facts"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    key: Mapped[str] = mapped_column(String, nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )


class WorkflowTemplateRecord(BrainBase):
    """SQLAlchemy record for WorkflowTemplate."""
    __tablename__ = "agentic_workflow_templates"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )


class ReflectionLessonRecord(BrainBase):
    """SQLAlchemy record for ReflectionLesson."""
    __tablename__ = "agentic_reflection_lessons"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )


class GoalMemoryRecordRow(BrainBase):
    """SQLAlchemy record for GoalMemoryRecord."""
    __tablename__ = "agentic_goal_memory_records"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )


class MemoryIndexRecord(BrainBase):
    """SQLAlchemy record for MemoryIndex."""
    __tablename__ = "agentic_memory_indices"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )


class EpisodicMemoryRepository(SessionMixin):
    """Persistence for ExperienceEpisode models."""
    
    def save(self, episode: ExperienceEpisode) -> None:
        with self._session() as session:
            record = session.get(EpisodeRecord, episode.id)
            if not record:
                record = EpisodeRecord(
                    id=episode.id,
                    tenant_id=episode.tenant_id,
                    site_id=episode.site_id,
                    payload=episode.model_dump(mode="json"),
                )
                session.add(record)
            else:
                record.payload = episode.model_dump(mode="json")
            session.commit()
            
    def get_all(self, tenant_id: str) -> list[ExperienceEpisode]:
        with self._session() as session:
            stmt = select(EpisodeRecord).where(EpisodeRecord.tenant_id == tenant_id)
            records = session.execute(stmt).scalars().all()
            return [ExperienceEpisode.model_validate(r.payload) for r in records]


class SemanticMemoryRepository(SessionMixin):
    """Persistence for SemanticFact models."""
    
    def save(self, fact: SemanticFact) -> None:
        with self._session() as session:
            # Look up by key to overwrite/update
            stmt = select(SemanticFactRecord).where(
                SemanticFactRecord.tenant_id == fact.tenant_id,
                SemanticFactRecord.key == fact.key,
            )
            record = session.execute(stmt).scalar_one_or_none()
            if not record:
                record = SemanticFactRecord(
                    id=fact.id,
                    tenant_id=fact.tenant_id,
                    key=fact.key,
                    payload=fact.model_dump(mode="json"),
                )
                session.add(record)
            else:
                record.payload = fact.model_dump(mode="json")
            session.commit()
            
    def get(self, tenant_id: str, key: str) -> SemanticFact | None:
        with self._session() as session:
            stmt = select(SemanticFactRecord).where(
                SemanticFactRecord.tenant_id == tenant_id,
                SemanticFactRecord.key == key,
            )
            record = session.execute(stmt).scalar_one_or_none()
            if not record:
                return None
            return SemanticFact.model_validate(record.payload)


class ProceduralMemoryRepository(SessionMixin):
    """Persistence for WorkflowTemplate models."""
    
    def save(self, template: WorkflowTemplate) -> None:
        with self._session() as session:
            stmt = select(WorkflowTemplateRecord).where(
                WorkflowTemplateRecord.tenant_id == template.tenant_id,
                WorkflowTemplateRecord.name == template.name,
            )
            record = session.execute(stmt).scalar_one_or_none()
            if not record:
                record = WorkflowTemplateRecord(
                    id=template.id,
                    tenant_id=template.tenant_id,
                    name=template.name,
                    payload=template.model_dump(mode="json"),
                )
                session.add(record)
            else:
                record.payload = template.model_dump(mode="json")
            session.commit()
            
    def get_by_name(self, tenant_id: str, name: str) -> WorkflowTemplate | None:
        with self._session() as session:
            stmt = select(WorkflowTemplateRecord).where(
                WorkflowTemplateRecord.tenant_id == tenant_id,
                WorkflowTemplateRecord.name == name,
            )
            record = session.execute(stmt).scalar_one_or_none()
            if not record:
                return None
            return WorkflowTemplate.model_validate(record.payload)


class ReflectionMemoryRepository(SessionMixin):
    """Persistence for ReflectionLesson models."""
    
    def save(self, lesson: ReflectionLesson) -> None:
        with self._session() as session:
            record = session.get(ReflectionLessonRecord, lesson.id)
            if not record:
                record = ReflectionLessonRecord(
                    id=lesson.id,
                    tenant_id=lesson.tenant_id,
                    payload=lesson.model_dump(mode="json"),
                )
                session.add(record)
            else:
                record.payload = lesson.model_dump(mode="json")
            session.commit()
            
    def get_all(self, tenant_id: str) -> list[ReflectionLesson]:
        with self._session() as session:
            stmt = select(ReflectionLessonRecord).where(
                ReflectionLessonRecord.tenant_id == tenant_id
            )
            records = session.execute(stmt).scalars().all()
            return [ReflectionLesson.model_validate(r.payload) for r in records]


class GoalMemoryRepository(SessionMixin):
    """Persistence for GoalMemoryRecord models."""
    
    def save(self, record_val: GoalMemoryRecord) -> None:
        with self._session() as session:
            record = session.get(GoalMemoryRecordRow, record_val.id)
            if not record:
                record = GoalMemoryRecordRow(
                    id=record_val.id,
                    tenant_id=record_val.tenant_id,
                    payload=record_val.model_dump(mode="json"),
                )
                session.add(record)
            else:
                record.payload = record_val.model_dump(mode="json")
            session.commit()
            
    def get(self, tenant_id: str, goal_id: str) -> GoalMemoryRecord | None:
        with self._session() as session:
            stmt = select(GoalMemoryRecordRow).where(
                GoalMemoryRecordRow.tenant_id == tenant_id
            )
            records = session.execute(stmt).scalars().all()
            for r in records:
                gmr = GoalMemoryRecord.model_validate(r.payload)
                if gmr.goal.id == goal_id:
                    return gmr
            return None

    def get_all(self, tenant_id: str) -> list[GoalMemoryRecord]:
        with self._session() as session:
            stmt = select(GoalMemoryRecordRow).where(
                GoalMemoryRecordRow.tenant_id == tenant_id
            )
            records = session.execute(stmt).scalars().all()
            return [GoalMemoryRecord.model_validate(r.payload) for r in records]


class MemoryIndexRepository(SessionMixin):
    """Persistence for MemoryIndex models."""
    
    def save(self, index: MemoryIndex) -> None:
        with self._session() as session:
            record = session.get(MemoryIndexRecord, index.id)
            if not record:
                record = MemoryIndexRecord(
                    id=index.id,
                    tenant_id=index.tenant_id,
                    entity_type=index.entity_type,
                    entity_id=index.entity_id,
                    payload=index.model_dump(mode="json"),
                )
                session.add(record)
            else:
                record.payload = index.model_dump(mode="json")
            session.commit()
            
    def find_by_tags(self, tenant_id: str, tags: list[str]) -> list[MemoryIndex]:
        with self._session() as session:
            stmt = select(MemoryIndexRecord).where(
                MemoryIndexRecord.tenant_id == tenant_id
            )
            records = session.execute(stmt).scalars().all()
            results = []
            for r in records:
                idx = MemoryIndex.model_validate(r.payload)
                if any(t in idx.tags for t in tags):
                    results.append(idx)
            return results
