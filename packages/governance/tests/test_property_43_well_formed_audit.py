"""Property 43 — Every Audit_Trail entry a successful governance transition
writes is well-formed.

Feature: website-orchestrator-milestone-0, Property 43: Every audit entry is
well-formed

Validates: Requirements 9.4, 9.8

Requirement 9.4: every Audit_Trail entry the Governance_Layer writes for a
successful transition is well-formed — it carries a non-empty actor, a non-empty
rationale, the fix id it concerns, and a non-empty transition string describing
the state change.

Requirement 9.8: in Milestone 0 the actor is always a human — i.e. the
caller-supplied non-empty identity — so the audited actor equals the actor the
caller passed to the operation.

This property drives all four successful governance transitions through
:class:`governance.service.GovernanceService`:

    * ``approve_fix`` of a Report_Only_Fix        -> ``pending->approved``
    * ``approve_fix`` of an Auto_Applicable_Fix   -> ``pending->applied``
    * ``reject_fix``  of a pending fix            -> ``pending->rejected``
    * ``rollback_fix`` of an applied fix          -> ``applied->rolled_back``

For a broad variety of generated fixes (alt-text and page-content targets, varied
ids and values) with valid caller-supplied actor/rationale, the operation is
driven against network-free in-memory fakes and every Audit_Trail entry the
operation writes is inspected. The property asserts each written entry has a
non-empty actor equal to the caller's actor (Req 9.8), a non-empty rationale equal
to the caller's rationale, the correct fix id, and a non-empty transition string
matching the operation (Req 9.4).

For the rollback scenario the original ``pending->applied`` audit entry is seeded
directly onto the fake twin (bypassing ``append_audit_entry``) so only the entry
the rollback under test writes is asserted against the caller's identity.
"""

from __future__ import annotations

from datetime import datetime, timezone

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


# --- In-memory fakes ----------------------------------------------------------


class FakeDigitalTwin:
    """An in-memory :class:`core.interfaces.DigitalTwinPort` spy.

    Stores fixes and appended Audit_Trail entries so the entries a transition
    writes can be inspected directly.
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

    Serves canned live values and records every read/write call.
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


def _seed_applied_audit(
    twin: FakeDigitalTwin, fix_id: str, before_value: str | None
) -> None:
    """Seed the ``pending->applied`` Audit_Trail entry carrying ``before_value``.

    Written directly onto the fake's ``audit_entries`` list (not via
    ``append_audit_entry``) so the rollback under test writes exactly one new
    entry, which is the one asserted against the caller's identity.
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


# --- Strategies ---------------------------------------------------------------

# Freeform text for live/proposed values; the empty string is a valid value.
_values = st.text(max_size=60)
# Valid caller-supplied identities: non-empty after stripping whitespace.
_nonblank = lambda max_size: st.text(min_size=1, max_size=max_size).filter(
    lambda s: bool(s.strip())
)


@st.composite
def _scenarios(draw):
    """Generate one of the four successful governance transitions.

    Each scenario carries everything the property needs: the operation name, a
    suitable fix in the right starting state, the fakes' seed data, the
    caller-supplied actor/rationale, and the transition string the written audit
    entry must record.
    """
    fix_id = draw(st.uuids().map(str))
    actor = draw(_nonblank(20))
    rationale = draw(_nonblank(40))
    operation = draw(
        st.sampled_from(
            [
                "approve_report_only",
                "approve_auto_applicable",
                "reject",
                "rollback",
            ]
        )
    )
    is_alt_text = draw(st.booleans())
    live_value = draw(_values)
    proposed_value = draw(_values)
    before_value = draw(_values)

    media: dict[int, WPMedia] = {}
    pages: dict[int, WPPage] = {}
    seed_before: str | None = None

    if operation == "approve_report_only":
        # Report_Only_Fix (auto_applicable == 0): no live target needed.
        fix = SuggestedFix(
            id=fix_id,
            tenant_id=TENANT,
            issue_id="issue-report",
            fix_type=FixType.UPDATE_PAGE_CONTENT,
            auto_applicable=0,
            reason="Content is thin; consider expanding.",
            status=FixStatus.PENDING,
        )
        transition = "pending->approved"
    elif operation == "approve_auto_applicable":
        # Auto_Applicable_Fix (auto_applicable == 1) in ``pending``; the fake PA
        # must serve the live BEFORE value the approval reads before writing.
        if is_alt_text:
            media_id = draw(st.integers(min_value=1, max_value=99999))
            fix = SuggestedFix(
                id=fix_id,
                tenant_id=TENANT,
                issue_id="issue-alt",
                fix_type=FixType.UPDATE_ALT_TEXT,
                auto_applicable=1,
                target_ref=TargetRef(media_id=media_id),
                proposed_value=proposed_value,
                status=FixStatus.PENDING,
            )
            media = {media_id: WPMedia(id=media_id, alt_text=live_value)}
        else:
            page_id = draw(st.integers(min_value=1, max_value=99999))
            fix = SuggestedFix(
                id=fix_id,
                tenant_id=TENANT,
                issue_id="issue-content",
                fix_type=FixType.UPDATE_PAGE_CONTENT,
                auto_applicable=1,
                target_ref=TargetRef(page_id=page_id),
                proposed_value=proposed_value,
                status=FixStatus.PENDING,
            )
            pages = {page_id: WPPage(id=page_id, content=live_value)}
        transition = "pending->applied"
    elif operation == "reject":
        # Any pending fix may be rejected; vary auto_applicable to exercise both.
        auto = draw(st.sampled_from([0, 1]))
        fix = SuggestedFix(
            id=fix_id,
            tenant_id=TENANT,
            issue_id="issue-reject",
            fix_type=FixType.UPDATE_PAGE_CONTENT,
            auto_applicable=auto,
            target_ref=TargetRef(page_id=1) if auto == 1 else None,
            proposed_value=proposed_value if auto == 1 else None,
            reason="Not needed." if auto == 0 else None,
            status=FixStatus.PENDING,
        )
        transition = "pending->rejected"
    else:  # rollback
        # Applied Auto_Applicable_Fix with a seeded audited before_value; the PA
        # currently holds the applied value and the rollback restores before.
        seed_before = before_value
        if is_alt_text:
            media_id = draw(st.integers(min_value=1, max_value=99999))
            fix = SuggestedFix(
                id=fix_id,
                tenant_id=TENANT,
                issue_id="issue-alt",
                fix_type=FixType.UPDATE_ALT_TEXT,
                auto_applicable=1,
                target_ref=TargetRef(media_id=media_id),
                proposed_value=proposed_value,
                status=FixStatus.APPLIED,
            )
            media = {media_id: WPMedia(id=media_id, alt_text=proposed_value)}
        else:
            page_id = draw(st.integers(min_value=1, max_value=99999))
            fix = SuggestedFix(
                id=fix_id,
                tenant_id=TENANT,
                issue_id="issue-content",
                fix_type=FixType.UPDATE_PAGE_CONTENT,
                auto_applicable=1,
                target_ref=TargetRef(page_id=page_id),
                proposed_value=proposed_value,
                status=FixStatus.APPLIED,
            )
            pages = {page_id: WPPage(id=page_id, content=proposed_value)}
        transition = "applied->rolled_back"

    return {
        "operation": operation,
        "fix": fix,
        "media": media,
        "pages": pages,
        "seed_before": seed_before,
        "actor": actor,
        "rationale": rationale,
        "transition": transition,
    }


def _drive(service: GovernanceService, scenario: dict) -> None:
    """Drive the scenario's operation through the service."""
    fix = scenario["fix"]
    actor = scenario["actor"]
    rationale = scenario["rationale"]
    op = scenario["operation"]
    if op == "reject":
        service.reject_fix(TENANT, fix.id, actor=actor, rationale=rationale)
    elif op == "rollback":
        service.rollback_fix(TENANT, fix.id, actor=actor, rationale=rationale)
    else:  # both approve variants
        service.approve_fix(TENANT, fix.id, actor=actor, rationale=rationale)


# --- Property -----------------------------------------------------------------


@settings(max_examples=200)
@given(scenario=_scenarios())
def test_property_43_every_audit_entry_is_well_formed(scenario: dict) -> None:
    """Every Audit_Trail entry a successful transition writes is well-formed.

    Feature: website-orchestrator-milestone-0, Property 43: Every audit entry is
    well-formed

    Validates: Requirements 9.4, 9.8
    """
    calls: list[tuple] = []
    fix = scenario["fix"]
    twin = FakeDigitalTwin(calls, [fix])
    pa = FakePublishingAdapter(calls, media=scenario["media"], pages=scenario["pages"])
    if scenario["seed_before"] is not None:
        _seed_applied_audit(twin, fix.id, before_value=scenario["seed_before"])
    service = GovernanceService(twin, pa)

    # Only the entries appended from here on are written by the operation; any
    # earlier entry (the seeded pending->applied entry for rollback) is excluded.
    pre_count = len(twin.audit_entries)

    _drive(service, scenario)

    written = twin.audit_entries[pre_count:]

    # A successful transition always writes at least one Audit_Trail entry.
    assert written, f"{scenario['operation']} wrote no Audit_Trail entry"

    for entry in written:
        # (9.4, 9.8) Non-empty actor equal to the caller's supplied identity.
        assert entry.actor == scenario["actor"]
        assert entry.actor.strip() != ""
        # (9.4) Non-empty rationale equal to the caller's rationale.
        assert entry.rationale == scenario["rationale"]
        assert entry.rationale.strip() != ""
        # (9.4) The entry concerns the operated-on fix.
        assert entry.fix_id == fix.id
        # (9.4) A non-empty transition string matching the operation.
        assert entry.transition == scenario["transition"]
        assert entry.transition != ""
