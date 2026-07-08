"""Property 53 — Governance decision logs carry outcome, fix id, actor, and
rationale.

Feature: website-orchestrator-milestone-0, Property 53: Governance decision logs
carry outcome, fix id, actor, and rationale

Validates: Requirements 13.3

Requirement 13.3: WHEN a governance decision completes, whether it succeeds or
fails, THE Website_Orchestrator SHALL emit a log entry recording the decision
outcome, the affected SuggestedFix identifier, the Actor, and the rationale.

This property drives every *completing* governance decision through
:class:`governance.service.GovernanceService` and asserts that a single
structured ``governance_decision`` JSON log entry is emitted carrying the correct
``outcome``, ``fix_id``, ``actor``, and ``rationale``:

    * approve a Report_Only_Fix        -> outcome ``"approved"``
    * approve an Auto_Applicable_Fix   -> outcome ``"applied"``
    * reject a pending fix             -> outcome ``"rejected"``
    * rollback an applied fix          -> outcome ``"rolled_back"``

To capture the logs deterministically, each example configures the process-global
structlog pipeline to render into a *fresh* :class:`io.StringIO` buffer via
:func:`core.logging.configure_logging` **before** running the operation. Because
the pipeline renders one single-line JSON object per entry, the buffer is parsed
line-by-line and filtered to the ``governance_decision`` event. Redaction is
disabled (``secret_values=[]``) so generated actor/rationale text is never
scrubbed, keeping the assertions exact.

The dependency fakes are network-free in-memory spies, so property runs stay
deterministic.
"""

from __future__ import annotations

import io
import json
from datetime import datetime, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

from core.interfaces import WPMedia, WPPage
from core.logging import configure_logging
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

    Stores fixes and appended Audit_Trail entries; ``list_audit_entries`` returns
    entries most-recent first, matching the real contract the rollback path reads.
    """

    def __init__(self, fixes: list[SuggestedFix]) -> None:
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
        return updated

    def append_audit_entry(self, tenant_id: str, entry: AuditEntry) -> AuditEntry:
        self.audit_entries.append(entry)
        return entry

    def list_audit_entries(self, tenant_id: str) -> list[AuditEntry]:
        return [e for e in reversed(self.audit_entries) if e.tenant_id == tenant_id]


class FakePublishingAdapter:
    """An in-memory :class:`core.interfaces.PublishingAdapterPort` spy."""

    def __init__(
        self,
        *,
        media: dict[int, WPMedia] | None = None,
        pages: dict[int, WPPage] | None = None,
    ) -> None:
        self._media = media or {}
        self._pages = pages or {}

    def get_media(self, media_id: int) -> WPMedia:
        return self._media[media_id]

    def get_page(self, page_id: int) -> WPPage:
        return self._pages[page_id]

    def update_media_alt_text(self, media_id: int, alt_text: str) -> WPMedia:
        updated = WPMedia(id=media_id, alt_text=alt_text)
        self._media[media_id] = updated
        return updated

    def update_page_content(self, page_id: int, content: str) -> WPPage:
        updated = WPPage(id=page_id, content=content)
        self._pages[page_id] = updated
        return updated


def _seed_applied_audit(
    twin: FakeDigitalTwin, fix_id: str, before_value: str
) -> None:
    """Seed the ``pending->applied`` Audit_Trail entry carrying ``before_value``,
    so the rollback path can recover the audited before-value (Req 8.4, 9.7)."""
    twin.audit_entries.append(
        AuditEntry(
            id="seed-applied",
            tenant_id=TENANT,
            fix_id=fix_id,
            actor="seed-actor",
            rationale="seed apply",
            transition="pending->applied",
            before_value=before_value,
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
    )


# --- Strategies ---------------------------------------------------------------

# Non-empty, non-whitespace actor/rationale (a valid decision requires both).
_identity = st.text(min_size=1, max_size=40).filter(lambda s: s.strip())
# Freeform text for proposed / live BEFORE values (empty strings allowed).
_values = st.text(max_size=60)


@st.composite
def _decision_scenarios(draw):
    """Generate one completing governance decision and its expected outcome.

    Covers all four completing operations: approve a Report_Only_Fix
    (``approved``), approve an Auto_Applicable_Fix (``applied``), reject a
    pending fix (``rejected``), and rollback an applied fix (``rolled_back``).
    Returns everything needed to seed the fakes, invoke the operation, and
    assert the emitted log entry.
    """
    fix_id = draw(st.uuids().map(str))
    actor = draw(_identity)
    rationale = draw(_identity)
    kind = draw(
        st.sampled_from(["approve_report_only", "approve_auto", "reject", "rollback"])
    )
    is_alt_text = draw(st.booleans())
    proposed_value = draw(_values)
    before_value = draw(_values)
    media_id = draw(st.integers(min_value=1, max_value=99999))
    page_id = draw(st.integers(min_value=1, max_value=99999))

    twin_fixes: list[SuggestedFix]
    media: dict[int, WPMedia] = {}
    pages: dict[int, WPPage] = {}

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
        operation = "approve"
        expected_outcome = "approved"

    elif kind == "approve_auto":
        if is_alt_text:
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
        else:
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
            pages = {page_id: WPPage(id=page_id, content=before_value)}
        operation = "approve"
        expected_outcome = "applied"

    elif kind == "reject":
        fix = SuggestedFix(
            id=fix_id,
            tenant_id=TENANT,
            issue_id="issue-reject",
            fix_type=FixType.UPDATE_PAGE_CONTENT,
            auto_applicable=draw(st.sampled_from([0, 1])),
            reason="Not needed.",
            status=FixStatus.PENDING,
        )
        operation = "reject"
        expected_outcome = "rejected"

    else:  # rollback an applied fix
        if is_alt_text:
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
        operation = "rollback"
        expected_outcome = "rolled_back"

    twin_fixes = [fix]

    return {
        "fix": fix,
        "operation": operation,
        "expected_outcome": expected_outcome,
        "actor": actor,
        "rationale": rationale,
        "media": media,
        "pages": pages,
        "twin_fixes": twin_fixes,
        "before_value": before_value,
        "seed_applied": kind == "rollback",
    }


def _parse_decision_entries(buffer: io.StringIO) -> list[dict]:
    """Return the parsed ``governance_decision`` JSON entries from ``buffer``.

    The logging pipeline renders one single-line JSON object per entry, so the
    buffer is split by line, each non-empty line is parsed as JSON, and the
    result is filtered to the ``governance_decision`` event (structlog records
    the message under the ``event`` key).
    """
    entries: list[dict] = []
    for line in buffer.getvalue().splitlines():
        line = line.strip()
        if not line:
            continue
        record = json.loads(line)
        if record.get("event") == "governance_decision":
            entries.append(record)
    return entries


# --- Property -----------------------------------------------------------------


@settings(max_examples=200)
@given(scenario=_decision_scenarios())
def test_property_53_decision_log_carries_outcome_fix_actor_rationale(
    scenario: dict,
) -> None:
    """For any completing governance decision, a structured ``governance_decision``
    log entry is emitted carrying the outcome, fix id, actor, and rationale.

    Feature: website-orchestrator-milestone-0, Property 53: Governance decision
    logs carry outcome, fix id, actor, and rationale

    Validates: Requirements 13.3
    """
    fix = scenario["fix"]
    actor = scenario["actor"]
    rationale = scenario["rationale"]

    twin = FakeDigitalTwin(scenario["twin_fixes"])
    if scenario["seed_applied"]:
        _seed_applied_audit(twin, fix.id, scenario["before_value"])
    pa = FakePublishingAdapter(media=scenario["media"], pages=scenario["pages"])
    service = GovernanceService(twin, pa)

    # Route the process-global logging pipeline into a fresh buffer for THIS
    # example, before the operation, so the governance logger renders here.
    # Disable redaction so generated actor/rationale text is never scrubbed.
    buffer = io.StringIO()
    configure_logging(stream=buffer, secret_values=[])

    if scenario["operation"] == "approve":
        service.approve_fix(TENANT, fix.id, actor=actor, rationale=rationale)
    elif scenario["operation"] == "reject":
        service.reject_fix(TENANT, fix.id, actor=actor, rationale=rationale)
    else:
        service.rollback_fix(TENANT, fix.id, actor=actor, rationale=rationale)

    # Exactly one governance_decision entry is emitted for the completed decision.
    entries = _parse_decision_entries(buffer)
    assert len(entries) == 1
    entry = entries[0]

    # The entry carries the decision outcome, the affected fix id, the actor, and
    # the rationale (Req 13.3), each with the expected value.
    assert entry["outcome"] == scenario["expected_outcome"]
    assert entry["fix_id"] == fix.id
    assert entry["actor"] == actor
    assert entry["rationale"] == rationale
