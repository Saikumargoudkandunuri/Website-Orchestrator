"""Property 41 — A successful rollback writes the audited before_value back
through the Publishing_Adapter FIRST, then transitions the fix to rolled_back.

Feature: website-orchestrator-milestone-0, Property 41: Successful rollback
writes before_value first, then transitions

Validates: Requirements 9.2

Requirement 9.2: on a valid rollback (an ``applied`` Auto_Applicable_Fix whose
original ``pending->applied`` Audit_Trail entry carries a before_value), the
Governance_Layer writes the audited before_value back through the
Publishing_Adapter FIRST, and only after that write succeeds sets the status to
``rolled_back`` and writes exactly one Audit_Trail entry for the
``applied->rolled_back`` transition.

This property drives :meth:`governance.service.GovernanceService.rollback_fix`
with a broad variety of ``applied`` Auto_Applicable_Fixes — both alt-text fixes
(``UPDATE_ALT_TEXT`` targeting a media id) and page-content fixes
(``UPDATE_PAGE_CONTENT`` targeting a page id) — with varied ids and varied
audited before_values (including the empty string, which is a valid value to
restore, not a missing before-value).

Both dependency fakes append every read/write/audit/status call to a single
ordered ``calls`` log, so the mandated ordering is observable directly. The
original ``pending->applied`` audit entry is seeded directly onto the fake twin
(bypassing the shared log) so the log records only the calls the rollback under
test makes. For each generated fix the property asserts, via the indices in that
log:

    write before_value back  <  update_fix_status(ROLLED_BACK)
    write before_value back  <  append_audit(applied->rolled_back)

together with the substantive facts the ordering exists to protect: the live
write restored the exact audited before_value, the final status is
``rolled_back``, and exactly one NEW Audit_Trail entry (the
``applied->rolled_back`` transition) is appended.

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
    Req 9.2 ordering invariant is observable, and stores appended Audit_Trail
    entries for content assertions.
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


# --- Strategies ---------------------------------------------------------------

# Audited before_values are freeform text. The empty string is intentionally
# allowed: media that had no alt text before the fix (BEFORE == "") is a valid
# value to restore, not a missing before-value (Req 9.7).
_values = st.text(max_size=60)


@st.composite
def _rollback_scenarios(draw):
    """Generate an ``applied`` Auto_Applicable_Fix plus its audited before_value.

    Produces both alt-text fixes (media target) and page-content fixes (page
    target) with varied ids and varied audited before_values (including the
    empty string), and returns everything the property needs to seed the fakes
    and assert.
    """
    fix_id = draw(st.uuids().map(str))
    before_value = draw(_values)
    # The value currently live on the site (the applied/proposed value); distinct
    # from the before_value so the restore is observable.
    applied_value = draw(_values)
    actor = draw(st.text(min_size=1, max_size=20).filter(lambda s: s.strip()))
    rationale = draw(st.text(min_size=1, max_size=40).filter(lambda s: s.strip()))
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
        media = {media_id: WPMedia(id=media_id, alt_text=applied_value)}
        pages = {}
        expected_write = ("media", media_id, before_value)
        write_call = "update_media_alt_text"
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
        media = {}
        pages = {page_id: WPPage(id=page_id, content=applied_value)}
        expected_write = ("page", page_id, before_value)
        write_call = "update_page_content"

    return {
        "fix": fix,
        "media": media,
        "pages": pages,
        "before_value": before_value,
        "expected_write": expected_write,
        "write_call": write_call,
        "actor": actor,
        "rationale": rationale,
    }


# --- Property -----------------------------------------------------------------


@settings(max_examples=200)
@given(scenario=_rollback_scenarios())
def test_property_41_rollback_writes_before_value_first_then_transitions(
    scenario: dict,
) -> None:
    """For any valid rollback, ``rollback_fix`` writes the audited before_value
    back FIRST, then sets ``rolled_back`` and appends exactly one audit entry.

    Feature: website-orchestrator-milestone-0, Property 41: Successful rollback
    writes before_value first, then transitions

    Validates: Requirements 9.2
    """
    calls: list[tuple] = []
    fix = scenario["fix"]
    twin = FakeDigitalTwin(calls, [fix])
    pa = FakePublishingAdapter(
        calls, media=scenario["media"], pages=scenario["pages"]
    )
    # Seed the original pending->applied audit entry carrying the before_value.
    _seed_applied_audit(twin, fix.id, before_value=scenario["before_value"])
    service = GovernanceService(twin, pa)

    updated = service.rollback_fix(
        TENANT, fix.id, actor=scenario["actor"], rationale=scenario["rationale"]
    )

    # (9.2) The fix reaches ``rolled_back`` only after the write; both the
    # returned record and the stored record read ``rolled_back``.
    assert updated.status is FixStatus.ROLLED_BACK
    assert twin.get_fix(TENANT, fix.id).status is FixStatus.ROLLED_BACK

    # The live write restored the exact audited before_value to the correct
    # target — this is the only Publishing_Adapter write performed.
    assert pa.writes == [scenario["expected_write"]]

    # Exactly one NEW Audit_Trail entry is appended for the transition (the
    # seeded pending->applied entry is not appended via the log).
    append_calls = [c for c in calls if c[0] == "append_audit_entry"]
    assert len(append_calls) == 1
    new_entry = twin.audit_entries[-1]
    assert new_entry.fix_id == fix.id
    assert new_entry.transition == "applied->rolled_back"

    # The only status update is the single transition to ROLLED_BACK.
    status_updates = [c for c in calls if c[0] == "update_fix_status"]
    assert [c[2] for c in status_updates] == [FixStatus.ROLLED_BACK]

    # Locate the ordered milestones in the shared calls log.
    write_idx = next(
        i
        for i, c in enumerate(calls)
        if c[0] == scenario["write_call"] and c[2] == scenario["before_value"]
    )
    rolled_back_idx = next(
        i
        for i, c in enumerate(calls)
        if c[0] == "update_fix_status" and c[2] is FixStatus.ROLLED_BACK
    )
    audit_idx = next(
        i for i, c in enumerate(calls) if c[0] == "append_audit_entry"
    )

    # (9.2) write before_value back FIRST, then set ROLLED_BACK, and the
    # applied->rolled_back audit append happens after the write.
    assert write_idx < rolled_back_idx
    assert write_idx < audit_idx
