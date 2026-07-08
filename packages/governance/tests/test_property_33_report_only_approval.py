"""Property 33 — Approving a report-only fix never calls the Publishing_Adapter.

Feature: website-orchestrator-milestone-0, Property 33: Approving a report-only
fix never calls the Publishing_Adapter.

**Validates: Requirements 8.3**

A Report_Only_Fix (``auto_applicable == 0``) carries no live write. Approving one
must therefore take the report-only path in
:meth:`governance.service.GovernanceService.approve_fix`: the status transitions
``pending -> approved``, exactly one Audit_Trail entry is written (recording the
actor and rationale, ``before_value`` absent), and **no** Publishing_Adapter call
of any kind is made — no ``get_media``/``get_page`` read and no
``update_media_alt_text``/``update_page_content`` write (Req 8.3).

This property drives that guarantee across arbitrary pending Report_Only_Fixes
(varied ``fix_type``, ``reason``, ``tenant_id``, and ``id``) and arbitrary valid
actor identities and non-empty rationales, using network-free in-memory spies for
the Core_Package Protocols. Both spies append every mutating/reading call to a
shared, ordered ``calls`` log, and the Publishing_Adapter spy additionally records
its ``writes``; the property asserts that ``pa.writes == []`` and that no
Publishing_Adapter call name ever appears in the shared log.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from core.interfaces import WPMedia, WPPage
from core.types import AuditEntry, FixStatus, FixType, SuggestedFix

from governance.service import GovernanceService

# The set of Publishing_Adapter call names that must NEVER appear for a
# report-only approval (Req 8.3).
_PA_CALL_NAMES = frozenset(
    {"get_media", "get_page", "update_media_alt_text", "update_page_content"}
)


# --- In-memory, network-free fakes -------------------------------------------
#
# These mirror the spies in ``test_governance_service.py``: every mutating call
# is appended to a shared, ordered ``calls`` log, and the Publishing_Adapter also
# records ``writes``. They are redefined here (rather than imported) to keep this
# property module self-contained.


class FakeDigitalTwin:
    """An in-memory :class:`core.interfaces.DigitalTwinPort` spy."""

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
    ``writes``. For this property no read/write should ever be reached, so the
    canned stores are intentionally empty.
    """

    def __init__(self, calls: list[tuple]) -> None:
        self.calls = calls
        self.writes: list[tuple] = []

    def get_media(self, media_id: int) -> WPMedia:  # pragma: no cover - must not run
        self.calls.append(("get_media", media_id))
        raise AssertionError("Publishing_Adapter.get_media must not be called")

    def get_page(self, page_id: int) -> WPPage:  # pragma: no cover - must not run
        self.calls.append(("get_page", page_id))
        raise AssertionError("Publishing_Adapter.get_page must not be called")

    def update_media_alt_text(
        self, media_id: int, alt_text: str
    ) -> WPMedia:  # pragma: no cover - must not run
        self.calls.append(("update_media_alt_text", media_id, alt_text))
        self.writes.append(("media", media_id, alt_text))
        raise AssertionError(
            "Publishing_Adapter.update_media_alt_text must not be called"
        )

    def update_page_content(
        self, page_id: int, content: str
    ) -> WPPage:  # pragma: no cover - must not run
        self.calls.append(("update_page_content", page_id, content))
        self.writes.append(("page", page_id, content))
        raise AssertionError(
            "Publishing_Adapter.update_page_content must not be called"
        )


# --- Strategies --------------------------------------------------------------

# Identifiers/tenants: non-empty printable tokens (no surrogates / nulls).
_tokens = st.text(
    alphabet=st.characters(
        min_codepoint=0x21, max_codepoint=0x7E
    ),
    min_size=1,
    max_size=40,
)

# A valid actor identity is any non-empty, non-whitespace-only string.
_actors = st.text(min_size=1, max_size=60).filter(lambda s: s.strip() != "")

# A valid rationale is any non-empty, non-whitespace-only string.
_rationales = st.text(min_size=1, max_size=200).filter(lambda s: s.strip() != "")

# Report-only fixes vary their fix_type across the writable kinds (and None),
# their human-readable reason, tenant, and id — but always auto_applicable == 0
# and status pending.
_fix_types = st.sampled_from(
    [None, FixType.UPDATE_ALT_TEXT, FixType.UPDATE_PAGE_CONTENT]
)
_reasons = st.one_of(st.none(), st.text(max_size=200))


@st.composite
def _report_only_fixes(draw: st.DrawFn) -> SuggestedFix:
    """Generate a pending Report_Only_Fix (``auto_applicable == 0``)."""
    return SuggestedFix(
        id=draw(_tokens),
        tenant_id=draw(_tokens),
        issue_id=draw(_tokens),
        fix_type=draw(_fix_types),
        auto_applicable=0,
        reason=draw(_reasons),
        status=FixStatus.PENDING,
    )


# --- Property 33 -------------------------------------------------------------


@settings(max_examples=200)
@given(fix=_report_only_fixes(), actor=_actors, rationale=_rationales)
def test_property_33_report_only_approval_never_calls_publishing_adapter(
    fix: SuggestedFix, actor: str, rationale: str
) -> None:
    """Approving any pending Report_Only_Fix sets ``approved``, writes exactly one
    Audit_Trail entry, and makes NO Publishing_Adapter call (Req 8.3)."""
    calls: list[tuple] = []
    twin = FakeDigitalTwin(calls, [fix])
    pa = FakePublishingAdapter(calls)
    service = GovernanceService(twin, pa)

    updated = service.approve_fix(
        fix.tenant_id, fix.id, actor=actor, rationale=rationale
    )

    # Status transitions to approved (Req 8.3).
    assert updated.status is FixStatus.APPROVED
    assert twin.get_fix(fix.tenant_id, fix.id).status is FixStatus.APPROVED

    # Exactly one Audit_Trail entry, recording actor + rationale, no before_value.
    assert len(twin.audit_entries) == 1
    entry = twin.audit_entries[0]
    assert entry.fix_id == fix.id
    assert entry.actor == actor
    assert entry.rationale == rationale
    assert entry.transition == "pending->approved"
    assert entry.before_value is None

    # No Publishing_Adapter write, and no PA call of ANY kind in the shared log.
    assert pa.writes == []
    assert not any(name in _PA_CALL_NAMES for (name, *_rest) in calls)
