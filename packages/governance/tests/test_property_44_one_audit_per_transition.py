"""Property 44 — Exactly one Audit_Trail entry per successful decision or
transition.

Feature: website-orchestrator-milestone-0, Property 44: Exactly one audit entry
per successful decision or transition

Validates: Requirements 9.5

Requirement 9.5: every successful governance decision or transition appends
**exactly one** Audit_Trail entry — no more, no fewer. This holds across all four
successful operations the Governance_Layer exposes:

* approve a Report_Only_Fix (``pending->approved``);
* approve an Auto_Applicable_Fix (``pending->applied``), whose single entry
  carries the freshly-read live BEFORE value (reconciling Req 8.4 with Req 9.5 —
  the pre-write BEFORE entry *is* the one transition entry, no second entry is
  appended after the write);
* reject a fix (``pending->rejected``);
* roll back an ``applied`` fix that has an audited BEFORE value
  (``applied->rolled_back``).

This property drives :meth:`governance.service.GovernanceService.approve_fix`,
:meth:`~governance.service.GovernanceService.reject_fix`, and
:meth:`~governance.service.GovernanceService.rollback_fix` with a broad variety
of fixes (both ``UPDATE_ALT_TEXT`` and ``UPDATE_PAGE_CONTENT`` for the
auto-applicable and rollback cases), varied ids, actors, rationales, and live /
audited values.

Both dependency fakes append every mutating call to a single ordered ``calls``
log. The property counts the ``append_audit_entry`` calls made *during* the
operation under test and asserts exactly one occurred. For the rollback case the
original ``pending->applied`` entry is seeded directly onto the fake twin
(bypassing ``append_audit_entry``) so it is **not** counted against the operation
— only the calls the operation itself makes are observed.

The fakes are network-free in-memory spies, so property runs stay deterministic.
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


# --- In-memory fakes (ordered shared ``calls`` log) ---------------------------


class FakeDigitalTwin:
    """An in-memory :class:`core.interfaces.DigitalTwinPort` spy.

    Records every mutating call in the shared, ordered ``calls`` log so the
    number of ``append_audit_entry`` calls the operation makes is observable, and
    stores appended Audit_Trail entries for content assertions.
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

    Serves canned live values and records every read/write call in the shared
    ``calls`` log.
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
    ``append_audit_entry``) so the shared ``calls`` log records only the appends
    the rollback under test makes.
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

# Freeform text for proposed / live / audited before values. The empty string is
# intentionally allowed: media that had no alt text is a valid live/before value.
_values = st.text(max_size=60)
_actors = st.text(min_size=1, max_size=20).filter(lambda s: s.strip())
_rationales = st.text(min_size=1, max_size=40).filter(lambda s: s.strip())


@st.composite
def _successful_operations(draw):
    """Generate one successful governance operation plus a fully-seeded world.

    Selects one of the four successful operations uniformly and returns a
    callable that performs it against a freshly-built service, along with the
    fakes needed to observe the operation. Each scenario is self-contained so the
    property can invoke the operation and count the audit appends it makes.
    """
    kind = draw(
        st.sampled_from(
            ["approve_report_only", "approve_auto", "reject", "rollback"]
        )
    )
    fix_id = draw(st.uuids().map(str))
    actor = draw(_actors)
    rationale = draw(_rationales)

    calls: list[tuple] = []

    if kind == "approve_report_only":
        fix = SuggestedFix(
            id=fix_id,
            tenant_id=TENANT,
            issue_id="issue-report",
            fix_type=FixType.UPDATE_PAGE_CONTENT,
            auto_applicable=0,
            reason="Content is thin; consider expanding.",
            status=FixStatus.PENDING,
        )
        twin = FakeDigitalTwin(calls, [fix])
        pa = FakePublishingAdapter(calls)
        service = GovernanceService(twin, pa)

        def op():
            return service.approve_fix(
                TENANT, fix_id, actor=actor, rationale=rationale
            )

        expected_transition = "pending->approved"

    elif kind == "approve_auto":
        proposed_value = draw(_values)
        before_value = draw(_values)
        is_alt_text = draw(st.booleans())
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
            twin = FakeDigitalTwin(calls, [fix])
            pa = FakePublishingAdapter(
                calls, media={media_id: WPMedia(id=media_id, alt_text=before_value)}
            )
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
            twin = FakeDigitalTwin(calls, [fix])
            pa = FakePublishingAdapter(
                calls, pages={page_id: WPPage(id=page_id, content=before_value)}
            )
        service = GovernanceService(twin, pa)

        def op():
            return service.approve_fix(
                TENANT, fix_id, actor=actor, rationale=rationale
            )

        expected_transition = "pending->applied"

    elif kind == "reject":
        # Reject applies to any pending fix; use a mix of report-only and
        # auto-applicable to widen coverage (rejection never touches the PA).
        auto = draw(st.booleans())
        fix = SuggestedFix(
            id=fix_id,
            tenant_id=TENANT,
            issue_id="issue-reject",
            fix_type=FixType.UPDATE_ALT_TEXT if auto else None,
            auto_applicable=1 if auto else 0,
            target_ref=TargetRef(media_id=draw(st.integers(1, 99999)))
            if auto
            else None,
            proposed_value=draw(_values) if auto else None,
            reason=None if auto else "Not needed.",
            status=FixStatus.PENDING,
        )
        twin = FakeDigitalTwin(calls, [fix])
        pa = FakePublishingAdapter(calls)
        service = GovernanceService(twin, pa)

        def op():
            return service.reject_fix(
                TENANT, fix_id, actor=actor, rationale=rationale
            )

        expected_transition = "pending->rejected"

    else:  # rollback
        before_value = draw(_values)
        applied_value = draw(_values)
        is_alt_text = draw(st.booleans())
        if is_alt_text:
            media_id = draw(st.integers(min_value=1, max_value=99999))
            fix = SuggestedFix(
                id=fix_id,
                tenant_id=TENANT,
                issue_id="issue-alt",
                fix_type=FixType.UPDATE_ALT_TEXT,
                auto_applicable=1,
                target_ref=TargetRef(media_id=media_id),
                proposed_value=applied_value,
                status=FixStatus.APPLIED,
            )
            twin = FakeDigitalTwin(calls, [fix])
            pa = FakePublishingAdapter(
                calls, media={media_id: WPMedia(id=media_id, alt_text=applied_value)}
            )
        else:
            page_id = draw(st.integers(min_value=1, max_value=99999))
            fix = SuggestedFix(
                id=fix_id,
                tenant_id=TENANT,
                issue_id="issue-content",
                fix_type=FixType.UPDATE_PAGE_CONTENT,
                auto_applicable=1,
                target_ref=TargetRef(page_id=page_id),
                proposed_value=applied_value,
                status=FixStatus.APPLIED,
            )
            twin = FakeDigitalTwin(calls, [fix])
            pa = FakePublishingAdapter(
                calls, pages={page_id: WPPage(id=page_id, content=applied_value)}
            )
        # Seed the original pending->applied entry directly so it is NOT counted
        # as an append made by the rollback operation.
        _seed_applied_audit(twin, fix_id, before_value=before_value)
        service = GovernanceService(twin, pa)

        def op():
            return service.rollback_fix(
                TENANT, fix_id, actor=actor, rationale=rationale
            )

        expected_transition = "applied->rolled_back"

    return {
        "kind": kind,
        "op": op,
        "calls": calls,
        "twin": twin,
        "fix_id": fix_id,
        "actor": actor,
        "rationale": rationale,
        "expected_transition": expected_transition,
    }


# --- Property -----------------------------------------------------------------


@settings(max_examples=200)
@given(scenario=_successful_operations())
def test_property_44_exactly_one_audit_entry_per_successful_transition(
    scenario: dict,
) -> None:
    """Any successful governance decision or transition appends exactly one
    Audit_Trail entry.

    Feature: website-orchestrator-milestone-0, Property 44: Exactly one audit
    entry per successful decision or transition

    Validates: Requirements 9.5
    """
    calls = scenario["calls"]

    # Perform the successful operation under test.
    scenario["op"]()

    # (9.5) Exactly one ``append_audit_entry`` call was made by the operation.
    # For rollback the seeded pending->applied entry was written directly onto the
    # twin (not via append_audit_entry), so it is not counted here.
    append_calls = [c for c in calls if c[0] == "append_audit_entry"]
    assert len(append_calls) == 1

    # That single appended entry belongs to the fix and records the expected
    # transition with the supplied actor and rationale.
    new_entry = scenario["twin"].audit_entries[-1]
    assert new_entry.fix_id == scenario["fix_id"]
    assert new_entry.transition == scenario["expected_transition"]
    assert new_entry.actor == scenario["actor"]
    assert new_entry.rationale == scenario["rationale"]

    # The append targeted the operation's fix.
    assert append_calls[0][1] == scenario["fix_id"]
