"""Property 37 — Already-decided fixes cannot be re-decided.

Feature: website-orchestrator-milestone-0, Property 37: Already-decided fixes
cannot be re-decided.

**Validates: Requirements 8.8**

The Governance_Layer is the sole path for a ``SuggestedFix`` status transition,
and a fix that has already been decided — its status is one of ``approved``,
``applied``, ``rejected``, or ``rolled_back`` — cannot be approved or rejected
again (Req 8.8). Both :meth:`GovernanceService.approve_fix` and
:meth:`GovernanceService.reject_fix` must fail closed on such a fix by raising
:class:`~core.exceptions.FixAlreadyDecidedError` while leaving the fix's status
unchanged, writing no Audit_Trail entry, and making no Publishing_Adapter call.

This property drives that guarantee across the full input space: for any of the
four decided statuses, any fix shape (Report_Only_Fix, auto-applicable alt-text,
auto-applicable page-content — with varied ids and proposed values), any valid
actor/rationale, and either operation (approve or reject), we assert the
exception is raised, the status is left exactly as it was, the Audit_Trail
remains empty, and ``pa.writes == []``.

The in-memory fakes mirror those in ``test_governance_service.py``: they record
every mutating call in a shared ordered ``calls`` log so an accidental status
transition or audit append would be observable, and the Publishing_Adapter is
seeded with the fix's live target so a *broken* guard that proceeded to write
would surface as a non-empty ``pa.writes`` rather than a bare ``KeyError``.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from core.exceptions import FixAlreadyDecidedError
from core.interfaces import WPMedia, WPPage
from core.types import (
    AuditEntry,
    FixStatus,
    FixType,
    SuggestedFix,
    TargetRef,
)

from governance.service import GovernanceService

TENANT = "tenant-a"

#: The four "decided" statuses that can never be decided again (Req 8.8).
_DECIDED_STATUSES = [
    FixStatus.APPROVED,
    FixStatus.APPLIED,
    FixStatus.REJECTED,
    FixStatus.ROLLED_BACK,
]


# --- In-memory fakes (mirror test_governance_service.py) ----------------------


class FakeDigitalTwin:
    """An in-memory :class:`core.interfaces.DigitalTwinPort` spy.

    Records every mutating call in the shared ordered ``calls`` log so an
    accidental status transition or Audit_Trail append is directly observable.
    """

    def __init__(self, calls: list[tuple], fixes: list[SuggestedFix]) -> None:
        self.calls = calls
        self._fixes: dict[str, SuggestedFix] = {f.id: f for f in fixes}
        self.audit_entries: list[AuditEntry] = []

    def list_pending_fixes(self, tenant_id: str) -> list[SuggestedFix]:
        return [
            f
            for f in self._fixes.values()
            if f.tenant_id == tenant_id and f.status is FixStatus.PENDING
        ]

    def get_fix(self, tenant_id: str, fix_id: str) -> SuggestedFix | None:
        fix = self._fixes.get(fix_id)
        if fix is None or fix.tenant_id != tenant_id:
            return None
        return fix

    def update_fix_status(
        self, tenant_id: str, fix_id: str, status: FixStatus
    ) -> SuggestedFix:
        fix = self._fixes[fix_id]
        updated = fix.model_copy(update={"status": status})
        self._fixes[fix_id] = updated
        self.calls.append(("update_fix_status", fix_id, status))
        return updated

    def append_audit_entry(self, tenant_id: str, entry: AuditEntry) -> AuditEntry:
        self.audit_entries.append(entry)
        self.calls.append(("append_audit_entry", entry.fix_id, entry.before_value))
        return entry

    def list_audit_entries(self, tenant_id: str) -> list[AuditEntry]:
        return [e for e in reversed(self.audit_entries) if e.tenant_id == tenant_id]


class FakePublishingAdapter:
    """An in-memory :class:`core.interfaces.PublishingAdapterPort` spy.

    Serves canned live values and records every read/write. ``writes`` stays
    empty unless a write method is actually invoked — the signal a broken guard
    would trip.
    """

    def __init__(
        self,
        calls: list[tuple],
        *,
        media: dict[int, WPMedia] | None = None,
        pages: dict[int, WPPage] | None = None,
    ) -> None:
        self.calls = calls
        self._media = media or {}
        self._pages = pages or {}
        self.writes: list[tuple] = []

    def get_media(self, media_id: int) -> WPMedia:
        self.calls.append(("get_media", media_id))
        return self._media[media_id]

    def get_page(self, page_id: int) -> WPPage:
        self.calls.append(("get_page", page_id))
        return self._pages[page_id]

    def update_media_alt_text(self, media_id: int, alt_text: str) -> WPMedia:
        self.calls.append(("update_media_alt_text", media_id, alt_text))
        self.writes.append(("media", media_id, alt_text))
        updated = WPMedia(id=media_id, alt_text=alt_text)
        self._media[media_id] = updated
        return updated

    def update_page_content(self, page_id: int, content: str) -> WPPage:
        self.calls.append(("update_page_content", page_id, content))
        self.writes.append(("page", page_id, content))
        updated = WPPage(id=page_id, content=content)
        self._pages[page_id] = updated
        return updated


# --- Strategies ---------------------------------------------------------------

# Valid actor/rationale: any string with non-whitespace content, so input
# validation (Req 8.11) passes and execution reaches the already-decided guard.
_valid_text = st.text(min_size=1, max_size=40).filter(lambda s: bool(s.strip()))

_ids = st.integers(min_value=1, max_value=2**31 - 1)
_values = st.text(max_size=60)
_operations = st.sampled_from(["approve", "reject"])


@st.composite
def _decided_scenarios(draw):
    """Build a decided fix plus a Publishing_Adapter seeded with its live target.

    Varies across all three fix shapes (report-only, auto-applicable alt-text,
    auto-applicable page-content), all four decided statuses, arbitrary ids and
    proposed values, and both operations. The PA is pre-seeded with the fix's
    live target so a *broken* guard that proceeded to read/write would produce a
    non-empty ``pa.writes`` (a clean assertion failure) rather than a KeyError.
    """
    status = draw(st.sampled_from(_DECIDED_STATUSES))
    kind = draw(st.sampled_from(["report_only", "alt_text", "page_content"]))
    fix_id = draw(st.text(min_size=1, max_size=12).filter(lambda s: bool(s.strip())))
    operation = draw(_operations)
    actor = draw(_valid_text)
    rationale = draw(_valid_text)

    media: dict[int, WPMedia] = {}
    pages: dict[int, WPPage] = {}

    if kind == "alt_text":
        media_id = draw(_ids)
        fix = SuggestedFix(
            id=fix_id,
            tenant_id=TENANT,
            issue_id="issue-1",
            fix_type=FixType.UPDATE_ALT_TEXT,
            auto_applicable=1,
            target_ref=TargetRef(media_id=media_id),
            proposed_value=draw(_values),
            status=status,
        )
        media[media_id] = WPMedia(id=media_id, alt_text=draw(_values))
    elif kind == "page_content":
        page_id = draw(_ids)
        fix = SuggestedFix(
            id=fix_id,
            tenant_id=TENANT,
            issue_id="issue-2",
            fix_type=FixType.UPDATE_PAGE_CONTENT,
            auto_applicable=1,
            target_ref=TargetRef(page_id=page_id),
            proposed_value=draw(_values),
            status=status,
        )
        pages[page_id] = WPPage(id=page_id, content=draw(_values))
    else:  # report_only
        fix = SuggestedFix(
            id=fix_id,
            tenant_id=TENANT,
            issue_id="issue-3",
            fix_type=FixType.UPDATE_PAGE_CONTENT,
            auto_applicable=0,
            reason=draw(_values),
            status=status,
        )

    return fix, status, operation, actor, rationale, media, pages


# --- Property 37 --------------------------------------------------------------


@pytest.mark.property
@settings(max_examples=200)
@given(scenario=_decided_scenarios())
def test_property_37_already_decided_fixes_cannot_be_redecided(scenario) -> None:
    """A decided fix rejects both approve and reject, unchanged, no side effects.

    For any decided status, any fix shape, any valid actor/rationale, and either
    operation, the decision raises :class:`FixAlreadyDecidedError`, the status is
    left unchanged, the Audit_Trail stays empty, and no Publishing_Adapter write
    occurs (Req 8.8).
    """
    fix, status, operation, actor, rationale, media, pages = scenario

    calls: list[tuple] = []
    twin = FakeDigitalTwin(calls, [fix])
    pa = FakePublishingAdapter(calls, media=media, pages=pages)
    service = GovernanceService(twin, pa)

    decide = service.approve_fix if operation == "approve" else service.reject_fix

    # Both approve and reject must fail closed on an already-decided fix.
    with pytest.raises(FixAlreadyDecidedError):
        decide(TENANT, fix.id, actor=actor, rationale=rationale)

    # Status is left exactly as it was — no transition happened.
    assert twin.get_fix(TENANT, fix.id).status is status
    assert not any(name == "update_fix_status" for (name, *_rest) in calls)

    # No Audit_Trail entry was written.
    assert twin.audit_entries == []
    assert not any(name == "append_audit_entry" for (name, *_rest) in calls)

    # No Publishing_Adapter call of any kind — in particular, no write.
    assert pa.writes == []
    _pa_call_names = {
        "get_media",
        "get_page",
        "update_media_alt_text",
        "update_page_content",
    }
    assert not any(name in _pa_call_names for (name, *_rest) in calls)
