"""AIInvocation audit-record persistence (§5.3).

Append-only: every AI call produces one immutable audit row, retrievable per
page for the future Reviewer agent and for human debugging today. The raw
pre-validation response is retained.
"""

from __future__ import annotations

from sqlalchemy import select

from intelligence.models.ai_invocation import AIInvocation
from intelligence.repositories._session import SessionMixin
from intelligence.repositories.models_orm import AIInvocationRow

__all__ = ["AIInvocationRepository"]


class AIInvocationRepository(SessionMixin):
    def save(self, tenant_id: str, invocation: AIInvocation) -> AIInvocation:
        tenant = self._resolve_tenant(tenant_id)
        stored = invocation.model_copy(update={"tenant_id": tenant})
        with self._session() as session:
            session.add(
                AIInvocationRow(
                    id=stored.id,
                    tenant_id=tenant,
                    page_id=stored.page_id,
                    capability=stored.capability,
                    prompt_version=stored.prompt_version,
                    provider=stored.provider,
                    model=stored.model,
                    cost_estimate=stored.cost_estimate,
                    confidence=stored.confidence,
                    raw_response=stored.raw_response,
                    validation_result=stored.validation_result.value,
                    payload=stored.model_dump(mode="json"),
                    created_at=stored.created_at,
                )
            )
        return stored

    def list_for_page(self, tenant_id: str, page_id: str) -> list[AIInvocation]:
        """Return the page's audit records, newest first."""
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            rows = (
                session.execute(
                    select(AIInvocationRow)
                    .where(
                        AIInvocationRow.tenant_id == tenant,
                        AIInvocationRow.page_id == page_id,
                    )
                    .order_by(AIInvocationRow.created_at.desc(), AIInvocationRow.id.desc())
                )
                .scalars()
                .all()
            )
            return [AIInvocation.model_validate(r.payload) for r in rows]
