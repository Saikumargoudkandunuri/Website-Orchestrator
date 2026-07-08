"""Unit tests for :class:`governance.service.GovernanceService` (task 11.1).

These tests exercise ``list_pending_fixes`` and the happy path of ``approve_fix``
for both a Report_Only_Fix and an Auto_Applicable_Fix, using network-free
in-memory spy/fake implementations of the Core_Package Protocols
(:class:`~core.interfaces.DigitalTwinPort` and
:class:`~core.interfaces.PublishingAdapterPort`).

The fakes append every mutating call to a shared, ordered ``calls`` log so the
Req 8.4 ordering invariant — the freshly-read BEFORE value is persisted to the
Audit_Trail *strictly before* the Publishing_Adapter write — is observable and
asserted directly.
"""

from __future__ import annotations

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


# --- In-memory fakes ----------------------------------------------------------


class FakeDigitalTwin:
    """An in-memory :class:`core.interfaces.DigitalTwinPort` spy.

    Stores fixes and appended Audit_Trail entries, and records the ordered
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
        """Return the tenant's Audit_Trail entries most-recent first (Req 10.7)."""
        return [
            e
            for e in reversed(self.audit_entries)
            if e.tenant_id == tenant_id
        ]


class FakePublishingAdapter:
    """An in-memory :class:`core.interfaces.PublishingAdapterPort` spy.

    Serves canned live BEFORE values and records every read/write call.
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


# --- Builders -----------------------------------------------------------------


def _report_only_fix(fix_id: str = "fix-report") -> SuggestedFix:
    return SuggestedFix(
        id=fix_id,
        tenant_id=TENANT,
        issue_id="issue-1",
        fix_type=FixType.UPDATE_PAGE_CONTENT,
        auto_applicable=0,
        reason="Content is thin; consider expanding.",
        status=FixStatus.PENDING,
    )


def _auto_alt_text_fix(fix_id: str = "fix-alt", media_id: int = 42) -> SuggestedFix:
    return SuggestedFix(
        id=fix_id,
        tenant_id=TENANT,
        issue_id="issue-2",
        fix_type=FixType.UPDATE_ALT_TEXT,
        auto_applicable=1,
        target_ref=TargetRef(media_id=media_id),
        proposed_value="A red bicycle leaning on a brick wall",
        status=FixStatus.PENDING,
    )


def _auto_content_fix(fix_id: str = "fix-content", page_id: int = 7) -> SuggestedFix:
    return SuggestedFix(
        id=fix_id,
        tenant_id=TENANT,
        issue_id="issue-3",
        fix_type=FixType.UPDATE_PAGE_CONTENT,
        auto_applicable=1,
        target_ref=TargetRef(page_id=page_id),
        proposed_value="<p>New expanded content.</p>",
        status=FixStatus.PENDING,
    )


# --- list_pending_fixes -------------------------------------------------------


def test_list_pending_fixes_returns_pending_only() -> None:
    calls: list[tuple] = []
    pending = _report_only_fix("p1")
    decided = _auto_alt_text_fix("d1").model_copy(
        update={"status": FixStatus.APPLIED}
    )
    twin = FakeDigitalTwin(calls, [pending, decided])
    service = GovernanceService(twin, FakePublishingAdapter(calls))

    result = service.list_pending_fixes(TENANT)

    assert [f.id for f in result] == ["p1"]


# --- Report_Only_Fix approval -------------------------------------------------


def test_approve_report_only_sets_approved_one_audit_no_pa_call() -> None:
    calls: list[tuple] = []
    fix = _report_only_fix()
    twin = FakeDigitalTwin(calls, [fix])
    pa = FakePublishingAdapter(calls)
    service = GovernanceService(twin, pa)

    updated = service.approve_fix(TENANT, fix.id, actor="alice", rationale="looks good")

    # Status transitions to approved (Req 8.3).
    assert updated.status is FixStatus.APPROVED
    # Exactly one Audit_Trail entry, recording actor + rationale, no before_value.
    assert len(twin.audit_entries) == 1
    entry = twin.audit_entries[0]
    assert entry.actor == "alice"
    assert entry.rationale == "looks good"
    assert entry.transition == "pending->approved"
    assert entry.before_value is None
    assert entry.fix_id == fix.id
    # No Publishing_Adapter call of any kind (Req 8.3).
    assert pa.writes == []
    pa_call_names = {"get_media", "get_page", "update_media_alt_text", "update_page_content"}
    assert not any(name in pa_call_names for (name, *_rest) in calls)


# --- Auto_Applicable_Fix approval (alt text) ----------------------------------


def test_approve_auto_applicable_alt_text_reads_before_then_writes_then_applies() -> None:
    calls: list[tuple] = []
    fix = _auto_alt_text_fix(media_id=42)
    live_before = WPMedia(id=42, alt_text="old alt text")
    twin = FakeDigitalTwin(calls, [fix])
    pa = FakePublishingAdapter(calls, media={42: live_before})
    service = GovernanceService(twin, pa)

    updated = service.approve_fix(TENANT, fix.id, actor="bob", rationale="fix alt")

    # Status becomes applied only after the write (Req 8.5).
    assert updated.status is FixStatus.APPLIED

    # Exactly one Audit_Trail entry, carrying the freshly-read BEFORE value.
    assert len(twin.audit_entries) == 1
    entry = twin.audit_entries[0]
    assert entry.before_value == "old alt text"
    assert entry.actor == "bob"
    assert entry.rationale == "fix alt"
    assert entry.transition == "pending->applied"

    # The live write used the proposed value.
    assert pa.writes == [("media", 42, "A red bicycle leaning on a brick wall")]

    # Ordering (Req 8.4): read BEFORE -> persist BEFORE to audit -> write.
    names = [name for (name, *_rest) in calls]
    assert names.index("get_media") < names.index("append_audit_entry")
    assert names.index("append_audit_entry") < names.index("update_media_alt_text")
    # Status is set to applied strictly after the write succeeds (Req 8.5).
    assert names.index("update_media_alt_text") < names.index("update_fix_status")


def test_approve_auto_applicable_persists_before_strictly_before_write() -> None:
    """Focused assertion on the Req 8.4 ordering invariant via the shared log."""
    calls: list[tuple] = []
    fix = _auto_alt_text_fix(media_id=99)
    twin = FakeDigitalTwin(calls, [fix])
    pa = FakePublishingAdapter(calls, media={99: WPMedia(id=99, alt_text="BEFORE")})
    service = GovernanceService(twin, pa)

    service.approve_fix(TENANT, fix.id, actor="carol", rationale="apply")

    # The audit-append that carries the BEFORE value must appear before any write.
    audit_idx = next(
        i for i, c in enumerate(calls)
        if c[0] == "append_audit_entry" and c[2] == "BEFORE"
    )
    write_idx = next(i for i, c in enumerate(calls) if c[0] == "update_media_alt_text")
    assert audit_idx < write_idx


# --- Auto_Applicable_Fix approval (page content) ------------------------------


def test_approve_auto_applicable_page_content_reads_before_then_writes() -> None:
    calls: list[tuple] = []
    fix = _auto_content_fix(page_id=7)
    twin = FakeDigitalTwin(calls, [fix])
    pa = FakePublishingAdapter(
        calls, pages={7: WPPage(id=7, content="<p>old</p>")}
    )
    service = GovernanceService(twin, pa)

    updated = service.approve_fix(TENANT, fix.id, actor="dave", rationale="expand")

    assert updated.status is FixStatus.APPLIED
    assert len(twin.audit_entries) == 1
    assert twin.audit_entries[0].before_value == "<p>old</p>"
    assert pa.writes == [("page", 7, "<p>New expanded content.</p>")]

    names = [name for (name, *_rest) in calls]
    assert names.index("get_page") < names.index("append_audit_entry")
    assert names.index("append_audit_entry") < names.index("update_page_content")
    assert names.index("update_page_content") < names.index("update_fix_status")


# --- Decision guards & failure handling (task 11.2) ---------------------------
#
# These cover the fail-closed guards and the auto-applicable failure paths added
# in task 11.2: input validation (Req 8.11), unknown id (Req 8.9), already-decided
# (Req 8.8), write failure (Req 8.6), BEFORE-read failure (Req 8.10), the
# never-``applied``-on-failure invariant (Req 8.12), and ``reject_fix`` (Req 8.7).

import pytest

from core.exceptions import (
    BeforeReadError,
    FixAlreadyDecidedError,
    FixNotFoundError,
    InvalidDecisionError,
    PublishingError,
    RollbackNotAllowedError,
    WPClientError,
)


class RaisingPublishingAdapter(FakePublishingAdapter):
    """A Publishing_Adapter spy whose read and/or write raise a typed error.

    Used to exercise the fail-closed BEFORE-read (Req 8.10) and write-failure
    (Req 8.6) paths without a live WordPress. Reads/writes still record their
    call in the shared ``calls`` log before raising.
    """

    def __init__(
        self,
        calls: list[tuple],
        *,
        media: dict[int, WPMedia] | None = None,
        pages: dict[int, WPPage] | None = None,
        fail_read: bool = False,
        fail_write: bool = False,
    ) -> None:
        super().__init__(calls, media=media, pages=pages)
        self._fail_read = fail_read
        self._fail_write = fail_write

    def get_media(self, media_id: int) -> WPMedia:
        self.calls.append(("get_media", media_id))
        if self._fail_read:
            raise WPClientError("simulated BEFORE-read failure")
        return self._media[media_id]

    def update_media_alt_text(self, media_id: int, alt_text: str) -> WPMedia:
        self.calls.append(("update_media_alt_text", media_id, alt_text))
        if self._fail_write:
            raise WPClientError("simulated write failure")
        return super().update_media_alt_text(media_id, alt_text)


def _decided_names(calls: list[tuple]) -> set[str]:
    return {name for (name, *_rest) in calls}


# --- Input validation (Req 8.11) ----------------------------------------------


@pytest.mark.parametrize("actor", [None, "", "   ", "\t\n"])
def test_approve_missing_actor_raises_and_makes_no_change(actor) -> None:
    calls: list[tuple] = []
    fix = _auto_alt_text_fix(media_id=42)
    twin = FakeDigitalTwin(calls, [fix])
    pa = FakePublishingAdapter(calls, media={42: WPMedia(id=42, alt_text="old")})
    service = GovernanceService(twin, pa)

    with pytest.raises(InvalidDecisionError):
        service.approve_fix(TENANT, fix.id, actor=actor, rationale="ok")

    # No transition, no audit entry, no Publishing_Adapter call (Req 8.11).
    assert twin.get_fix(TENANT, fix.id).status is FixStatus.PENDING
    assert twin.audit_entries == []
    assert calls == []


@pytest.mark.parametrize("rationale", [None, "", "   ", "\n\t"])
def test_approve_empty_rationale_raises_and_makes_no_change(rationale) -> None:
    calls: list[tuple] = []
    fix = _report_only_fix()
    twin = FakeDigitalTwin(calls, [fix])
    pa = FakePublishingAdapter(calls)
    service = GovernanceService(twin, pa)

    with pytest.raises(InvalidDecisionError):
        service.approve_fix(TENANT, fix.id, actor="alice", rationale=rationale)

    assert twin.get_fix(TENANT, fix.id).status is FixStatus.PENDING
    assert twin.audit_entries == []
    assert calls == []


@pytest.mark.parametrize("rationale", [None, "", "   "])
def test_reject_empty_rationale_raises_and_makes_no_change(rationale) -> None:
    calls: list[tuple] = []
    fix = _report_only_fix()
    twin = FakeDigitalTwin(calls, [fix])
    service = GovernanceService(twin, FakePublishingAdapter(calls))

    with pytest.raises(InvalidDecisionError):
        service.reject_fix(TENANT, fix.id, actor="alice", rationale=rationale)

    assert twin.get_fix(TENANT, fix.id).status is FixStatus.PENDING
    assert twin.audit_entries == []
    assert calls == []


# --- Unknown id (Req 8.9) -----------------------------------------------------


def test_approve_unknown_id_raises_fix_not_found_no_pa_write() -> None:
    calls: list[tuple] = []
    twin = FakeDigitalTwin(calls, [])
    pa = FakePublishingAdapter(calls)
    service = GovernanceService(twin, pa)

    with pytest.raises(FixNotFoundError):
        service.approve_fix(TENANT, "nope", actor="alice", rationale="ok")

    # No WordPress write of any kind, no audit entry (Req 8.9).
    assert pa.writes == []
    assert twin.audit_entries == []
    assert not _decided_names(calls)


def test_reject_unknown_id_raises_fix_not_found() -> None:
    calls: list[tuple] = []
    twin = FakeDigitalTwin(calls, [])
    service = GovernanceService(twin, FakePublishingAdapter(calls))

    with pytest.raises(FixNotFoundError):
        service.reject_fix(TENANT, "nope", actor="alice", rationale="ok")

    assert twin.audit_entries == []


# --- Already-decided (Req 8.8) ------------------------------------------------


@pytest.mark.parametrize(
    "status",
    [
        FixStatus.APPROVED,
        FixStatus.APPLIED,
        FixStatus.REJECTED,
        FixStatus.ROLLED_BACK,
    ],
)
def test_approve_already_decided_raises_and_leaves_status(status) -> None:
    calls: list[tuple] = []
    fix = _report_only_fix().model_copy(update={"status": status})
    twin = FakeDigitalTwin(calls, [fix])
    pa = FakePublishingAdapter(calls)
    service = GovernanceService(twin, pa)

    with pytest.raises(FixAlreadyDecidedError):
        service.approve_fix(TENANT, fix.id, actor="alice", rationale="ok")

    # Status unchanged, no audit entry, no PA call (Req 8.8).
    assert twin.get_fix(TENANT, fix.id).status is status
    assert twin.audit_entries == []
    assert pa.writes == []


@pytest.mark.parametrize(
    "status",
    [FixStatus.APPROVED, FixStatus.APPLIED, FixStatus.REJECTED, FixStatus.ROLLED_BACK],
)
def test_reject_already_decided_raises_and_leaves_status(status) -> None:
    calls: list[tuple] = []
    fix = _report_only_fix().model_copy(update={"status": status})
    twin = FakeDigitalTwin(calls, [fix])
    service = GovernanceService(twin, FakePublishingAdapter(calls))

    with pytest.raises(FixAlreadyDecidedError):
        service.reject_fix(TENANT, fix.id, actor="alice", rationale="ok")

    assert twin.get_fix(TENANT, fix.id).status is status
    assert twin.audit_entries == []


# --- Write failure keeps approved, never applied (Req 8.6, 8.12) --------------


def test_approve_write_failure_keeps_approved_never_applied() -> None:
    calls: list[tuple] = []
    fix = _auto_alt_text_fix(media_id=42)
    twin = FakeDigitalTwin(calls, [fix])
    pa = RaisingPublishingAdapter(
        calls, media={42: WPMedia(id=42, alt_text="old alt")}, fail_write=True
    )
    service = GovernanceService(twin, pa)

    with pytest.raises(PublishingError):
        service.approve_fix(TENANT, fix.id, actor="bob", rationale="apply")

    # Status is parked at approved and never reaches applied (Req 8.6, 8.12).
    assert twin.get_fix(TENANT, fix.id).status is FixStatus.APPROVED
    applied_updates = [
        c for c in calls if c[0] == "update_fix_status" and c[2] is FixStatus.APPLIED
    ]
    assert applied_updates == []

    # The only audit entry is the mandated pre-write BEFORE capture (Req 8.4);
    # no additional applied entry is written on failure.
    assert len(twin.audit_entries) == 1
    assert twin.audit_entries[0].before_value == "old alt"

    # The write was attempted (and failed) after the BEFORE capture.
    names = [name for (name, *_rest) in calls]
    assert names.index("append_audit_entry") < names.index("update_media_alt_text")


# --- BEFORE-read failure fails closed, skips write (Req 8.10, 8.12) -----------


def test_approve_before_read_failure_skips_write_keeps_approved() -> None:
    calls: list[tuple] = []
    fix = _auto_alt_text_fix(media_id=42)
    twin = FakeDigitalTwin(calls, [fix])
    pa = RaisingPublishingAdapter(calls, fail_read=True)
    service = GovernanceService(twin, pa)

    with pytest.raises(BeforeReadError):
        service.approve_fix(TENANT, fix.id, actor="carol", rationale="apply")

    # Fails closed before writing: no write, no audit entry (Req 8.10).
    assert pa.writes == []
    assert twin.audit_entries == []
    assert "update_media_alt_text" not in _decided_names(calls)

    # Status parked at approved, never applied (Req 8.10, 8.12).
    assert twin.get_fix(TENANT, fix.id).status is FixStatus.APPROVED
    applied_updates = [
        c for c in calls if c[0] == "update_fix_status" and c[2] is FixStatus.APPLIED
    ]
    assert applied_updates == []


# --- reject_fix (Req 8.7) -----------------------------------------------------


def test_reject_fix_sets_rejected_one_audit_no_pa_call() -> None:
    calls: list[tuple] = []
    fix = _auto_alt_text_fix(media_id=42)
    twin = FakeDigitalTwin(calls, [fix])
    pa = FakePublishingAdapter(calls, media={42: WPMedia(id=42, alt_text="old")})
    service = GovernanceService(twin, pa)

    updated = service.reject_fix(
        TENANT, fix.id, actor="dave", rationale="not needed"
    )

    # Status transitions to rejected (Req 8.7).
    assert updated.status is FixStatus.REJECTED
    assert twin.get_fix(TENANT, fix.id).status is FixStatus.REJECTED

    # Exactly one Audit_Trail entry recording actor + rationale (Req 8.7, 9.5).
    assert len(twin.audit_entries) == 1
    entry = twin.audit_entries[0]
    assert entry.actor == "dave"
    assert entry.rationale == "not needed"
    assert entry.transition == "pending->rejected"
    assert entry.before_value is None
    assert entry.fix_id == fix.id

    # No Publishing_Adapter call of any kind for a rejection.
    assert pa.writes == []
    pa_call_names = {"get_media", "get_page", "update_media_alt_text", "update_page_content"}
    assert not any(name in pa_call_names for (name, *_rest) in calls)


# --- rollback_fix (task 11.3, Req 9.1-9.8) ------------------------------------
#
# Rollback reverses an ``applied`` Auto_Applicable_Fix. It is valid only from
# ``applied`` and only when an audited ``before_value`` — captured on the original
# ``pending->applied`` Audit_Trail entry — is available. On a valid rollback the
# audited before-value is written back through the Publishing_Adapter FIRST, and
# only after that write succeeds is the status set to ``rolled_back`` and one
# Audit_Trail entry written (Req 9.2, 9.5). These tests seed the applied audit
# entry directly on the fake twin (bypassing the shared ``calls`` log) so the log
# observes only the calls the rollback itself makes.

from datetime import datetime, timezone


def _applied_alt_text_fix(fix_id: str = "fix-applied", media_id: int = 42) -> SuggestedFix:
    """An Auto_Applicable_Fix already in the ``applied`` state, ready to roll back."""
    return SuggestedFix(
        id=fix_id,
        tenant_id=TENANT,
        issue_id="issue-2",
        fix_type=FixType.UPDATE_ALT_TEXT,
        auto_applicable=1,
        target_ref=TargetRef(media_id=media_id),
        proposed_value="A red bicycle leaning on a brick wall",
        status=FixStatus.APPLIED,
    )


def _applied_content_fix(fix_id: str = "fix-applied-page", page_id: int = 7) -> SuggestedFix:
    return SuggestedFix(
        id=fix_id,
        tenant_id=TENANT,
        issue_id="issue-3",
        fix_type=FixType.UPDATE_PAGE_CONTENT,
        auto_applicable=1,
        target_ref=TargetRef(page_id=page_id),
        proposed_value="<p>New expanded content.</p>",
        status=FixStatus.APPLIED,
    )


def _seed_applied_audit(
    twin: FakeDigitalTwin, fix_id: str, before_value: str | None
) -> None:
    """Seed the ``pending->applied`` Audit_Trail entry carrying ``before_value``.

    Written directly onto the fake's ``audit_entries`` list (not via
    ``append_audit_entry``) so the shared ``calls`` log records only the calls the
    rollback under test makes.
    """
    twin.audit_entries.append(
        AuditEntry(
            id="seed-applied",
            tenant_id=TENANT,
            fix_id=fix_id,
            actor="bob",
            rationale="apply",
            transition="pending->applied",
            before_value=before_value,
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
    )


# --- Successful rollback (Req 9.2, 9.5) ---------------------------------------


def test_rollback_writes_before_value_first_then_sets_rolled_back() -> None:
    calls: list[tuple] = []
    fix = _applied_alt_text_fix(media_id=42)
    twin = FakeDigitalTwin(calls, [fix])
    # The live site currently holds the applied (proposed) value.
    pa = FakePublishingAdapter(
        calls, media={42: WPMedia(id=42, alt_text="A red bicycle leaning on a brick wall")}
    )
    _seed_applied_audit(twin, fix.id, before_value="old alt text")
    service = GovernanceService(twin, pa)

    updated = service.rollback_fix(TENANT, fix.id, actor="carol", rationale="revert")

    # Status becomes rolled_back only after the write (Req 9.2).
    assert updated.status is FixStatus.ROLLED_BACK
    assert twin.get_fix(TENANT, fix.id).status is FixStatus.ROLLED_BACK

    # The audited BEFORE value was written back through the Publishing_Adapter.
    assert pa.writes == [("media", 42, "old alt text")]

    # Exactly one NEW Audit_Trail entry for the transition (the seeded applied
    # entry plus this rolled_back entry = 2 total; only one appended here).
    append_calls = [c for c in calls if c[0] == "append_audit_entry"]
    assert len(append_calls) == 1
    assert twin.audit_entries[-1].transition == "applied->rolled_back"

    # Ordering (Req 9.2): write back the before_value FIRST, then set rolled_back,
    # and the audit append happens after the write.
    names = [name for (name, *_rest) in calls]
    assert names.index("update_media_alt_text") < names.index("update_fix_status")
    assert names.index("update_media_alt_text") < names.index("append_audit_entry")
    # The only status update is to ROLLED_BACK.
    status_updates = [c for c in calls if c[0] == "update_fix_status"]
    assert [c[2] for c in status_updates] == [FixStatus.ROLLED_BACK]


def test_rollback_page_content_writes_before_value_back() -> None:
    calls: list[tuple] = []
    fix = _applied_content_fix(page_id=7)
    twin = FakeDigitalTwin(calls, [fix])
    pa = FakePublishingAdapter(
        calls, pages={7: WPPage(id=7, content="<p>New expanded content.</p>")}
    )
    _seed_applied_audit(twin, fix.id, before_value="<p>old</p>")
    service = GovernanceService(twin, pa)

    updated = service.rollback_fix(TENANT, fix.id, actor="dave", rationale="revert")

    assert updated.status is FixStatus.ROLLED_BACK
    assert pa.writes == [("page", 7, "<p>old</p>")]
    names = [name for (name, *_rest) in calls]
    assert names.index("update_page_content") < names.index("update_fix_status")


def test_rollback_restores_empty_before_value() -> None:
    """An empty-string BEFORE value (media that had no alt text) is a valid
    value to restore, not a missing before-value (Req 9.7)."""
    calls: list[tuple] = []
    fix = _applied_alt_text_fix(media_id=42)
    twin = FakeDigitalTwin(calls, [fix])
    pa = FakePublishingAdapter(calls, media={42: WPMedia(id=42, alt_text="applied")})
    _seed_applied_audit(twin, fix.id, before_value="")
    service = GovernanceService(twin, pa)

    updated = service.rollback_fix(TENANT, fix.id, actor="carol", rationale="revert")

    assert updated.status is FixStatus.ROLLED_BACK
    assert pa.writes == [("media", 42, "")]


# --- Well-formed audit entry (Req 9.4, 9.8) -----------------------------------


def test_rollback_audit_entry_is_well_formed() -> None:
    calls: list[tuple] = []
    fix = _applied_alt_text_fix(media_id=42)
    twin = FakeDigitalTwin(calls, [fix])
    pa = FakePublishingAdapter(calls, media={42: WPMedia(id=42, alt_text="applied")})
    _seed_applied_audit(twin, fix.id, before_value="old alt text")
    service = GovernanceService(twin, pa)

    service.rollback_fix(TENANT, fix.id, actor="erin", rationale="reverting the change")

    entry = twin.audit_entries[-1]
    assert entry.actor == "erin"  # non-empty; human actor in M0 (Req 9.8)
    assert entry.rationale == "reverting the change"  # non-empty (Req 9.4)
    assert entry.fix_id == fix.id
    assert entry.transition == "applied->rolled_back"
    assert entry.before_value == "old alt text"


# --- Non-applied status rejected, no write, unchanged (Req 9.1) ---------------


@pytest.mark.parametrize(
    "status",
    [
        FixStatus.PENDING,
        FixStatus.APPROVED,
        FixStatus.REJECTED,
        FixStatus.ROLLED_BACK,
    ],
)
def test_rollback_non_applied_raises_no_write_unchanged(status) -> None:
    calls: list[tuple] = []
    fix = _applied_alt_text_fix(media_id=42).model_copy(update={"status": status})
    twin = FakeDigitalTwin(calls, [fix])
    pa = FakePublishingAdapter(calls, media={42: WPMedia(id=42, alt_text="applied")})
    # Even with an audited before-value present, a non-applied status is refused.
    _seed_applied_audit(twin, fix.id, before_value="old alt text")
    service = GovernanceService(twin, pa)

    with pytest.raises(RollbackNotAllowedError):
        service.rollback_fix(TENANT, fix.id, actor="carol", rationale="revert")

    # No WordPress write and the status is left unchanged (Req 9.1).
    assert pa.writes == []
    assert twin.get_fix(TENANT, fix.id).status is status
    assert not any(c[0] == "update_fix_status" for c in calls)
    assert not any(c[0] == "append_audit_entry" for c in calls)


# --- Missing before_value rejected, no write, stays applied (Req 9.7) ---------


def test_rollback_missing_before_value_raises_stays_applied() -> None:
    calls: list[tuple] = []
    fix = _applied_alt_text_fix(media_id=42)
    twin = FakeDigitalTwin(calls, [fix])
    pa = FakePublishingAdapter(calls, media={42: WPMedia(id=42, alt_text="applied")})
    # No applied-transition audit entry seeded -> no audited before_value.
    service = GovernanceService(twin, pa)

    with pytest.raises(RollbackNotAllowedError):
        service.rollback_fix(TENANT, fix.id, actor="carol", rationale="revert")

    # No write; the status stays at applied (Req 9.7).
    assert pa.writes == []
    assert twin.get_fix(TENANT, fix.id).status is FixStatus.APPLIED
    assert twin.audit_entries == []


def test_rollback_applied_entry_without_before_value_is_missing() -> None:
    """An applied audit entry that recorded no before_value counts as missing
    (Req 9.7)."""
    calls: list[tuple] = []
    fix = _applied_alt_text_fix(media_id=42)
    twin = FakeDigitalTwin(calls, [fix])
    pa = FakePublishingAdapter(calls, media={42: WPMedia(id=42, alt_text="applied")})
    _seed_applied_audit(twin, fix.id, before_value=None)
    service = GovernanceService(twin, pa)

    with pytest.raises(RollbackNotAllowedError):
        service.rollback_fix(TENANT, fix.id, actor="carol", rationale="revert")

    assert pa.writes == []
    assert twin.get_fix(TENANT, fix.id).status is FixStatus.APPLIED


# --- Rollback write failure keeps applied, no rolled_back audit (Req 9.6) -----


def test_rollback_write_failure_keeps_applied_no_rolled_back_audit() -> None:
    calls: list[tuple] = []
    fix = _applied_alt_text_fix(media_id=42)
    twin = FakeDigitalTwin(calls, [fix])
    pa = RaisingPublishingAdapter(
        calls, media={42: WPMedia(id=42, alt_text="applied")}, fail_write=True
    )
    _seed_applied_audit(twin, fix.id, before_value="old alt text")
    service = GovernanceService(twin, pa)

    with pytest.raises(PublishingError):
        service.rollback_fix(TENANT, fix.id, actor="carol", rationale="revert")

    # Status held at applied; the write was attempted and failed (Req 9.6).
    assert twin.get_fix(TENANT, fix.id).status is FixStatus.APPLIED
    assert "update_media_alt_text" in _decided_names(calls)
    # No rolled_back transition: no status update and no new audit entry.
    assert not any(c[0] == "update_fix_status" for c in calls)
    assert not any(c[0] == "append_audit_entry" for c in calls)
    # Only the seeded applied entry remains; no applied->rolled_back entry.
    assert [e.transition for e in twin.audit_entries] == ["pending->applied"]


# --- Input validation & unknown id (Req 8.11, 8.9) ----------------------------


@pytest.mark.parametrize("actor", [None, "", "   "])
def test_rollback_missing_actor_raises_and_makes_no_change(actor) -> None:
    calls: list[tuple] = []
    fix = _applied_alt_text_fix(media_id=42)
    twin = FakeDigitalTwin(calls, [fix])
    pa = FakePublishingAdapter(calls, media={42: WPMedia(id=42, alt_text="applied")})
    _seed_applied_audit(twin, fix.id, before_value="old alt text")
    service = GovernanceService(twin, pa)

    with pytest.raises(InvalidDecisionError):
        service.rollback_fix(TENANT, fix.id, actor=actor, rationale="revert")

    assert twin.get_fix(TENANT, fix.id).status is FixStatus.APPLIED
    assert pa.writes == []
    assert calls == []


@pytest.mark.parametrize("rationale", [None, "", "   "])
def test_rollback_empty_rationale_raises_and_makes_no_change(rationale) -> None:
    calls: list[tuple] = []
    fix = _applied_alt_text_fix(media_id=42)
    twin = FakeDigitalTwin(calls, [fix])
    pa = FakePublishingAdapter(calls, media={42: WPMedia(id=42, alt_text="applied")})
    _seed_applied_audit(twin, fix.id, before_value="old alt text")
    service = GovernanceService(twin, pa)

    with pytest.raises(InvalidDecisionError):
        service.rollback_fix(TENANT, fix.id, actor="carol", rationale=rationale)

    assert twin.get_fix(TENANT, fix.id).status is FixStatus.APPLIED
    assert pa.writes == []
    assert calls == []


def test_rollback_unknown_id_raises_fix_not_found_no_write() -> None:
    calls: list[tuple] = []
    twin = FakeDigitalTwin(calls, [])
    pa = FakePublishingAdapter(calls)
    service = GovernanceService(twin, pa)

    with pytest.raises(FixNotFoundError):
        service.rollback_fix(TENANT, "nope", actor="carol", rationale="revert")

    assert pa.writes == []
    assert twin.audit_entries == []
