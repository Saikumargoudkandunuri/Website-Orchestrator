"""Property 42 — Rollback write failure preserves applied status, no rolled_back audit.

Feature: website-orchestrator-milestone-0, Property 42: Rollback write failure
preserves applied status and writes no rolled_back audit.

**Validates: Requirements 9.6**

A rollback reverses an ``applied`` Auto_Applicable_Fix by writing the audited
``before_value`` back through the Publishing_Adapter **first**, and only after
that write succeeds does it set the status to ``rolled_back`` and append one
``applied->rolled_back`` Audit_Trail entry (Req 9.2, 9.5). Requirement 9.6
governs the *failure* case: when that live write **raises**, the rollback must
fail closed by

* holding the fix's status at ``applied`` (it never advances to ``rolled_back``),
* logging and re-raising the :class:`~core.exceptions.PublishingError`, and
* writing **no** ``applied->rolled_back`` Audit_Trail entry (the only audit
  entry that survives is the seeded ``pending->applied`` capture).

This property drives that guarantee across the full input space of rollbacks
whose live write fails: both auto-applicable shapes (alt-text and page-content),
arbitrary ids, arbitrary audited ``before_value`` (present — including the empty
string, a valid value to restore), and any valid actor/rationale. In every case
the Publishing_Adapter's write raises, and we assert the re-raise, the retained
``applied`` status, the absence of any ``update_fix_status`` to ``rolled_back``,
and the absence of any new ``applied->rolled_back`` audit append.

The in-memory fakes mirror those in ``test_governance_service.py``: they record
every mutating call in a shared ordered ``calls`` log so an accidental status
transition or audit append would be observable. The
:class:`RaisingPublishingAdapter` records the write in ``calls`` (so we can
confirm the write was attempted) and then raises a typed ``WPClientError`` — a
:class:`~core.exceptions.PublishingError` — for both write methods. The seeded
``pending->applied`` audit entry is written directly onto the fake's
``audit_entries`` list (not via ``append_audit_entry``) so the ``calls`` log
records only the calls the rollback under test makes.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from core.exceptions import PublishingError, WPClientError
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

    Serves canned live values and records every read/write.
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


class RaisingPublishingAdapter(FakePublishingAdapter):
    """A Publishing_Adapter spy whose live *writes* raise a typed error.

    Mirrors the helper in ``test_governance_service.py`` but fails the write for
    **both** auto-applicable shapes (alt-text and page-content) so a rollback of
    either kind exercises the Req 9.6 write-failure path. Each write still records
    its call in the shared ``calls`` log before raising, so the test can confirm
    the write was attempted (and then failed).
    """

    def __init__(
        self,
        calls: list[tuple],
        *,
        media: dict[int, WPMedia] | None = None,
        pages: dict[int, WPPage] | None = None,
        fail_write: bool = False,
    ) -> None:
        super().__init__(calls, media=media, pages=pages)
        self._fail_write = fail_write

    def update_media_alt_text(self, media_id: int, alt_text: str) -> WPMedia:
        self.calls.append(("update_media_alt_text", media_id, alt_text))
        if self._fail_write:
            raise WPClientError("simulated rollback write failure")
        return super().update_media_alt_text(media_id, alt_text)

    def update_page_content(self, page_id: int, content: str) -> WPPage:
        self.calls.append(("update_page_content", page_id, content))
        if self._fail_write:
            raise WPClientError("simulated rollback write failure")
        return super().update_page_content(page_id, content)


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

# Valid actor/rationale: any string with non-whitespace content, so input
# validation (Req 8.11) passes and execution reaches the rollback write.
_valid_text = st.text(min_size=1, max_size=40).filter(lambda s: bool(s.strip()))

_ids = st.integers(min_value=1, max_value=2**31 - 1)
# An audited before_value that is *present*: any string, including the empty
# string (a valid value to restore, e.g. media that originally had no alt text).
_values = st.text(max_size=60)


@st.composite
def _rollback_write_failure_scenarios(draw):
    """An ``applied`` auto-applicable fix with an audited before-value present,
    whose live rollback write will raise.

    Varies across both auto-applicable shapes (alt-text, page-content), arbitrary
    ids, arbitrary present before-values, and valid actor/rationale. The live
    target is seeded on the Publishing_Adapter so the (failing) write targets a
    known resource.
    """
    kind = draw(st.sampled_from(["alt_text", "page_content"]))
    fix_id = draw(st.text(min_size=1, max_size=12).filter(lambda s: bool(s.strip())))
    actor = draw(_valid_text)
    rationale = draw(_valid_text)
    before_value = draw(_values)  # present (may be the empty string)

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
            status=FixStatus.APPLIED,
        )
        media[media_id] = WPMedia(id=media_id, alt_text=draw(_values))
    else:  # page_content
        page_id = draw(_ids)
        fix = SuggestedFix(
            id=fix_id,
            tenant_id=TENANT,
            issue_id="issue-2",
            fix_type=FixType.UPDATE_PAGE_CONTENT,
            auto_applicable=1,
            target_ref=TargetRef(page_id=page_id),
            proposed_value=draw(_values),
            status=FixStatus.APPLIED,
        )
        pages[page_id] = WPPage(id=page_id, content=draw(_values))

    return fix, actor, rationale, before_value, media, pages


# --- Property 42 --------------------------------------------------------------


@pytest.mark.property
@settings(max_examples=200)
@given(scenario=_rollback_write_failure_scenarios())
def test_property_42_rollback_write_failure_preserves_applied_no_audit(
    scenario,
) -> None:
    """A rollback whose live write raises fails closed and stays ``applied`` (Req 9.6).

    For any applied Auto_Applicable_Fix (alt-text or page-content) with an audited
    before-value present, when the Publishing_Adapter write RAISES during
    rollback, ``rollback_fix`` re-raises a :class:`PublishingError`, the status
    stays ``applied`` (never ``rolled_back``), and no new
    ``applied->rolled_back`` Audit_Trail entry is written.
    """
    fix, actor, rationale, before_value, media, pages = scenario

    calls: list[tuple] = []
    twin = FakeDigitalTwin(calls, [fix])
    pa = RaisingPublishingAdapter(calls, media=media, pages=pages, fail_write=True)
    _seed_applied_audit(twin, fix.id, before_value=before_value)
    service = GovernanceService(twin, pa)

    # The rollback write raises → the PublishingError is re-raised (Req 9.6).
    with pytest.raises(PublishingError):
        service.rollback_fix(TENANT, fix.id, actor=actor, rationale=rationale)

    # The write was attempted (and failed) before failing closed.
    write_names = {"update_media_alt_text", "update_page_content"}
    assert any(name in write_names for (name, *_rest) in calls)

    # Status held at ``applied`` — it never advances to ``rolled_back`` (Req 9.6).
    assert twin.get_fix(TENANT, fix.id).status is FixStatus.APPLIED
    assert not any(
        name == "update_fix_status" and value is FixStatus.ROLLED_BACK
        for (name, _fid, value) in (
            c for c in calls if c[0] == "update_fix_status"
        )
    )
    assert not any(name == "update_fix_status" for (name, *_rest) in calls)

    # No new rolled_back Audit_Trail entry: the only entry is the seeded
    # pending->applied capture; no applied->rolled_back append occurred (Req 9.6).
    assert not any(name == "append_audit_entry" for (name, *_rest) in calls)
    assert [e.transition for e in twin.audit_entries] == ["pending->applied"]
