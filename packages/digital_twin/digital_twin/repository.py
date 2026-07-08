"""Digital_Twin repository — the concrete :class:`core.interfaces.DigitalTwinPort`.

This module implements the persistence operations the rest of the orchestrator
depends on through the ``DigitalTwinPort`` contract (Req 12.2): upserting crawled
pages, freshness-aware page reads, and persisting/reading issues, fixes, and the
Audit_Trail. It maps between the Core_Package transfer records
(:mod:`core.types`) and the SQLAlchemy ORM rows (:mod:`digital_twin.models`).

Multi-tenancy invariants (Req 14.4-14.6)
----------------------------------------
Every row written carries a non-null ``tenant_id``. The tenant stamped on a
write is *resolved* from the call's ``tenant_id`` argument, falling back to the
tenant configured on the repository. If neither yields a usable (non-empty)
tenant, the write is rejected with :class:`~core.exceptions.DigitalTwinError`
and nothing is persisted (Req 14.5, 14.6).

Freshness (Req 3.2-3.6)
-----------------------
Each stored page carries a UTC ``crawled_at`` timestamp (Req 3.2). ``get_page``
judges a stored page against a caller-supplied ``now``: the page is served as an
:class:`~core.results.Ok` while its age (``now - crawled_at``) is within the
configured Staleness_Threshold (Req 3.4), surfaced as
:class:`~core.results.Stale` once its age exceeds the threshold (Req 3.5), and
reported as :class:`~core.results.NotFound` when it is not stored at all
(Req 3.6). The threshold is configurable via the constructor.

Schema note
-----------
The Milestone 0 relational schema stores page-level fields, links, and the meta
description; it does not persist a page's raw HTML, image references, or
per-page redirect chain. Reads therefore reconstruct
:class:`~core.types.CrawledPage` with those unstored fields at their defaults
while preserving the persisted fields exactly — critically the ``crawled_at``
timestamp (Req 3.3).

A fix's ``target_ref`` (the live media/page id it writes to) *is* persisted, on
the ``suggested_fixes.target_media_id`` / ``target_page_id`` columns, and
reconstructed on read (Req 5.3). Persisting it is required so that a fix reloaded
from the repo still identifies its live write target, which the Governance_Layer
needs to apply and roll back an auto-applicable fix end-to-end (Req 11.5-11.8).
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Iterator

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from core.exceptions import DigitalTwinError
from core.results import NotFound, Ok, ReadResult, Stale
from core.types import (
    AuditEntry,
    CrawledPage,
    FixStatus,
    FixType,
    Issue,
    IssueCandidate,
    IssueDetail,
    IssueType,
    LinkStatus,
    Severity,
    SuggestedFix,
    TargetRef,
)

from digital_twin.models import (
    AuditTrail,
    Issue as IssueRow,
    Link as LinkRow,
    Page as PageRow,
    PageMetadata as PageMetadataRow,
    SuggestedFix as SuggestedFixRow,
)

__all__ = ["DigitalTwinRepository", "DEFAULT_STALENESS_THRESHOLD_SECONDS"]

#: Fallback Staleness_Threshold (seconds) used when neither the constructor nor
#: Core_Package configuration supplies one.
DEFAULT_STALENESS_THRESHOLD_SECONDS: int = 3600


def _new_id() -> str:
    """Return a fresh opaque identifier for a persisted row."""
    return uuid.uuid4().hex


def _target_ref_from_row(row: SuggestedFixRow) -> TargetRef | None:
    """Reconstruct a fix's :class:`TargetRef` from its persisted target columns.

    Returns ``None`` when neither ``target_media_id`` nor ``target_page_id`` is
    set (a report-only fix has no write target), otherwise a ``TargetRef``
    carrying whichever id(s) were persisted (Req 5.3, 11.5-11.8).
    """
    if row.target_media_id is None and row.target_page_id is None:
        return None
    return TargetRef(media_id=row.target_media_id, page_id=row.target_page_id)


def _to_utc(value: datetime) -> datetime:
    """Return ``value`` as a timezone-aware UTC :class:`datetime`.

    A naive datetime is assumed to already be UTC (SQLite does not retain a
    timezone, so values read back are naive UTC); an aware datetime is converted
    to UTC. This keeps every timestamp comparable and preserves the stored
    instant across a persistence round-trip (Req 3.2, 3.3).
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class DigitalTwinRepository:
    """A :class:`core.interfaces.DigitalTwinPort` backed by SQLAlchemy.

    The repository is constructed with either an active
    :class:`sqlalchemy.orm.Session` (used directly; the caller owns its
    lifecycle) or a session factory (a :class:`sqlalchemy.orm.sessionmaker` or
    any zero-argument callable returning a ``Session``), in which case a fresh
    session is opened, committed, and closed per operation.

    Parameters
    ----------
    session_source:
        An active ``Session`` or a callable/``sessionmaker`` producing one.
    tenant_id:
        Optional configured Tenant_Id used to stamp rows when a call does not
        supply one (Req 14.5).
    staleness_threshold:
        Optional Staleness_Threshold as a :class:`datetime.timedelta` or a
        number of seconds. Falls back to Core_Package configuration and then to
        :data:`DEFAULT_STALENESS_THRESHOLD_SECONDS`.
    """

    def __init__(
        self,
        session_source: Session | sessionmaker[Session] | object,
        *,
        tenant_id: str | None = None,
        staleness_threshold: timedelta | float | int | None = None,
    ) -> None:
        self._session_source = session_source
        self._configured_tenant = tenant_id
        self._staleness_threshold = self._coerce_threshold(staleness_threshold)

    # --- Construction helpers -------------------------------------------------

    @staticmethod
    def _coerce_threshold(
        value: timedelta | float | int | None,
    ) -> timedelta:
        """Normalize the configured Staleness_Threshold to a ``timedelta``."""
        if isinstance(value, timedelta):
            return value
        if value is not None:
            return timedelta(seconds=float(value))

        # No explicit threshold: prefer validated Core_Package settings, but
        # never let an unrelated missing secret block persistence — fall back to
        # the canonical default when settings cannot be loaded.
        try:  # pragma: no cover - exercised indirectly
            from core.config import get_settings

            return timedelta(seconds=get_settings().staleness_threshold)
        except Exception:  # noqa: BLE001 - configuration is optional here
            return timedelta(seconds=DEFAULT_STALENESS_THRESHOLD_SECONDS)

    @property
    def staleness_threshold(self) -> timedelta:
        """The configured Staleness_Threshold as a :class:`timedelta`."""
        return self._staleness_threshold

    # --- Session / tenant plumbing -------------------------------------------

    @contextmanager
    def _session(self) -> Iterator[Session]:
        """Yield a working :class:`Session`, committing on success.

        When constructed with an active session the caller owns its lifecycle,
        so the session is neither created nor closed here (but is still
        committed/rolled back). When constructed with a factory a fresh session
        is created and closed around the operation.
        """
        external = isinstance(self._session_source, Session)
        session: Session = (
            self._session_source  # type: ignore[assignment]
            if external
            else self._session_source()  # type: ignore[operator]
        )
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            if not external:
                session.close()

    def _resolve_tenant(self, tenant_id: str | None) -> str:
        """Return the tenant to stamp, or reject when none is resolvable.

        The call's ``tenant_id`` takes precedence, falling back to the tenant
        configured on the repository. A record that cannot be attributed to any
        tenant is rejected so no row is ever persisted without a ``tenant_id``
        (Req 14.5, 14.6).
        """
        for candidate in (tenant_id, self._configured_tenant):
            if candidate is None:
                continue
            resolved = str(candidate).strip()
            if resolved:
                return resolved
        raise DigitalTwinError(
            "Cannot resolve a tenant_id for the write: no tenant was provided "
            "and none is configured; refusing to persist a record without a "
            "tenant (Req 14.6)."
        )

    # --- Mapping helpers ------------------------------------------------------

    def _page_to_record(self, page: PageRow) -> CrawledPage:
        """Reconstruct a :class:`CrawledPage` from a persisted ``Page`` row.

        Persisted fields (including ``crawled_at``) are preserved exactly;
        fields the M0 schema does not store (raw HTML, images, per-page redirect
        chain) take their record defaults.
        """
        links = [
            LinkStatus(
                url=link.href,
                status_code=link.status_code,
                reachable=link.reachable,
            )
            for link in page.links
        ]
        meta_description = (
            page.page_metadata[0].meta_description if page.page_metadata else None
        )
        return CrawledPage(
            url=page.url,
            final_url=page.final_url or page.url,
            status_code=page.status_code if page.status_code is not None else 0,
            title=page.title,
            meta_description=meta_description,
            word_count=page.word_count,
            has_schema=page.has_schema,
            links=links,
            crawled_at=_to_utc(page.crawled_at),
        )

    def _apply_page(self, page: PageRow, source: CrawledPage, tenant: str) -> None:
        """Copy ``source`` onto ``page``, stamping ``tenant`` (Req 3.2, 14.5)."""
        page.tenant_id = tenant
        page.url = source.url
        page.final_url = source.final_url
        page.status_code = source.status_code
        page.title = source.title
        page.word_count = source.word_count
        page.has_schema = source.has_schema
        page.crawled_at = _to_utc(source.crawled_at)

        # Reassigning the collections lets delete-orphan clear any prior rows on
        # an update so the persisted links/metadata always mirror the source.
        page.links = [
            LinkRow(
                id=_new_id(),
                tenant_id=tenant,
                href=link.url,
                status_code=link.status_code,
                reachable=link.reachable,
            )
            for link in source.links
        ]
        page.page_metadata = (
            [
                PageMetadataRow(
                    id=_new_id(),
                    tenant_id=tenant,
                    meta_description=source.meta_description,
                )
            ]
            if source.meta_description is not None
            else []
        )

    # --- DigitalTwinPort: pages ----------------------------------------------

    def upsert_pages(self, tenant_id: str, pages: list[CrawledPage]) -> None:
        """Insert or update ``pages`` for ``tenant_id`` (Req 3.1, 3.2).

        Each page is matched on ``(tenant_id, url)``: an existing row is updated
        in place (its links and metadata replaced), otherwise a new row is
        created. Every written row is stamped with the resolved tenant; if no
        tenant is resolvable the whole operation is rejected before any write
        (Req 14.5, 14.6).
        """
        tenant = self._resolve_tenant(tenant_id)
        if not pages:
            return
        with self._session() as session:
            for source in pages:
                existing = session.execute(
                    select(PageRow).where(
                        PageRow.tenant_id == tenant,
                        PageRow.url == source.url,
                    )
                ).scalar_one_or_none()
                if existing is None:
                    existing = PageRow(id=_new_id())
                    session.add(existing)
                self._apply_page(existing, source, tenant)

    def get_page(
        self, tenant_id: str, url: str, now: datetime
    ) -> ReadResult[CrawledPage]:
        """Read the stored page for ``url``, judged for freshness against ``now``.

        Returns :class:`~core.results.NotFound` when the page is absent
        (Req 3.6); :class:`~core.results.Ok` carrying the reconstructed
        :class:`CrawledPage` (including ``crawled_at``) while its age is within
        the Staleness_Threshold (Req 3.3, 3.4); and
        :class:`~core.results.Stale` once its age exceeds the threshold
        (Req 3.5).
        """
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            page = session.execute(
                select(PageRow).where(
                    PageRow.tenant_id == tenant,
                    PageRow.url == url,
                )
            ).scalar_one_or_none()
            if page is None:
                return NotFound(key=url)

            crawled_at = _to_utc(page.crawled_at)
            age = _to_utc(now) - crawled_at
            if age > self._staleness_threshold:
                return Stale(
                    key=url,
                    crawled_at=crawled_at,
                    age_seconds=age.total_seconds(),
                    threshold_seconds=self._staleness_threshold.total_seconds(),
                )
            return Ok(self._page_to_record(page))

    # --- DigitalTwinPort: issues ---------------------------------------------

    def persist_issues(
        self, tenant_id: str, issues: list[IssueCandidate]
    ) -> list[Issue]:
        """Persist ``issues`` as :class:`Issue` rows and return the stored records.

        Each candidate is linked to its page via ``detail.page_url``; an issue
        whose page is not persisted for the tenant is rejected. Every row is
        stamped with the resolved tenant (Req 14.5).
        """
        tenant = self._resolve_tenant(tenant_id)
        if not issues:
            return []
        stored: list[Issue] = []
        with self._session() as session:
            for candidate in issues:
                page_url = candidate.detail.page_url
                page = session.execute(
                    select(PageRow).where(
                        PageRow.tenant_id == tenant,
                        PageRow.url == page_url,
                    )
                ).scalar_one_or_none()
                if page is None:
                    raise DigitalTwinError(
                        "Cannot persist an issue for a page that is not stored "
                        f"for this tenant: {page_url!r}."
                    )
                issue_id = _new_id()
                session.add(
                    IssueRow(
                        id=issue_id,
                        tenant_id=tenant,
                        page_id=page.id,
                        issue_type=candidate.issue_type.value,
                        severity=candidate.severity.value,
                        description=candidate.description,
                        ignored=False,
                    )
                )
                stored.append(
                    Issue(
                        id=issue_id,
                        tenant_id=tenant,
                        ignored=False,
                        issue_type=candidate.issue_type,
                        severity=candidate.severity,
                        description=candidate.description,
                        detail=candidate.detail,
                    )
                )
        return stored

    def list_active_issues(self, tenant_id: str) -> list[Issue]:
        """Return the tenant's persisted issues excluding ignored ones (Req 4.11)."""
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            rows = (
                session.execute(
                    select(IssueRow).where(
                        IssueRow.tenant_id == tenant,
                        IssueRow.ignored.is_(False),
                    )
                )
                .scalars()
                .all()
            )
            return [
                Issue(
                    id=row.id,
                    tenant_id=row.tenant_id,
                    ignored=row.ignored,
                    issue_type=IssueType(row.issue_type),
                    severity=Severity(row.severity),
                    description=row.description,
                    detail=IssueDetail(page_url=row.page.url),
                )
                for row in rows
            ]

    def mark_issue_ignored(self, tenant_id: str, issue_id: str) -> None:
        """Mark issue ``issue_id`` ignored so it drops out of active reporting
        (Req 4.11)."""
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            row = session.execute(
                select(IssueRow).where(
                    IssueRow.tenant_id == tenant,
                    IssueRow.id == issue_id,
                )
            ).scalar_one_or_none()
            if row is None:
                raise DigitalTwinError(
                    f"Cannot ignore unknown issue {issue_id!r} for this tenant."
                )
            row.ignored = True

    # --- DigitalTwinPort: fixes ----------------------------------------------

    def persist_fixes(
        self, tenant_id: str, fixes: list[SuggestedFix]
    ) -> list[SuggestedFix]:
        """Persist ``fixes`` and return the stored records with the tenant stamped
        (Req 5.1, 14.5)."""
        tenant = self._resolve_tenant(tenant_id)
        if not fixes:
            return []
        stored: list[SuggestedFix] = []
        with self._session() as session:
            for fix in fixes:
                target = fix.target_ref
                session.add(
                    SuggestedFixRow(
                        id=fix.id,
                        tenant_id=tenant,
                        issue_id=fix.issue_id,
                        fix_type=fix.fix_type.value if fix.fix_type else None,
                        auto_applicable=fix.auto_applicable,
                        target_media_id=target.media_id if target else None,
                        target_page_id=target.page_id if target else None,
                        proposed_value=fix.proposed_value,
                        reason=fix.reason,
                        status=fix.status.value,
                        generation_model=fix.generation_model,
                        generation_confidence=fix.generation_confidence,
                    )
                )
                stored.append(fix.model_copy(update={"tenant_id": tenant}))
        return stored

    def _fix_to_record(self, row: SuggestedFixRow) -> SuggestedFix:
        """Reconstruct a :class:`SuggestedFix` from a persisted row.

        The fix's ``target_ref`` (the media/page id it writes to) is persisted on
        the row (``target_media_id`` / ``target_page_id``) and reconstructed here,
        so a fix reloaded from the repo still carries its live write target — the
        Governance_Layer needs it to apply and roll back an auto-applicable fix
        (Req 5.3, 11.5-11.8). A row with neither id set reconstructs a ``None``
        target (a report-only fix has no write target).
        """
        return SuggestedFix(
            id=row.id,
            tenant_id=row.tenant_id,
            issue_id=row.issue_id,
            fix_type=FixType(row.fix_type) if row.fix_type else None,
            auto_applicable=row.auto_applicable,
            target_ref=_target_ref_from_row(row),
            proposed_value=row.proposed_value,
            reason=row.reason,
            status=FixStatus(row.status),
            generation_model=row.generation_model,
            generation_confidence=row.generation_confidence,
        )

    def get_fix(self, tenant_id: str, fix_id: str) -> SuggestedFix | None:
        """Return the stored :class:`SuggestedFix` ``fix_id`` for the tenant, or
        ``None`` when it is absent (Req 8.9)."""
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            row = session.execute(
                select(SuggestedFixRow).where(
                    SuggestedFixRow.tenant_id == tenant,
                    SuggestedFixRow.id == fix_id,
                )
            ).scalar_one_or_none()
            return self._fix_to_record(row) if row is not None else None

    def list_pending_fixes(self, tenant_id: str) -> list[SuggestedFix]:
        """Return the tenant's fixes whose status is ``pending`` (Req 8.1)."""
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            rows = (
                session.execute(
                    select(SuggestedFixRow).where(
                        SuggestedFixRow.tenant_id == tenant,
                        SuggestedFixRow.status == FixStatus.PENDING.value,
                    )
                )
                .scalars()
                .all()
            )
            return [self._fix_to_record(row) for row in rows]

    def list_fixes(self, tenant_id: str) -> list[SuggestedFix]:
        """Return **all** the tenant's persisted suggested fixes, regardless of
        status (Req 10.3)."""
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            rows = (
                session.execute(
                    select(SuggestedFixRow).where(
                        SuggestedFixRow.tenant_id == tenant,
                    )
                )
                .scalars()
                .all()
            )
            return [self._fix_to_record(row) for row in rows]

    def update_fix_status(
        self, tenant_id: str, fix_id: str, status: FixStatus
    ) -> SuggestedFix:
        """Set the ``status`` of fix ``fix_id`` and return the updated record.

        Raises :class:`~core.exceptions.DigitalTwinError` when the fix does not
        exist for the tenant, so the Governance_Layer can surface an unknown-id
        as a not-found decision (Req 8.9).
        """
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            row = session.execute(
                select(SuggestedFixRow).where(
                    SuggestedFixRow.tenant_id == tenant,
                    SuggestedFixRow.id == fix_id,
                )
            ).scalar_one_or_none()
            if row is None:
                raise DigitalTwinError(
                    f"Cannot update status of unknown fix {fix_id!r} for this "
                    "tenant."
                )
            row.status = status.value
            session.flush()
            return self._fix_to_record(row)

    # --- Audit_Trail ----------------------------------------------------------

    def append_audit_entry(
        self, tenant_id: str, entry: AuditEntry
    ) -> AuditEntry:
        """Append one entry to the Audit_Trail and return it with the tenant
        stamped (Req 9.3, 9.4, 14.5)."""
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            session.add(
                AuditTrail(
                    id=entry.id,
                    tenant_id=tenant,
                    fix_id=entry.fix_id,
                    actor=entry.actor,
                    rationale=entry.rationale,
                    transition=entry.transition,
                    before_value=entry.before_value,
                    created_at=_to_utc(entry.created_at),
                )
            )
        return entry.model_copy(update={"tenant_id": tenant})

    def list_audit_entries(self, tenant_id: str) -> list[AuditEntry]:
        """Return the tenant's Audit_Trail entries, most-recent first (Req 10.7)."""
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            rows = (
                session.execute(
                    select(AuditTrail)
                    .where(AuditTrail.tenant_id == tenant)
                    .order_by(AuditTrail.created_at.desc(), AuditTrail.id.desc())
                )
                .scalars()
                .all()
            )
            return [
                AuditEntry(
                    id=row.id,
                    tenant_id=row.tenant_id,
                    fix_id=row.fix_id,
                    actor=row.actor,
                    rationale=row.rationale,
                    transition=row.transition,
                    before_value=row.before_value,
                    created_at=_to_utc(row.created_at),
                )
                for row in rows
            ]
