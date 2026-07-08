"""Property 34 — Approving an auto-applicable fix reads and persists BEFORE
prior to writing, then applies.

Feature: website-orchestrator-milestone-0, Property 34: Approving an
auto-applicable fix reads and persists BEFORE prior to writing, then applies

Validates: Requirements 8.4, 8.5

Requirement 8.4: for an Auto_Applicable_Fix the Governance_Layer reads the live
BEFORE value from WordPress immediately before writing and persists that
freshly-read value to the Audit_Trail **strictly before** performing the write.

Requirement 8.5: the fix's status is set to ``applied`` **only after** the live
write succeeds.

This property drives :meth:`governance.service.GovernanceService.approve_fix`
with a broad variety of pending Auto_Applicable_Fixes — both alt-text fixes
(``UPDATE_ALT_TEXT`` targeting a media id) and page-content fixes
(``UPDATE_PAGE_CONTENT`` targeting a page id) — with varied ids, proposed
values, and varied *live* BEFORE values served by the Publishing_Adapter fake.

Both dependency fakes append every read/write/audit/status call to a single
ordered ``calls`` log, so the mandated ordering is observable directly. For each
generated fix the property asserts, via the indices in that log:

    read BEFORE  <  append_audit(before)  <  write  <  update_fix_status(APPLIED)

together with the substantive facts the ordering exists to protect: the final
status is ``applied``, the single Audit_Trail entry carries the exact live BEFORE
value the Publishing_Adapter returned (transition ``pending->applied``), and the
live write used the fix's ``proposed_value``.

The fakes are network-free in-memory spies, so property runs stay deterministic.
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


# --- In-memory fakes (ordered shared ``calls`` log) ---------------------------


class FakeDigitalTwin:
    """An in-memory :class:`core.interfaces.DigitalTwinPort` spy.

    Records every mutating call in the shared, ordered ``calls`` log so the
    Req 8.4 ordering invariant is observable, and stores appended Audit_Trail
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

    Serves canned live BEFORE values and records every read/write call in the
    shared ``calls`` log.
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

# Freeform text for proposed values and live BEFORE values. Empty strings are
# allowed: media with no alt text (BEFORE == "") is a valid live value, and the
# write may propose any string.
_values = st.text(max_size=60)


@st.composite
def _auto_applicable_scenarios(draw):
    """Generate a pending Auto_Applicable_Fix plus its live BEFORE value.

    Produces both alt-text fixes (media target) and page-content fixes (page
    target) with varied ids, proposed values, and varied live BEFORE values,
    and returns everything the property needs to seed the fakes and assert.
    """
    fix_id = draw(st.uuids().map(str))
    proposed_value = draw(_values)
    before_value = draw(_values)
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
            proposed_value=proposed_value,
            status=FixStatus.PENDING,
        )
        media = {media_id: WPMedia(id=media_id, alt_text=before_value)}
        pages = {}
        expected_write = ("media", media_id, proposed_value)
        read_call = "get_media"
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
            proposed_value=proposed_value,
            status=FixStatus.PENDING,
        )
        media = {}
        page_id_key = page_id
        pages = {page_id_key: WPPage(id=page_id, content=before_value)}
        expected_write = ("page", page_id, proposed_value)
        read_call = "get_page"
        write_call = "update_page_content"

    return {
        "fix": fix,
        "media": media,
        "pages": pages,
        "before_value": before_value,
        "proposed_value": proposed_value,
        "expected_write": expected_write,
        "read_call": read_call,
        "write_call": write_call,
        "actor": actor,
        "rationale": rationale,
    }


# --- Property -----------------------------------------------------------------


@settings(max_examples=200)
@given(scenario=_auto_applicable_scenarios())
def test_property_34_auto_applicable_reads_persists_before_then_writes_then_applies(
    scenario: dict,
) -> None:
    """For any pending Auto_Applicable_Fix, ``approve_fix`` reads and persists
    the live BEFORE value strictly before writing, then applies.

    Feature: website-orchestrator-milestone-0, Property 34: Approving an
    auto-applicable fix reads and persists BEFORE prior to writing, then applies

    Validates: Requirements 8.4, 8.5
    """
    calls: list[tuple] = []
    fix = scenario["fix"]
    twin = FakeDigitalTwin(calls, [fix])
    pa = FakePublishingAdapter(
        calls, media=scenario["media"], pages=scenario["pages"]
    )
    service = GovernanceService(twin, pa)

    updated = service.approve_fix(
        TENANT, fix.id, actor=scenario["actor"], rationale=scenario["rationale"]
    )

    # (8.5) The fix reaches ``applied`` only after the write; the returned record
    # and the stored record both read ``applied``.
    assert updated.status is FixStatus.APPLIED
    assert twin.get_fix(TENANT, fix.id).status is FixStatus.APPLIED

    # Exactly one Audit_Trail entry, carrying the freshly-read live BEFORE value
    # for the pending->applied transition (Req 8.4).
    assert len(twin.audit_entries) == 1
    entry = twin.audit_entries[0]
    assert entry.fix_id == fix.id
    assert entry.transition == "pending->applied"
    assert entry.before_value == scenario["before_value"]

    # The live write used the fix's proposed_value against the correct target.
    assert pa.writes == [scenario["expected_write"]]

    # Locate the four ordered milestones in the shared calls log.
    names = [name for (name, *_rest) in calls]
    read_idx = names.index(scenario["read_call"])
    write_idx = names.index(scenario["write_call"])

    # The audit append that carries the freshly-read BEFORE value.
    audit_idx = next(
        i
        for i, c in enumerate(calls)
        if c[0] == "append_audit_entry"
        and c[1] == fix.id
        and c[2] == scenario["before_value"]
    )
    # The status transition to APPLIED.
    applied_idx = next(
        i
        for i, c in enumerate(calls)
        if c[0] == "update_fix_status" and c[2] is FixStatus.APPLIED
    )

    # (8.4) read BEFORE -> persist BEFORE to Audit_Trail -> write, and
    # (8.5) set APPLIED strictly after the write succeeds.
    assert read_idx < audit_idx < write_idx < applied_idx
