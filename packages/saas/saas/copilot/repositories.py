"""Copilot Repositories for System 6."""

from __future__ import annotations

from typing import Any
from sqlalchemy import select, delete

from intelligence.repositories._session import SessionMixin
from saas.copilot.models import (
    ConversationSessionRow,
    PromptTemplateRow,
    AIExplanationRow,
    ConversationSession,
    PromptTemplate,
    AIExplanation,
)

__all__ = ["CopilotRepository"]


class CopilotRepository(SessionMixin):
    """SaaS Copilot Repository managing chat logs, prompt templates, and reasoning graphs."""

    def save_session(self, session_data: ConversationSession) -> None:
        tenant = self._resolve_tenant(session_data.tenant_id)
        with self._session() as session:
            existing = session.get(ConversationSessionRow, session_data.id)
            if existing:
                existing.messages_json = session_data.messages_json
            else:
                session.add(ConversationSessionRow(
                    id=session_data.id,
                    tenant_id=tenant,
                    user_id=session_data.user_id,
                    messages_json=session_data.messages_json,
                    created_at=session_data.created_at,
                ))
            session.commit()

    def get_session(self, tenant_id: str, session_id: str) -> ConversationSession | None:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            row = session.get(ConversationSessionRow, session_id)
            if row and row.tenant_id == tenant:
                return ConversationSession(
                    id=row.id,
                    tenant_id=row.tenant_id,
                    user_id=row.user_id,
                    messages_json=row.messages_json,
                    created_at=row.created_at,
                )
            return None

    def save_template(self, template: PromptTemplate) -> None:
        tenant = self._resolve_tenant(template.tenant_id)
        with self._session() as session:
            existing = session.get(PromptTemplateRow, template.id)
            if existing:
                existing.template_text = template.template_text
                existing.description = template.description
            else:
                session.add(PromptTemplateRow(
                    id=template.id,
                    tenant_id=tenant,
                    name=template.name,
                    template_text=template.template_text,
                    description=template.description,
                ))
            session.commit()

    def list_templates(self, tenant_id: str) -> list[PromptTemplate]:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            rows = session.execute(
                select(PromptTemplateRow).where(PromptTemplateRow.tenant_id == tenant)
            ).scalars().all()
            return [
                PromptTemplate(
                    id=r.id,
                    tenant_id=r.tenant_id,
                    name=r.name,
                    template_text=r.template_text,
                    description=r.description,
                )
                for r in rows
            ]

    def save_explanation(self, exp: AIExplanation) -> None:
        tenant = self._resolve_tenant(exp.tenant_id)
        with self._session() as session:
            existing = session.execute(
                select(AIExplanationRow).where(
                    AIExplanationRow.tenant_id == tenant,
                    AIExplanationRow.goal_id == exp.goal_id,
                )
            ).scalar_one_or_none()

            if existing:
                existing.explanation_json = exp.explanation_json
            else:
                session.add(AIExplanationRow(
                    id=exp.id,
                    tenant_id=tenant,
                    goal_id=exp.goal_id,
                    explanation_json=exp.explanation_json,
                ))
            session.commit()

    def get_explanation(self, tenant_id: str, goal_id: str) -> AIExplanation | None:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            row = session.execute(
                select(AIExplanationRow).where(
                    AIExplanationRow.tenant_id == tenant,
                    AIExplanationRow.goal_id == goal_id,
                )
            ).scalar_one_or_none()
            if row:
                return AIExplanation(
                    id=row.id,
                    tenant_id=row.tenant_id,
                    goal_id=row.goal_id,
                    explanation_json=row.explanation_json,
                )
            return None
