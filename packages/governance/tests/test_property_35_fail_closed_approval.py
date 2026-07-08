"""Property 35 — fail-closed approval preserves ``approved`` and never applies.

Feature: website-orchestrator-milestone-0
Property 35: Approval failures preserve the approved status and never reach applied

Validates: Requirements 8.6, 8.10, 8.12

For **any** pending Auto_Applicable_Fix (alt-text or page-content, with varied
targets / proposed values) and **any** injected failure mode
(a BEFORE-read failure, OR a live-write failure),
:meth:`~governance.service.GovernanceService.approve_fix`:

* raises a typed error — :class:`~core.exceptions.BeforeReadError` for a
  BEFORE-read failure (Req 8.10), or the underlying
  :class:`~core.exceptions.PublishingError` for a write failure (Req 8.6);
* leaves the fix parked at ``approved`` and it **never** reaches ``applied``
  (Req 8.12) — no ``update_fix_status`` to ``APPLIED`` ever appears in the calls
  log and the final persisted status is ``approved``;
* on a BEFORE-read failure performs **no** write and writes **no** Audit_Trail
  entry (Req 8.10);
* on a write failure leaves exactly the single mandated pre-write BEFORE audit
  entry (no applied entry) (Req 8.6).

The in-memory fakes mirror those in ``test_governance_service`` but the raising
adapter here injects failures on **both** the alt-text and page-content
read/write paths so the property can vary the fix type freely.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from core.exceptions import BeforeReadError, PublishingError, WPClientError
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

    Records every mutating call in the shared ordered ``calls`` log so the
    never-``applied`` invariant (Req 8.12) is directly observable.
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


class RaisingPublishingAdapter:
    """A Publishing_Adapter spy that fails the read OR the write on demand.

    Unlike the alt-text-only helper in ``test_governance_service``, this adapter
    injects failures on **both** the media (alt-text) and page (content) paths so
    the property can vary the fix type. Reads/writes record their call in the
    shared ``calls`` log before raising, matching the real adapter's observable
    behaviour.
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
        self.calls = calls
        self._media = media or {}
        self._pages = pages or {}
        self.writes: list[tuple] = []
        self._fail_read = fail_read
        self._fail_write = fail_write

    # reads
    def get_media(self, media_id: int) -> WPMedia:
        self.calls.append(("get_media", media_id))
        if self._fail_read:
            raise WPClientError("simulated BEFORE-read failure (media)")
        return self._media[media_id]

    def get_page(self, page_id: int) -> WPPage:
        self.calls.append(("get_page", page_id))
        if self._fail_read:
            raise WPClientError("simulated BEFORE-read failure (page)")
        return self._pages[page_id]

    # writes
    def update_media_alt_text(self, media_id: int, alt_text: str) -> WPMedia:
        self.calls.append(("update_media_alt_text", media_id, alt_text))
        if self._fail_write:
            raise WPClientError("simulated write failure (media)")
        updated = WPMedia(id=media_id, alt_text=alt_text)
        self._media[media_id] = updated
        self.writes.append(("media", media_id, alt_text))
        return updated

    def update_page_content(self, page_id: int, content: str) -> WPPage:
        self.calls.append(("update_page_content", page_id, content))
        if self._fail_write:
            raise WPClientError("simulated write failure (page)")
        updated = WPPage(id=page_id, content=content)
        self._pages[page_id] = updated
        self.writes.append(("page", page_id, content))
        return updated


# --- Strategies ---------------------------------------------------------------

_text = st.text(min_size=1, max_size=40)
_ids = st.integers(min_value=1, max_value=10_000)
# A live BEFORE value may legitimately be empty (media with no alt text).
_before_text = st.text(min_size=0, max_size=40)
_FAILURE_MODES = st.sampled_from(["read", "write"])
# A valid actor / rationale must be non-empty after stripping (Req 8.11); this
# property targets the fail-closed apply path, not input validation, so both
# are constrained to be genuinely non-blank.
_nonblank = st.text(min_size=1, max_size=40).filter(lambda s: s.strip() != "")


@st.composite
def _pending_auto_fix_and_world(draw):
    """Build a pending Auto_Applicable_Fix plus the raising adapter/twin world.

    Varies the fix type (alt-text vs page-content), the target id, the proposed
    value, the live BEFORE value, and the injected failure mode.
    """
    fix_type = draw(st.sampled_from([FixType.UPDATE_ALT_TEXT, FixType.UPDATE_PAGE_CONTENT]))
    target_id = draw(_ids)
    proposed = draw(_text)
    before = draw(_before_text)
    failure_mode = draw(_FAILURE_MODES)
    fix_id = draw(_text)
    issue_id = draw(_text)

    if fix_type is FixType.UPDATE_ALT_TEXT:
        target_ref = TargetRef(media_id=target_id)
        media = {target_id: WPMedia(id=target_id, alt_text=before)}
        pages = {}
    else:
        target_ref = TargetRef(page_id=target_id)
        media = {}
        pages = {target_id: WPPage(id=target_id, content=before)}

    fix = SuggestedFix(
        id=fix_id,
        tenant_id=TENANT,
        issue_id=issue_id,
        fix_type=fix_type,
        auto_applicable=1,
        target_ref=target_ref,
        proposed_value=proposed,
        status=FixStatus.PENDING,
    )
    return fix, media, pages, failure_mode


# --- Property 35 --------------------------------------------------------------


@pytest.mark.property
@settings(max_examples=200)
@given(
    world=_pending_auto_fix_and_world(),
    actor=_nonblank,
    rationale=_nonblank,
)
def test_property_35_fail_closed_approval_never_applies(world, actor, rationale) -> None:
    """Feature: website-orchestrator-milestone-0, Property 35: Approval failures
    preserve the approved status and never reach applied.

    Validates: Requirements 8.6, 8.10, 8.12
    """
    fix, media, pages, failure_mode = world

    calls: list[tuple] = []
    twin = FakeDigitalTwin(calls, [fix])
    pa = RaisingPublishingAdapter(
        calls,
        media=dict(media),
        pages=dict(pages),
        fail_read=(failure_mode == "read"),
        fail_write=(failure_mode == "write"),
    )
    service = GovernanceService(twin, pa)

    # The approval must fail closed with the mode-appropriate typed error.
    if failure_mode == "read":
        expected_exc = BeforeReadError
    else:
        expected_exc = PublishingError

    with pytest.raises(expected_exc):
        service.approve_fix(TENANT, fix.id, actor=actor, rationale=rationale)

    # --- Invariant: the fix NEVER reaches APPLIED (Req 8.12) ------------------
    # No status update to APPLIED is ever recorded in the calls log ...
    applied_updates = [
        c for c in calls if c[0] == "update_fix_status" and c[2] is FixStatus.APPLIED
    ]
    assert applied_updates == [], "fix must never transition to applied on failure"

    # ... and the fix is parked at APPROVED (Req 8.6, 8.10).
    assert twin.get_fix(TENANT, fix.id).status is FixStatus.APPROVED

    write_names = {"update_media_alt_text", "update_page_content"}

    if failure_mode == "read":
        # BEFORE-read failure fails closed BEFORE writing: no write attempted,
        # and no Audit_Trail entry written (Req 8.10).
        assert pa.writes == []
        assert twin.audit_entries == []
        assert not any(name in write_names for (name, *_rest) in calls)
    else:
        # Write failure: the write was attempted (and failed); exactly the one
        # mandated pre-write BEFORE audit entry exists — no applied entry (Req 8.6).
        assert pa.writes == []  # the write raised before recording success
        assert len(twin.audit_entries) == 1
        assert any(name in write_names for (name, *_rest) in calls)
        # The single audit append happened strictly before the (failed) write.
        names = [name for (name, *_rest) in calls]
        write_idx = next(i for i, n in enumerate(names) if n in write_names)
        assert names.index("append_audit_entry") < write_idx
