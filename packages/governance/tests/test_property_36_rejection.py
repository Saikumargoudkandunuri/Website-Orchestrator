"""Property 36 — Rejecting a pending fix sets rejected with an audit entry.

Feature: website-orchestrator-milestone-0, Property 36: Rejecting a pending fix
sets rejected with an audit entry

Validates: Requirements 8.7

Requirement 8.7: WHEN a reviewer rejects a pending SuggestedFix, THE
Governance_Layer SHALL set the fix's status to ``rejected`` and write exactly
one Audit_Trail entry recording the actor and rationale (the ``pending->rejected``
transition), and SHALL make no Publishing_Adapter call of any kind.

This property drives :meth:`governance.service.GovernanceService.reject_fix`
against network-free, in-memory spy implementations of the Core_Package Protocols
(:class:`~core.interfaces.DigitalTwinPort` and
:class:`~core.interfaces.PublishingAdapterPort`). Every mutating/read call is
appended to a shared, ordered ``calls`` log so we can assert that no
Publishing_Adapter call ever occurs for a rejection.

The generated fix is varied across the whole rejection-relevant input space:
report-only (``auto_applicable == 0``) and auto-applicable (``auto_applicable
== 1``) fixes, both writable fix types, with or without a write target and a
proposed value — because a rejection must behave identically regardless of the
fix's shape. The actor is any non-empty identity and the rationale any non-empty
(non-whitespace) string.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

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

# The set of Publishing_Adapter call names that must NEVER appear for a
# rejection (Req 8.7): a rejection makes no live read or write of any kind.
_PA_CALL_NAMES = {
    "get_media",
    "get_page",
    "update_media_alt_text",
    "update_page_content",
}


# --- In-memory fakes ----------------------------------------------------------


class FakeDigitalTwin:
    """An in-memory :class:`core.interfaces.DigitalTwinPort` spy.

    Stores fixes and appended Audit_Trail entries and records the ordered
    sequence of mutating calls in the shared ``calls`` log.
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

    Records every read/write call in the shared ``calls`` log and every write in
    ``writes`` so a rejection can be asserted to touch neither.
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

# Non-empty, non-whitespace text for ids / actor / rationale.
_nonblank = st.text(min_size=1, max_size=40).filter(lambda s: s.strip() != "")

# Free-form optional text (may be blank / None) for proposed values.
_optional_text = st.one_of(st.none(), st.text(min_size=0, max_size=40))


@st.composite
def _pending_fixes(draw: st.DrawFn) -> SuggestedFix:
    """A varied *pending* SuggestedFix spanning the rejection-relevant space.

    Covers both report-only (``auto_applicable == 0``) and auto-applicable
    (``auto_applicable == 1``) fixes, both writable fix types, and optional
    targets / proposed values — a rejection must behave identically for all of
    them, so we vary the shape freely.
    """
    fix_id = draw(_nonblank)
    auto_applicable = draw(st.sampled_from([0, 1]))
    fix_type = draw(st.one_of(st.none(), st.sampled_from(list(FixType))))

    target_ref = draw(
        st.one_of(
            st.none(),
            st.builds(
                TargetRef,
                media_id=st.one_of(
                    st.none(), st.integers(min_value=1, max_value=10_000)
                ),
                page_id=st.one_of(
                    st.none(), st.integers(min_value=1, max_value=10_000)
                ),
            ),
        )
    )

    return SuggestedFix(
        id=fix_id,
        tenant_id=TENANT,
        issue_id=draw(_nonblank),
        fix_type=fix_type,
        auto_applicable=auto_applicable,
        target_ref=target_ref,
        proposed_value=draw(_optional_text),
        reason=draw(_optional_text),
        status=FixStatus.PENDING,
    )


# --- Property -----------------------------------------------------------------


@settings(max_examples=200)
@given(
    fix=_pending_fixes(),
    actor=_nonblank,
    rationale=_nonblank,
)
def test_property_36_rejecting_pending_fix_sets_rejected_with_audit_entry(
    fix: SuggestedFix,
    actor: str,
    rationale: str,
) -> None:
    """For any pending fix (report-only or auto-applicable, varied shape) and a
    valid actor + non-empty rationale, ``reject_fix`` sets the status to
    ``rejected``, writes exactly one Audit_Trail entry recording the actor and
    rationale for the ``pending->rejected`` transition, and never calls the
    Publishing_Adapter.

    Feature: website-orchestrator-milestone-0, Property 36: Rejecting a pending
    fix sets rejected with an audit entry

    Validates: Requirements 8.7
    """
    calls: list[tuple] = []
    twin = FakeDigitalTwin(calls, [fix])
    pa = FakePublishingAdapter(calls)
    service = GovernanceService(twin, pa)

    updated = service.reject_fix(TENANT, fix.id, actor=actor, rationale=rationale)

    # Status transitions to rejected, and the stored fix reflects it (Req 8.7).
    assert updated.status is FixStatus.REJECTED
    assert twin.get_fix(TENANT, fix.id).status is FixStatus.REJECTED

    # Exactly one Audit_Trail entry, recording actor + rationale for the
    # pending->rejected transition, with no before_value (Req 8.7).
    assert len(twin.audit_entries) == 1
    entry = twin.audit_entries[0]
    assert entry.actor == actor
    assert entry.rationale == rationale
    assert entry.transition == "pending->rejected"
    assert entry.before_value is None
    assert entry.fix_id == fix.id
    assert entry.tenant_id == TENANT

    # No Publishing_Adapter call of any kind for a rejection (Req 8.7).
    assert pa.writes == []
    assert not any(name in _PA_CALL_NAMES for (name, *_rest) in calls)
