"""Governance_Layer service — the sole path for a ``SuggestedFix`` status
transition (Req 8.2).

:class:`GovernanceService` implements :class:`core.interfaces.GovernancePort`.
It reaches the Digital_Twin and the Publishing_Adapter **only** through the
Core_Package Protocols (:class:`~core.interfaces.DigitalTwinPort` and
:class:`~core.interfaces.PublishingAdapterPort`), which are injected at
construction time, so this subsystem depends on Core_Package alone.

Scope of this module (task 11.1)
--------------------------------
This implements :meth:`~GovernanceService.list_pending_fixes` and the **happy
path** of :meth:`~GovernanceService.approve_fix`:

* **Report_Only_Fix** (``auto_applicable == 0``): set status to ``approved``,
  write exactly one Audit_Trail entry recording the actor and rationale, and
  make no Publishing_Adapter call (Req 8.3).
* **Auto_Applicable_Fix** (``auto_applicable == 1``): read the live BEFORE value
  from WordPress immediately before writing and persist that freshly-read value
  to the Audit_Trail **strictly before** performing the write (Req 8.4); perform
  the write; and set status to ``applied`` **only after** the write succeeds
  (Req 8.5).

Every decision emits a structured governance decision log carrying the outcome,
fix id, actor, and rationale (Req 13.3).

Scope added in task 11.2
------------------------
The decision guards and ``reject_fix`` are now implemented:

* :meth:`_validate_inputs` fails closed on a missing actor or an empty/whitespace
  rationale (``InvalidDecisionError``) **before** any load, so no status
  transition, audit entry, or Publishing_Adapter call occurs (Req 8.11).
* :meth:`_load_fix` raises ``FixNotFoundError`` for an unknown id and performs no
  WordPress write (Req 8.9); the already-decided guard (``FixAlreadyDecidedError``)
  is applied by :meth:`approve_fix` / :meth:`reject_fix` via :meth:`_ensure_pending`
  (Req 8.8), kept out of the shared loader so ``rollback_fix`` (task 11.3) can act
  on an already-``applied`` fix.
* The auto-applicable approval fails closed on a BEFORE-read failure
  (``BeforeReadError``, skip the write) and on a write failure (keep ``approved``);
  in both cases the fix never reaches ``applied`` (Req 8.6, 8.10, 8.12).
* :meth:`reject_fix` sets ``rejected`` and writes exactly one Audit_Trail entry
  (Req 8.7).

Scope added in task 11.3
------------------------
:meth:`rollback_fix` reverses an ``applied`` Auto_Applicable_Fix:

* It is valid **only** from ``applied`` and only when an audited ``before_value``
  is available — recovered from the ``pending->applied`` Audit_Trail entry via
  :meth:`_find_applied_before_value`. A non-``applied`` status or a missing
  before-value fails closed with :class:`~core.exceptions.RollbackNotAllowedError`,
  performing no write (status unchanged / held at ``applied``) (Req 9.1, 9.7).
* On a valid rollback the audited ``before_value`` is written back through the
  Publishing_Adapter **first**; only after that write succeeds is the status set to
  ``rolled_back`` and exactly one ``applied->rolled_back`` Audit_Trail entry written
  (Req 9.2, 9.5). A rollback write failure holds the status at ``applied``, logs,
  re-raises, and writes no ``rolled_back`` entry (Req 9.6).

Audit-entry ordering reconciliation (Req 8.4 vs Req 9.5)
--------------------------------------------------------
For an auto-applicable approval the freshly-read BEFORE value must be persisted to
the Audit_Trail **strictly before** the live write (Req 8.4), yet a *successful*
transition must produce **exactly one** Audit_Trail entry (Req 9.5). These are
reconciled by writing a single entry — the ``pending->applied`` entry carrying the
BEFORE value — before the write, and *not* appending a second entry after the
write succeeds (the pre-write entry represents the successful transition). Because
that single entry is the only ``append_audit_entry`` call the path ever makes, a
failed approval never appends an *additional* applied entry: on a BEFORE-read
failure no entry is written at all (the failure precedes the append), and on a
write failure only the mandated pre-write BEFORE capture exists while the status is
held at ``approved`` and never advances to ``applied`` (Req 8.6, 8.12).
"""

from __future__ import annotations

import uuid

from core.exceptions import (
    BeforeReadError,
    FixAlreadyDecidedError,
    FixNotFoundError,
    GovernanceError,
    InvalidDecisionError,
    PublishingError,
    RollbackNotAllowedError,
)
from core.interfaces import DigitalTwinPort, PublishingAdapterPort
from core.logging import get_logger, operation_trace
from core.types import AuditEntry, FixStatus, FixType, SuggestedFix
from core.utils import utc_now

__all__ = ["GovernanceService"]

_log = get_logger("governance")


def _new_id() -> str:
    """Return a fresh opaque identifier for an Audit_Trail entry."""
    return uuid.uuid4().hex


class GovernanceService:
    """A :class:`core.interfaces.GovernancePort` backed by injected Core Protocols.

    Parameters
    ----------
    digital_twin:
        The :class:`~core.interfaces.DigitalTwinPort` used to read fixes and
        append Audit_Trail entries.
    publishing_adapter:
        The :class:`~core.interfaces.PublishingAdapterPort` — the only writer to
        the live WordPress site, called for Auto_Applicable_Fixes exclusively.
    """

    def __init__(
        self,
        digital_twin: DigitalTwinPort,
        publishing_adapter: PublishingAdapterPort,
    ) -> None:
        self._twin = digital_twin
        self._pa = publishing_adapter

    # --- Reads ----------------------------------------------------------------

    def list_pending_fixes(self, tenant_id: str) -> list[SuggestedFix]:
        """Return the fixes awaiting a decision for ``tenant_id`` (Req 8.1)."""
        return list(self._twin.list_pending_fixes(tenant_id))

    # --- Decisions ------------------------------------------------------------

    def approve_fix(
        self, tenant_id: str, fix_id: str, actor: str, rationale: str
    ) -> SuggestedFix:
        """Approve the fix ``fix_id`` on behalf of ``actor`` (Req 8.3-8.5).

        For a Report_Only_Fix the fix is marked ``approved`` and one Audit_Trail
        entry is written, with no live write. For an Auto_Applicable_Fix the live
        BEFORE value is read and persisted to the Audit_Trail strictly before the
        write; the write is then performed; and the fix is marked ``applied``
        only after the write succeeds.
        """
        with operation_trace():
            self._validate_inputs(actor, rationale)
            fix = self._load_fix(tenant_id, fix_id)
            self._ensure_pending(fix)

            if fix.auto_applicable == 1:
                return self._approve_auto_applicable(
                    tenant_id, fix, actor, rationale
                )
            return self._approve_report_only(tenant_id, fix, actor, rationale)

    # --- Report-only path -----------------------------------------------------

    def _approve_report_only(
        self,
        tenant_id: str,
        fix: SuggestedFix,
        actor: str,
        rationale: str,
    ) -> SuggestedFix:
        """Approve a Report_Only_Fix: set ``approved`` + one audit entry, no PA
        call (Req 8.3)."""
        updated = self._twin.update_fix_status(
            tenant_id, fix.id, FixStatus.APPROVED
        )
        self._append_audit(
            tenant_id,
            fix_id=fix.id,
            actor=actor,
            rationale=rationale,
            transition="pending->approved",
            before_value=None,
        )
        self._log_decision(
            outcome="approved",
            fix_id=fix.id,
            actor=actor,
            rationale=rationale,
        )
        return updated

    # --- Auto-applicable path -------------------------------------------------

    def _approve_auto_applicable(
        self,
        tenant_id: str,
        fix: SuggestedFix,
        actor: str,
        rationale: str,
    ) -> SuggestedFix:
        """Approve an Auto_Applicable_Fix: persist the freshly-read BEFORE value
        strictly before the write, write, then set ``applied`` (Req 8.4, 8.5).

        Fails closed on either dependency failure so the fix never reaches
        ``applied`` (Req 8.12):

        * BEFORE-read failure -> skip the write, hold status at ``approved``, log,
          and re-raise as :class:`~core.exceptions.BeforeReadError` (Req 8.10).
        * write failure -> hold status at ``approved``, log, and re-raise the
          Publishing_Adapter error (Req 8.6).
        """
        # 1. Read the live BEFORE value immediately before writing (Req 8.4). If
        #    the read fails, fail closed BEFORE writing anything: no audit entry
        #    is appended and the fix is parked at ``approved`` (Req 8.10, 8.12).
        try:
            before_value = self._read_before_value(fix)
        except PublishingError as exc:
            self._fail_closed_to_approved(tenant_id, fix)
            self._log_failure(
                reason="before_read_failed",
                fix_id=fix.id,
                actor=actor,
                error=exc,
            )
            raise BeforeReadError(
                f"Could not read the live BEFORE value for fix {fix.id!r}; "
                "skipping the write and holding status at 'approved'."
            ) from exc

        # 2. Persist that freshly-read BEFORE value to the Audit_Trail STRICTLY
        #    before performing the write (Req 8.4). This single entry records the
        #    successful pending->applied transition (Req 9.5); no second entry is
        #    appended after the write, so a failed write never leaves an extra
        #    applied entry.
        self._append_audit(
            tenant_id,
            fix_id=fix.id,
            actor=actor,
            rationale=rationale,
            transition="pending->applied",
            before_value=before_value,
        )

        # 3. Perform the live write through the Publishing_Adapter. On failure,
        #    fail closed: park the fix at ``approved`` (never ``applied``), log,
        #    and re-raise (Req 8.6, 8.12).
        try:
            self._write_proposed_value(fix)
        except PublishingError as exc:
            self._fail_closed_to_approved(tenant_id, fix)
            self._log_failure(
                reason="write_failed",
                fix_id=fix.id,
                actor=actor,
                error=exc,
            )
            raise

        # 4. Set status to applied ONLY AFTER the write succeeds (Req 8.5).
        updated = self._twin.update_fix_status(
            tenant_id, fix.id, FixStatus.APPLIED
        )
        self._log_decision(
            outcome="applied",
            fix_id=fix.id,
            actor=actor,
            rationale=rationale,
        )
        return updated

    def _fail_closed_to_approved(
        self, tenant_id: str, fix: SuggestedFix
    ) -> None:
        """Park an auto-applicable fix at ``approved`` after a failed apply.

        Req 8.6 and 8.10 require the fix to be held at ``approved`` (decided but
        not applied) when the BEFORE-read or the live write fails. The fix never
        advances to ``applied`` on any failure (Req 8.12)."""
        self._twin.update_fix_status(tenant_id, fix.id, FixStatus.APPROVED)

    def _read_before_value(self, fix: SuggestedFix) -> str:
        """Read the live BEFORE value for ``fix`` via the Publishing_Adapter.

        The read target is selected by the fix's ``fix_type`` and ``target_ref``:
        media ``alt_text`` for an alt-text fix, page ``content`` for a page fix.
        """
        target = fix.target_ref
        if fix.fix_type is FixType.UPDATE_ALT_TEXT:
            if target is None or target.media_id is None:
                raise GovernanceError(
                    f"Auto-applicable alt-text fix {fix.id!r} has no media target."
                )
            media = self._pa.get_media(target.media_id)
            return media.alt_text
        if fix.fix_type is FixType.UPDATE_PAGE_CONTENT:
            if target is None or target.page_id is None:
                raise GovernanceError(
                    f"Auto-applicable content fix {fix.id!r} has no page target."
                )
            page = self._pa.get_page(target.page_id)
            return page.content
        raise GovernanceError(
            f"Fix {fix.id!r} has no writable fix_type for an auto-applicable "
            "approval."
        )

    def _write_proposed_value(self, fix: SuggestedFix) -> None:
        """Write the fix's ``proposed_value`` to the live site (Req 6.2)."""
        target = fix.target_ref
        proposed = fix.proposed_value or ""
        if fix.fix_type is FixType.UPDATE_ALT_TEXT:
            assert target is not None and target.media_id is not None
            self._pa.update_media_alt_text(target.media_id, proposed)
        elif fix.fix_type is FixType.UPDATE_PAGE_CONTENT:
            assert target is not None and target.page_id is not None
            self._pa.update_page_content(target.page_id, proposed)
        else:  # pragma: no cover - guarded by _read_before_value
            raise GovernanceError(
                f"Fix {fix.id!r} has no writable fix_type."
            )

    # --- Shared helpers (extended by tasks 11.2 / 11.3) -----------------------

    #: Statuses that mean a fix has already been decided and cannot be
    #: approved or rejected again (Req 8.8).
    _DECIDED_STATUSES = frozenset(
        {
            FixStatus.APPROVED,
            FixStatus.APPLIED,
            FixStatus.REJECTED,
            FixStatus.ROLLED_BACK,
        }
    )

    def _validate_inputs(self, actor: str, rationale: str) -> None:
        """Fail closed on a missing actor or an empty/whitespace rationale.

        Runs **before** any load, so an invalid decision performs no status
        transition, writes no Audit_Trail entry, and makes no Publishing_Adapter
        call (Req 8.11). A missing actor is ``None`` or a blank/whitespace-only
        string; an empty rationale is ``None`` or blank/whitespace-only.
        """
        if actor is None or not actor.strip():
            raise InvalidDecisionError(
                "A governance decision requires a non-empty actor identity."
            )
        if rationale is None or not rationale.strip():
            raise InvalidDecisionError(
                "A governance decision requires a non-empty rationale."
            )

    def _load_fix(self, tenant_id: str, fix_id: str) -> SuggestedFix:
        """Look up the targeted fix, or fail closed if it does not exist.

        An unknown id raises :class:`~core.exceptions.FixNotFoundError`; because
        this runs before any Publishing_Adapter interaction, no WordPress write
        occurs (Req 8.9). This loader is shared by every decision, so it does
        **not** enforce the already-decided guard — ``rollback_fix`` must be able
        to load an already-``applied`` fix. The pending-state guard is applied by
        :meth:`_ensure_pending` from :meth:`approve_fix` / :meth:`reject_fix`.
        """
        fix = self._twin.get_fix(tenant_id, fix_id)
        if fix is None:
            raise FixNotFoundError(
                f"Fix {fix_id!r} was not found for tenant {tenant_id!r}."
            )
        return fix

    def _ensure_pending(self, fix: SuggestedFix) -> None:
        """Guard that ``fix`` is still ``pending`` before approve/reject.

        A fix already in ``approved``, ``applied``, ``rejected``, or
        ``rolled_back`` raises :class:`~core.exceptions.FixAlreadyDecidedError`
        and its status is left unchanged (Req 8.8)."""
        if fix.status in self._DECIDED_STATUSES:
            raise FixAlreadyDecidedError(
                f"Fix {fix.id!r} is already {fix.status.value!r} and cannot be "
                "decided again."
            )

    def _append_audit(
        self,
        tenant_id: str,
        *,
        fix_id: str,
        actor: str,
        rationale: str,
        transition: str,
        before_value: str | None,
    ) -> AuditEntry:
        """Append exactly one well-formed Audit_Trail entry (Req 9.3-9.5)."""
        entry = AuditEntry(
            id=_new_id(),
            tenant_id=tenant_id,
            fix_id=fix_id,
            actor=actor,
            rationale=rationale,
            transition=transition,
            before_value=before_value,
            created_at=utc_now(),
        )
        return self._twin.append_audit_entry(tenant_id, entry)

    def _log_decision(
        self,
        *,
        outcome: str,
        fix_id: str,
        actor: str,
        rationale: str,
    ) -> None:
        """Emit a structured governance decision log (Req 13.3).

        The entry carries the decision ``outcome``, the affected ``fix_id``, the
        ``actor``, and the ``rationale`` so decisions are auditable in the logs.
        """
        _log.info(
            "governance_decision",
            outcome=outcome,
            fix_id=fix_id,
            actor=actor,
            rationale=rationale,
        )

    def _log_failure(
        self,
        *,
        reason: str,
        fix_id: str,
        actor: str,
        error: Exception,
    ) -> None:
        """Emit a structured governance failure log for a fail-closed apply.

        Records the ``reason`` (e.g. ``before_read_failed`` / ``write_failed``),
        the affected ``fix_id``, the ``actor``, and the error type so a denied
        auto-applicable approval is diagnosable without leaking the error's
        payload (Req 8.6, 8.10)."""
        _log.error(
            "governance_apply_failed",
            reason=reason,
            fix_id=fix_id,
            actor=actor,
            error_type=type(error).__name__,
        )

    # --- Rejection ------------------------------------------------------------

    def reject_fix(
        self, tenant_id: str, fix_id: str, actor: str, rationale: str
    ) -> SuggestedFix:
        """Reject the fix ``fix_id`` on behalf of ``actor`` (Req 8.7).

        Validates the inputs (Req 8.11), loads the fix (unknown id ->
        ``FixNotFoundError``, Req 8.9), and guards that it is still ``pending``
        (already-decided -> ``FixAlreadyDecidedError``, Req 8.8). It then sets the
        status to ``rejected`` and writes exactly one Audit_Trail entry recording
        the actor and rationale (Req 8.7, 9.5). No Publishing_Adapter call is ever
        made for a rejection.
        """
        with operation_trace():
            self._validate_inputs(actor, rationale)
            fix = self._load_fix(tenant_id, fix_id)
            self._ensure_pending(fix)

            updated = self._twin.update_fix_status(
                tenant_id, fix.id, FixStatus.REJECTED
            )
            self._append_audit(
                tenant_id,
                fix_id=fix.id,
                actor=actor,
                rationale=rationale,
                transition="pending->rejected",
                before_value=None,
            )
            self._log_decision(
                outcome="rejected",
                fix_id=fix.id,
                actor=actor,
                rationale=rationale,
            )
            return updated

    def rollback_fix(
        self, tenant_id: str, fix_id: str, actor: str, rationale: str
    ) -> SuggestedFix:
        """Roll back the applied fix ``fix_id`` on behalf of ``actor`` (Req 9.1, 9.2).

        A rollback is valid **only** when the fix is currently ``applied`` and an
        audited ``before_value`` — captured on the original ``pending->applied``
        transition — is available:

        * Missing actor / empty rationale -> ``InvalidDecisionError`` before any
          load, so no transition, no audit entry, no Publishing_Adapter call
          (Req 8.11).
        * Unknown id -> ``FixNotFoundError``, no WordPress write (Req 8.9).
        * Status is not ``applied`` -> ``RollbackNotAllowedError``, no write, the
          status is left unchanged (Req 9.1).
        * No audited ``before_value`` -> ``RollbackNotAllowedError``, no write, the
          status stays ``applied`` (Req 9.7).

        On a valid rollback the audited ``before_value`` is written back through
        the Publishing_Adapter and, **only after** that write succeeds, the status
        is set to ``rolled_back`` and exactly one Audit_Trail entry recording the
        ``applied->rolled_back`` transition is written (Req 9.2, 9.5). If the
        rollback write fails, the status is held at ``applied``, the failure is
        logged, the Publishing_Adapter error is re-raised, and **no**
        ``rolled_back`` Audit_Trail entry is written (Req 9.6).
        """
        with operation_trace():
            self._validate_inputs(actor, rationale)
            fix = self._load_fix(tenant_id, fix_id)

            # Precondition 1: rollback is valid only from ``applied`` (Req 9.1).
            # Any other status fails closed with a typed error, no write, and the
            # status is left unchanged.
            if fix.status is not FixStatus.APPLIED:
                raise RollbackNotAllowedError(
                    f"Fix {fix.id!r} is {fix.status.value!r} and cannot be rolled "
                    "back; a rollback is valid only from 'applied'."
                )

            # Precondition 2: an audited BEFORE value must exist (Req 9.7). It was
            # captured on the original pending->applied transition. When it is
            # absent we reject the rollback with a typed error, perform no write,
            # and leave the status at ``applied``.
            before_value = self._find_applied_before_value(tenant_id, fix.id)
            if before_value is None:
                raise RollbackNotAllowedError(
                    f"Fix {fix.id!r} has no audited before_value; the rollback is "
                    "rejected and the status stays 'applied'."
                )

            # Write the audited BEFORE value back through the Publishing_Adapter
            # FIRST (Req 9.2). On failure fail closed: hold status at ``applied``,
            # log, re-raise, and write NO rolled_back audit entry (Req 9.6).
            try:
                self._write_target_value(fix, before_value)
            except PublishingError as exc:
                self._log_failure(
                    reason="rollback_write_failed",
                    fix_id=fix.id,
                    actor=actor,
                    error=exc,
                )
                raise

            # Only AFTER the write succeeds: set status to ``rolled_back`` and
            # write exactly one Audit_Trail entry for the transition (Req 9.2, 9.5).
            updated = self._twin.update_fix_status(
                tenant_id, fix.id, FixStatus.ROLLED_BACK
            )
            self._append_audit(
                tenant_id,
                fix_id=fix.id,
                actor=actor,
                rationale=rationale,
                transition="applied->rolled_back",
                before_value=before_value,
            )
            self._log_decision(
                outcome="rolled_back",
                fix_id=fix.id,
                actor=actor,
                rationale=rationale,
            )
            return updated

    def _find_applied_before_value(
        self, tenant_id: str, fix_id: str
    ) -> str | None:
        """Return the audited BEFORE value captured when ``fix_id`` was applied.

        The auto-applicable approval path persists the freshly-read BEFORE value
        on the ``pending->applied`` Audit_Trail entry (Req 8.4). To roll back we
        recover that value from the tenant's Audit_Trail, which
        :meth:`~core.interfaces.DigitalTwinPort.list_audit_entries` returns
        most-recent first, so the first matching applied-transition entry for this
        fix carries the value to restore. Returns ``None`` when no such entry
        exists or when it recorded no ``before_value`` (both treated as a missing
        audited before-value, Req 9.7). An empty-string BEFORE value (e.g. media
        that originally had no alt text) is a valid value to restore and is
        returned as-is.
        """
        for entry in self._twin.list_audit_entries(tenant_id):
            if entry.fix_id == fix_id and entry.transition == "pending->applied":
                return entry.before_value
        return None

    def _write_target_value(self, fix: SuggestedFix, value: str) -> None:
        """Write ``value`` to the fix's live target via the Publishing_Adapter.

        The write target is selected by the fix's ``fix_type`` and ``target_ref``:
        media ``alt_text`` for an alt-text fix, page ``content`` for a page fix.
        Used by the rollback path to restore the audited BEFORE value (Req 9.2).
        """
        target = fix.target_ref
        if fix.fix_type is FixType.UPDATE_ALT_TEXT:
            if target is None or target.media_id is None:
                raise GovernanceError(
                    f"Alt-text fix {fix.id!r} has no media target to write."
                )
            self._pa.update_media_alt_text(target.media_id, value)
        elif fix.fix_type is FixType.UPDATE_PAGE_CONTENT:
            if target is None or target.page_id is None:
                raise GovernanceError(
                    f"Content fix {fix.id!r} has no page target to write."
                )
            self._pa.update_page_content(target.page_id, value)
        else:
            raise GovernanceError(
                f"Fix {fix.id!r} has no writable fix_type."
            )
