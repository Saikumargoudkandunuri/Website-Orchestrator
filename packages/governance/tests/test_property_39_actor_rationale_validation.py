"""Property 39 — Missing actor or empty rationale is rejected with no transition.

Feature: website-orchestrator-milestone-0, Property 39: Missing actor or empty
rationale is rejected with no transition.

**Validates: Requirements 8.11**

Every Governance_Layer decision validates its inputs and fails closed **before**
any load, status transition, Audit_Trail write, or Publishing_Adapter call
(Req 8.11). A *missing actor* is ``None`` or a blank/whitespace-only string; an
*empty rationale* is ``None`` or blank/whitespace-only. When either the actor or
the rationale is invalid, the decision must raise
:class:`~core.exceptions.InvalidDecisionError` while making no observable change:
the fix stays ``pending``, the Audit_Trail stays empty, ``pa.writes == []``, and —
because validation runs strictly before any dependency is touched — the shared
``calls`` log is empty.

This property drives that guarantee across the full input space: for any pending
fix shape (Report_Only_Fix, auto-applicable alt-text, auto-applicable
page-content — with varied ids and proposed values), any of the three decisions
(``approve_fix``, ``reject_fix``, ``rollback_fix``), and any (actor, rationale)
pair in which *at least one* of the two is invalid (the other may be valid or
invalid), we assert the exception is raised and nothing happened.

The in-memory fakes mirror those in ``test_governance_service.py``: they record
every mutating and read call in a shared ordered ``calls`` log, and the
Publishing_Adapter is seeded with the fix's live target so a *broken* guard that
proceeded past validation would surface as a non-empty ``calls``/``pa.writes``
rather than a bare ``KeyError``.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from core.exceptions import InvalidDecisionError
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
    accidental load, status transition, or Audit_Trail append is directly
    observable.
    """

    def __init__(self, calls: list[tuple], fixes: list[SuggestedFix]) -> None:
        self.calls = calls
        self._fixes: dict[str, SuggestedFix] = {f.id: f for f in fixes}
        self.audit_entries: list[AuditEntry] = []

    def list_pending_fixes(self, tenant_id: str) -> list[SuggestedFix]:
        self.calls.append(("list_pending_fixes", tenant_id))
        return [
            f
            for f in self._fixes.values()
            if f.tenant_id == tenant_id and f.status is FixStatus.PENDING
        ]

    def get_fix(self, tenant_id: str, fix_id: str) -> SuggestedFix | None:
        # Note: get_fix records into the shared calls log so a guard that loads
        # the fix *before* validating would be observable. It is also used by the
        # test's own assertions via a separate, non-logging read below.
        self.calls.append(("get_fix", fix_id))
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
        self.calls.append(("list_audit_entries", tenant_id))
        return [e for e in reversed(self.audit_entries) if e.tenant_id == tenant_id]

    def current_status(self, fix_id: str) -> FixStatus:
        """Read a fix's status for assertions WITHOUT touching the calls log."""
        return self._fixes[fix_id].status


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


# --- Strategies ---------------------------------------------------------------

# Valid text: any string with non-whitespace content (passes Req 8.11 validation).
_valid_text = st.text(min_size=1, max_size=40).filter(lambda s: bool(s.strip()))

# Invalid text: ``None`` or a blank/whitespace-only string (fails validation).
_whitespace = st.text(alphabet=" \t\n\r\v\f", min_size=0, max_size=6)
_invalid_text = st.one_of(st.none(), _whitespace)

_ids = st.integers(min_value=1, max_value=2**31 - 1)
_values = st.text(max_size=60)
_operations = st.sampled_from(["approve", "reject", "rollback"])


@st.composite
def _invalid_credentials(draw):
    """Draw an (actor, rationale) pair where AT LEAST ONE is invalid.

    Covers the three invalid combinations: invalid actor + valid rationale,
    valid actor + invalid rationale, and both invalid. The ``both_valid`` case
    is deliberately excluded — the property is about rejection.
    """
    combo = draw(
        st.sampled_from(["actor_invalid", "rationale_invalid", "both_invalid"])
    )
    if combo == "actor_invalid":
        return draw(_invalid_text), draw(_valid_text)
    if combo == "rationale_invalid":
        return draw(_valid_text), draw(_invalid_text)
    return draw(_invalid_text), draw(_invalid_text)


@st.composite
def _scenarios(draw):
    """Build a pending fix (seeded PA), an operation, and invalid credentials.

    Varies across all three fix shapes, arbitrary ids/proposed values, and all
    three operations. Every fix starts ``pending``. The PA is pre-seeded with the
    fix's live target so a *broken* guard that read/wrote before validating would
    produce observable calls (a clean assertion failure) rather than a KeyError.
    """
    kind = draw(st.sampled_from(["report_only", "alt_text", "page_content"]))
    fix_id = draw(st.text(min_size=1, max_size=12).filter(lambda s: bool(s.strip())))
    operation = draw(_operations)
    actor, rationale = draw(_invalid_credentials())

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
            status=FixStatus.PENDING,
        )
        media[media_id] = WPMedia(id=media_id, alt_text=draw(_values))
    elif kind == "page_content":
        page_id = draw(_ids)
        fix = SuggestedFix(
            id=fix_id,
            tenant_id=TENANT,
            issue_id="issue-2",
            fix_type=FixType.UPDATE_PAGE_CONTENT,
            auto_applicable=1,
            target_ref=TargetRef(page_id=page_id),
            proposed_value=draw(_values),
            status=FixStatus.PENDING,
        )
        pages[page_id] = WPPage(id=page_id, content=draw(_values))
    else:  # report_only
        fix = SuggestedFix(
            id=fix_id,
            tenant_id=TENANT,
            issue_id="issue-3",
            fix_type=FixType.UPDATE_PAGE_CONTENT,
            auto_applicable=0,
            reason=draw(_values),
            status=FixStatus.PENDING,
        )

    return fix, operation, actor, rationale, media, pages


# --- Property 39 --------------------------------------------------------------


@pytest.mark.property
@settings(max_examples=200)
@given(scenario=_scenarios())
def test_property_39_missing_actor_or_empty_rationale_rejected_no_transition(
    scenario,
) -> None:
    """Invalid actor/rationale is rejected with no transition and no side effect.

    For any pending fix, any of the three decisions, and any (actor, rationale)
    pair with at least one invalid value, the decision raises
    :class:`InvalidDecisionError`, the fix stays ``pending``, the Audit_Trail
    stays empty, no Publishing_Adapter write occurs, and — because validation runs
    strictly before any load — the shared ``calls`` log is empty (Req 8.11).
    """
    fix, operation, actor, rationale, media, pages = scenario

    calls: list[tuple] = []
    twin = FakeDigitalTwin(calls, [fix])
    pa = FakePublishingAdapter(calls, media=media, pages=pages)
    service = GovernanceService(twin, pa)

    decide = {
        "approve": service.approve_fix,
        "reject": service.reject_fix,
        "rollback": service.rollback_fix,
    }[operation]

    # The decision must fail closed with InvalidDecisionError.
    with pytest.raises(InvalidDecisionError):
        decide(TENANT, fix.id, actor=actor, rationale=rationale)

    # The fix is left exactly ``pending`` — no transition happened.
    assert twin.current_status(fix.id) is FixStatus.PENDING

    # No Audit_Trail entry was written.
    assert twin.audit_entries == []

    # No Publishing_Adapter write occurred.
    assert pa.writes == []

    # Validation ran strictly before any load or dependency call: the shared
    # calls log is empty — no get_fix, no reads, no writes, no audit append.
    assert calls == []
