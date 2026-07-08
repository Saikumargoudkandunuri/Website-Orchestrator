"""Property 40 — Rollback is valid only from applied with an audited before_value.

Feature: website-orchestrator-milestone-0, Property 40: Rollback is valid only
from applied with an audited before_value.

**Validates: Requirements 9.1, 9.7**

A rollback reverses an ``applied`` Auto_Applicable_Fix, and it is valid **only**
when two preconditions hold together:

* the fix is currently ``applied`` (Req 9.1), and
* an audited ``before_value`` — captured on the original ``pending->applied``
  Audit_Trail entry — is available (Req 9.7).

When either precondition fails, :meth:`GovernanceService.rollback_fix` must fail
closed by raising :class:`~core.exceptions.RollbackNotAllowedError`, performing
**no** Publishing_Adapter write, and leaving the fix's status unchanged (a
non-applied fix stays as it was, Req 9.1; an applied fix without an audited
before-value stays ``applied``, Req 9.7).

This property drives that guarantee across the full input space of *refused*
rollbacks, split into the two precondition-violating families:

* **Non-applied status** — for any of ``pending``, ``approved``, ``rejected``,
  or ``rolled_back``, the rollback is refused regardless of whether an audited
  before-value happens to exist (we seed one or not, arbitrarily): the exception
  is raised, ``pa.writes == []``, and the status is left exactly as it was.
* **Applied but no audited before-value** — for an ``applied`` fix whose
  ``pending->applied`` audit entry is either absent entirely or present but
  recorded a ``None`` before-value, the rollback is refused: the exception is
  raised, ``pa.writes == []``, and the status stays ``applied``.

The in-memory fakes mirror those in ``test_governance_service.py``: they record
every mutating call in a shared ordered ``calls`` log so an accidental status
transition or audit append would be observable, and the Publishing_Adapter is
seeded with the fix's live target so a *broken* guard that proceeded to write
would surface as a non-empty ``pa.writes`` rather than a bare ``KeyError``. The
seeded ``pending->applied`` audit entry is written directly onto the fake's
``audit_entries`` list (not via ``append_audit_entry``) so the ``calls`` log
records only the calls the rollback under test makes.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from core.exceptions import RollbackNotAllowedError
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

#: The four non-``applied`` statuses from which a rollback is always refused
#: (Req 9.1). An ``applied`` fix is handled by the missing-before-value family.
_NON_APPLIED_STATUSES = [
    FixStatus.PENDING,
    FixStatus.APPROVED,
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
# validation (Req 8.11) passes and execution reaches the rollback preconditions.
_valid_text = st.text(min_size=1, max_size=40).filter(lambda s: bool(s.strip()))

_ids = st.integers(min_value=1, max_value=2**31 - 1)
_values = st.text(max_size=60)


def _make_fix(kind: str, fix_id: str, status: FixStatus, draw):
    """Build an Auto_Applicable_Fix of ``kind`` in ``status`` plus its PA seed.

    Returns ``(fix, media, pages)`` where ``media``/``pages`` pre-seed the
    Publishing_Adapter with the fix's live target so a broken guard that
    proceeded to write would surface as a clean ``pa.writes`` assertion failure
    rather than a ``KeyError``.
    """
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
            status=status,
        )
        pages[page_id] = WPPage(id=page_id, content=draw(_values))

    return fix, media, pages


@st.composite
def _non_applied_scenarios(draw):
    """A fix in a non-``applied`` status — rollback refused regardless (Req 9.1).

    Varies across both auto-applicable shapes (alt-text, page-content), all four
    non-applied statuses, arbitrary ids/values, valid actor/rationale, and
    *whether or not* an audited before-value happens to have been seeded (either
    way the non-applied status alone forces the refusal).
    """
    status = draw(st.sampled_from(_NON_APPLIED_STATUSES))
    kind = draw(st.sampled_from(["alt_text", "page_content"]))
    fix_id = draw(st.text(min_size=1, max_size=12).filter(lambda s: bool(s.strip())))
    actor = draw(_valid_text)
    rationale = draw(_valid_text)
    seed_before = draw(st.booleans())
    before_value = draw(st.one_of(st.none(), _values)) if seed_before else None

    fix, media, pages = _make_fix(kind, fix_id, status, draw)
    return fix, status, actor, rationale, seed_before, before_value, media, pages


@st.composite
def _applied_missing_before_scenarios(draw):
    """An ``applied`` fix with NO audited before-value — rollback refused (Req 9.7).

    "No audited before-value" means either no ``pending->applied`` audit entry
    was seeded at all, or one was seeded that recorded ``None`` as its
    before-value. Varies across both auto-applicable shapes, arbitrary
    ids/values, and valid actor/rationale.
    """
    kind = draw(st.sampled_from(["alt_text", "page_content"]))
    fix_id = draw(st.text(min_size=1, max_size=12).filter(lambda s: bool(s.strip())))
    actor = draw(_valid_text)
    rationale = draw(_valid_text)
    # Two ways the audited before-value is missing: omit the applied entry, or
    # seed an applied entry that recorded None.
    seed_none_entry = draw(st.booleans())

    fix, media, pages = _make_fix(kind, fix_id, FixStatus.APPLIED, draw)
    return fix, actor, rationale, seed_none_entry, media, pages


# --- Property 40 --------------------------------------------------------------


@pytest.mark.property
@settings(max_examples=200)
@given(scenario=_non_applied_scenarios())
def test_property_40_non_applied_status_refuses_rollback(scenario) -> None:
    """A non-``applied`` fix refuses rollback, unchanged, with no write (Req 9.1).

    For any of the four non-applied statuses, any auto-applicable fix shape, any
    valid actor/rationale, and regardless of whether an audited before-value
    exists, ``rollback_fix`` raises :class:`RollbackNotAllowedError`, performs no
    Publishing_Adapter write, and leaves the status exactly as it was.
    """
    fix, status, actor, rationale, seed_before, before_value, media, pages = scenario

    calls: list[tuple] = []
    twin = FakeDigitalTwin(calls, [fix])
    pa = FakePublishingAdapter(calls, media=media, pages=pages)
    if seed_before:
        _seed_applied_audit(twin, fix.id, before_value=before_value)
    service = GovernanceService(twin, pa)

    with pytest.raises(RollbackNotAllowedError):
        service.rollback_fix(TENANT, fix.id, actor=actor, rationale=rationale)

    # Status left exactly as it was — no transition happened (Req 9.1).
    assert twin.get_fix(TENANT, fix.id).status is status
    assert not any(name == "update_fix_status" for (name, *_rest) in calls)

    # No Publishing_Adapter write of any kind (Req 9.1).
    assert pa.writes == []
    assert not any(
        name in {"update_media_alt_text", "update_page_content"}
        for (name, *_rest) in calls
    )
    # No new rolled_back Audit_Trail entry was appended.
    assert not any(name == "append_audit_entry" for (name, *_rest) in calls)


@pytest.mark.property
@settings(max_examples=200)
@given(scenario=_applied_missing_before_scenarios())
def test_property_40_applied_without_before_value_refuses_rollback(scenario) -> None:
    """An ``applied`` fix with no audited before-value refuses rollback (Req 9.7).

    For an ``applied`` auto-applicable fix whose ``pending->applied`` audit entry
    is either absent or recorded a ``None`` before-value, ``rollback_fix`` raises
    :class:`RollbackNotAllowedError`, performs no Publishing_Adapter write, and
    leaves the status at ``applied``.
    """
    fix, actor, rationale, seed_none_entry, media, pages = scenario

    calls: list[tuple] = []
    twin = FakeDigitalTwin(calls, [fix])
    pa = FakePublishingAdapter(calls, media=media, pages=pages)
    # Missing audited before-value: either no applied entry, or one recording None.
    if seed_none_entry:
        _seed_applied_audit(twin, fix.id, before_value=None)
    service = GovernanceService(twin, pa)

    with pytest.raises(RollbackNotAllowedError):
        service.rollback_fix(TENANT, fix.id, actor=actor, rationale=rationale)

    # No write; the status stays at ``applied`` (Req 9.7).
    assert pa.writes == []
    assert not any(
        name in {"update_media_alt_text", "update_page_content"}
        for (name, *_rest) in calls
    )
    assert twin.get_fix(TENANT, fix.id).status is FixStatus.APPLIED
    assert not any(name == "update_fix_status" for (name, *_rest) in calls)
    # No new rolled_back Audit_Trail entry was appended.
    assert not any(name == "append_audit_entry" for (name, *_rest) in calls)
