"""Core_Package domain events — the typed records emitted when a SuggestedFix
transitions through the governance state machine (Req 12.1, 15.1).

The Governance_Layer is the only path for a ``SuggestedFix`` status transition
(Req 8.2). Each successful transition corresponds to exactly one Audit_Trail
entry (Req 9.5) and is described here by an immutable, typed domain event:

* :class:`FixApproved` — a fix moved to ``approved`` (Req 8.3-8.5).
* :class:`FixApplied` — an Auto_Applicable_Fix's write succeeded and the fix
  moved to ``applied`` (Req 8.5). Carries the freshly-read ``before_value`` that
  was persisted to the Audit_Trail immediately before the write (Req 8.4).
* :class:`FixRolledBack` — an applied fix was reverted to its ``before_value``
  and moved to ``rolled_back`` (Req 9.2). Carries the ``before_value`` written
  back to the live site.

Every event carries the fix id, the acting ``actor``, the ``rationale``, the
``tenant_id``, and a UTC ``timestamp``; events tied to a live write also carry
the ``before_value`` (Req 9.3, 9.4). All fields are typed and the records are
frozen, so an emitted event is an immutable fact about a transition that already
happened.

Per Requirement 15 this module imports nothing internal to the orchestrator
beyond :mod:`core.utils` (for the UTC clock used as the default timestamp).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from core.utils import utc_now

__all__ = [
    "FixApproved",
    "FixApplied",
    "FixRolledBack",
]


class _FixEvent(BaseModel):
    """Common, immutable fields shared by every fix domain event.

    Records the fix that transitioned (``fix_id``), the tenant it belongs to
    (``tenant_id``), the human ``actor`` who decided it, their non-empty
    ``rationale``, and the UTC ``timestamp`` at which the event occurred
    (Req 9.3, 9.4).
    """

    model_config = ConfigDict(frozen=True)

    fix_id: str
    tenant_id: str
    actor: str = Field(min_length=1)  # non-empty; human in M0
    rationale: str = Field(min_length=1)  # non-empty
    timestamp: datetime = Field(default_factory=utc_now)  # UTC


class FixApproved(_FixEvent):
    """Emitted when a SuggestedFix is approved (Req 8.3-8.5).

    Approval alone performs no live write, so no before-value is carried; the
    write (and its before-value) is captured by :class:`FixApplied` for
    Auto_Applicable_Fixes.
    """


class FixApplied(_FixEvent):
    """Emitted when an approved Auto_Applicable_Fix's write succeeds (Req 8.5).

    ``before_value`` is the live value read immediately before the write and
    persisted to the Audit_Trail, enabling a later rollback (Req 8.4, 9.2).
    """

    before_value: str | None = None  # freshly-read live value prior to the write


class FixRolledBack(_FixEvent):
    """Emitted when an applied fix is rolled back to its prior value (Req 9.2).

    ``before_value`` is the audited value written back through the
    Publishing_Adapter to restore the live site.
    """

    before_value: str | None = None  # value restored on the live site
