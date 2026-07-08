"""Base for Milestone-2 KnowledgeObject-driven fix generators (§8.2).

These package a KnowledgeObject's already-*proposed* field values into Milestone
1 :class:`~core.types.SuggestedFix` records so they flow through the existing
Governance/Publisher pipeline **unchanged**. They keep AI generation (already
done by the analyzers) and fix-packaging as separate concerns — the generators
only read proposed fields, never re-derive them.

Publishing scope note: Milestone 1's Publisher writes only page ``content`` and
media ``alt_text``. Meta description, title, slug, and schema are not writable by
that Publisher, so these fixes are produced **report-only**
(``auto_applicable=0``) — they still flow through governance (approve/reject)
unchanged; wiring them to a live write is a future Publisher extension. Alt-text
proposals continue to flow through Milestone 1's existing ``update_alt_text``
generator/pipeline.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from core.types import FixStatus, SuggestedFix
from intelligence.models.knowledge_object import KnowledgeObject

__all__ = ["KnowledgeObjectFixGenerator"]


class KnowledgeObjectFixGenerator(ABC):
    """Turns a KnowledgeObject's proposed value into at most one SuggestedFix."""

    #: A machine-readable kind recorded in the fix reason (e.g. "update_meta_description").
    kind: str = ""

    @abstractmethod
    def proposed_value(self, ko: KnowledgeObject) -> str | None:
        """Return the proposed value for this fix, or ``None`` when absent."""
        ...

    def reasoning(self, ko: KnowledgeObject) -> str | None:  # pragma: no cover - default
        return None

    def generate(
        self, ko: KnowledgeObject, *, issue_id: str, tenant_id: str | None = None
    ) -> SuggestedFix | None:
        """Package the proposal as a report-only :class:`SuggestedFix`, or ``None``.

        Never writes to the database (pure transform, like Milestone 1's
        FixGenerator). The caller persists via the existing Fix repository.
        """
        value = self.proposed_value(ko)
        if not value or not value.strip():
            return None
        reason = self.reasoning(ko) or ""
        return SuggestedFix(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id or ko.tenant_id,
            issue_id=issue_id,
            fix_type=None,  # not one of M1's writable FixTypes; report-only
            auto_applicable=0,
            target_ref=None,
            proposed_value=value,
            reason=f"{self.kind}: {reason}".strip().rstrip(":").strip()
            or self.kind,
            status=FixStatus.PENDING,
        )
