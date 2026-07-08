"""Collaboration Repositories for System 5."""

from __future__ import annotations

from typing import Any
from sqlalchemy import select, delete

from intelligence.repositories._session import SessionMixin
from saas.collaboration.models import (
    ThreadRow,
    CommentRow,
    NotificationRow,
    DecisionLogRow,
    Thread,
    Comment,
    Notification,
    DecisionLog,
)

__all__ = ["CollaborationRepository"]


class CollaborationRepository(SessionMixin):
    """SaaS Collaboration Repository managing discussions, notifications, and signed decisions."""

    def save_thread(self, thread: Thread) -> None:
        tenant = self._resolve_tenant(thread.tenant_id)
        with self._session() as session:
            existing = session.get(ThreadRow, thread.id)
            if not existing:
                session.add(ThreadRow(
                    id=thread.id,
                    tenant_id=tenant,
                    target_node_id=thread.target_node_id,
                    title=thread.title,
                    created_at=thread.created_at,
                ))
            session.commit()

    def list_threads(self, tenant_id: str, target_node_id: str) -> list[Thread]:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            rows = session.execute(
                select(ThreadRow).where(
                    ThreadRow.tenant_id == tenant,
                    ThreadRow.target_node_id == target_node_id,
                )
            ).scalars().all()
            return [
                Thread(
                    id=r.id,
                    tenant_id=r.tenant_id,
                    target_node_id=r.target_node_id,
                    title=r.title,
                    created_at=r.created_at,
                )
                for r in rows
            ]

    def save_comment(self, comment: Comment) -> None:
        tenant = self._resolve_tenant(comment.tenant_id)
        with self._session() as session:
            session.add(CommentRow(
                id=comment.id,
                tenant_id=tenant,
                thread_id=comment.thread_id,
                author=comment.author,
                content=comment.content,
                created_at=comment.created_at,
            ))
            session.commit()

    def list_comments(self, tenant_id: str, thread_id: str) -> list[Comment]:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            rows = session.execute(
                select(CommentRow).where(
                    CommentRow.tenant_id == tenant,
                    CommentRow.thread_id == thread_id,
                ).order_by(CommentRow.created_at.asc())
            ).scalars().all()
            return [
                Comment(
                    id=r.id,
                    tenant_id=r.tenant_id,
                    thread_id=r.thread_id,
                    author=r.author,
                    content=r.content,
                    created_at=r.created_at,
                )
                for r in rows
            ]

    def save_notification(self, notif: Notification) -> None:
        tenant = self._resolve_tenant(notif.tenant_id)
        with self._session() as session:
            session.add(NotificationRow(
                id=notif.id,
                tenant_id=tenant,
                user_id=notif.user_id,
                message=notif.message,
                is_read=notif.is_read,
                created_at=notif.created_at,
            ))
            session.commit()

    def list_notifications(self, tenant_id: str, user_id: str) -> list[Notification]:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            rows = session.execute(
                select(NotificationRow).where(
                    NotificationRow.tenant_id == tenant,
                    NotificationRow.user_id == user_id,
                )
            ).scalars().all()
            return [
                Notification(
                    id=r.id,
                    tenant_id=r.tenant_id,
                    user_id=r.user_id,
                    message=r.message,
                    is_read=r.is_read,
                    created_at=r.created_at,
                )
                for r in rows
            ]

    def save_decision(self, dec: DecisionLog) -> None:
        tenant = self._resolve_tenant(dec.tenant_id)
        with self._session() as session:
            session.add(DecisionLogRow(
                id=dec.id,
                tenant_id=tenant,
                goal_id=dec.goal_id,
                actor=dec.actor,
                rationale=dec.rationale,
                votes_json=dec.votes_json,
                signature=dec.signature,
                created_at=dec.created_at,
            ))
            session.commit()

    def list_decisions(self, tenant_id: str) -> list[DecisionLog]:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            rows = session.execute(
                select(DecisionLogRow).where(
                    DecisionLogRow.tenant_id == tenant
                ).order_by(DecisionLogRow.created_at.desc())
            ).scalars().all()
            return [
                DecisionLog(
                    id=r.id,
                    tenant_id=r.tenant_id,
                    goal_id=r.goal_id,
                    actor=r.actor,
                    rationale=r.rationale,
                    votes_json=r.votes_json,
                    signature=r.signature,
                    created_at=r.created_at,
                )
                for r in rows
            ]
