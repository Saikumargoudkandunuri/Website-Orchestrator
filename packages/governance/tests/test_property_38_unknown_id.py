"""Property 38 — Unknown fix ids raise not-found without writing to WordPress.

Feature: website-orchestrator-milestone-0, Property 38: Unknown fix ids raise
not-found without writing to WordPress.

**Validates: Requirements 8.9**

The Governance_Layer is the sole path for a ``SuggestedFix`` status transition.
When a decision references a fix id that does not exist for the tenant, the
operation must fail closed by raising :class:`~core.exceptions.FixNotFoundError`
**before** any Publishing_Adapter interaction, so no WordPress write is ever
performed and no Audit_Trail entry is written (Req 8.9). This holds for all three
decision entrypoints: :meth:`GovernanceService.approve_fix`,
:meth:`~GovernanceService.reject_fix`, and :meth:`~GovernanceService.rollback_fix`.

This property drives that guarantee across the full input space: for any store
state that does **not** contain the targeted id (an empty twin, or a twin holding
other fixes with different ids), any of the three operations, and any valid
actor/rationale, we assert :class:`FixNotFoundError` is raised, the
Publishing_Adapter is never called (``pa.writes == []`` and no read/write call is
logged), and no Audit_Trail entry is written.

The in-memory fakes mirror those in ``test_governance_service.py``: they record
every mutating/reading call in a shared ordered ``calls`` log so an accidental
audit append or any Publishing_Adapter interaction would be directly observable.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from core.exceptions import FixNotFoundError
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

    Records every read/write call. ``writes`` stays empty unless a write method is
    actually invoked, and any read/write is logged into the shared ``calls`` list
    — either would be the signal that the unknown-id guard failed to fail closed.
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

# Valid actor/rationale: any string with non-whitespace content, so input
# validation (Req 8.11) passes and execution reaches the unknown-id guard.
_valid_text = st.text(min_size=1, max_size=40).filter(lambda s: bool(s.strip()))

_fix_ids = st.text(min_size=1, max_size=12).filter(lambda s: bool(s.strip()))
_operations = st.sampled_from(["approve", "reject", "rollback"])


def _other_fix(fix_id: str) -> SuggestedFix:
    """A pending report-only fix under a *different* id, used to seed a
    non-empty twin that still does not contain the targeted (unknown) id."""
    return SuggestedFix(
        id=fix_id,
        tenant_id=TENANT,
        issue_id="issue-other",
        fix_type=FixType.UPDATE_PAGE_CONTENT,
        auto_applicable=0,
        reason="An unrelated fix that happens to live in the store.",
        status=FixStatus.PENDING,
    )


@st.composite
def _unknown_id_scenarios(draw):
    """Build a store that does NOT contain the targeted id, plus a random
    unknown ``fix_id``, an operation, and valid actor/rationale.

    The store is either empty or seeded with other fixes whose ids are all
    distinct from the targeted id (so the lookup genuinely misses). This covers
    both the empty-twin and populated-but-non-matching cases required by the
    property.
    """
    target_id = draw(_fix_ids)

    # A set of other ids guaranteed to exclude the targeted (unknown) id.
    other_ids = draw(
        st.sets(_fix_ids.filter(lambda s: s != target_id), max_size=4)
    )
    fixes = [_other_fix(fid) for fid in other_ids]

    operation = draw(_operations)
    actor = draw(_valid_text)
    rationale = draw(_valid_text)

    return target_id, fixes, operation, actor, rationale


# --- Property 38 --------------------------------------------------------------


@pytest.mark.property
@settings(max_examples=200)
@given(scenario=_unknown_id_scenarios())
def test_property_38_unknown_id_raises_not_found_no_wordpress_write(scenario) -> None:
    """An unknown fix id fails closed with no WordPress write, no audit entry.

    For any store that does not contain the targeted id, any of the three
    operations (approve / reject / rollback), and any valid actor/rationale, the
    decision raises :class:`FixNotFoundError`, the Publishing_Adapter is never
    called, and no Audit_Trail entry is written (Req 8.9).
    """
    target_id, fixes, operation, actor, rationale = scenario

    calls: list[tuple] = []
    twin = FakeDigitalTwin(calls, fixes)
    pa = FakePublishingAdapter(calls)
    service = GovernanceService(twin, pa)

    op = {
        "approve": service.approve_fix,
        "reject": service.reject_fix,
        "rollback": service.rollback_fix,
    }[operation]

    # Every entrypoint must fail closed on an unknown id (Req 8.9).
    with pytest.raises(FixNotFoundError):
        op(TENANT, target_id, actor=actor, rationale=rationale)

    # No WordPress write of any kind.
    assert pa.writes == []

    # No Publishing_Adapter interaction at all — not even a BEFORE read.
    _pa_call_names = {
        "get_media",
        "get_page",
        "update_media_alt_text",
        "update_page_content",
    }
    assert not any(name in _pa_call_names for (name, *_rest) in calls)

    # No Audit_Trail entry was written and no status transition occurred.
    assert twin.audit_entries == []
    assert not any(name == "append_audit_entry" for (name, *_rest) in calls)
    assert not any(name == "update_fix_status" for (name, *_rest) in calls)
