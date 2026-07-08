"""Core_Package interfaces — the published, typed contracts (Protocols) every
subsystem exposes to the rest of the orchestrator (Req 12.1, 12.2, 15.1).

Each subsystem named in the Glossary publishes exactly one ``typing.Protocol``
here. A Protocol specifies the typed input parameters and the typed return value
of every operation the subsystem exposes to other subsystems, so callers depend
on these contracts rather than on any subsystem's internal implementation
modules (Req 12.2). Handled failures surface either as ``Core_Package``-derived
exceptions or as :mod:`core.results` result objects, never as bare exceptions or
untyped structures (Req 12.1).

All shared records are imported from :mod:`core.types` and all result/read
outcomes from :mod:`core.results`; per Requirement 15 this module imports
nothing internal to the orchestrator beyond ``Core_Package`` itself.

WordPress-specific transfer records
-----------------------------------
``WPPage`` and ``WPMedia`` are the two typed records the ``Publishing_Adapter``
returns from the live WordPress REST API. They are WordPress-shaped rather than
general orchestrator records, and the ``PublishingAdapterPort`` is their only
consumer, so they are defined here alongside that Port (kept as typed Pydantic
models) rather than in :mod:`core.types`, which is reserved for the
inter-subsystem records named in the Glossary.

Page-read outcome
-----------------
``DigitalTwinPort.get_page`` returns a freshness-aware read outcome. The read's
success payload is the stored page — modelled as :class:`~core.types.CrawledPage`
(the canonical page record, which carries the ``crawled_at`` timestamp reads are
judged against) — so the return type is ``ReadResult[CrawledPage]``: an
:class:`~core.results.Ok` hit, a :class:`~core.results.NotFound` miss, or a
:class:`~core.results.Stale` hit (Req 3.4-3.6).
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from core.exceptions import GenerationError
from core.results import ReadResult, Result
from core.types import (
    AltTextGenerationInput,
    AltTextGenerationOutput,
    AuditEntry,
    CrawledPage,
    FixStatus,
    Issue,
    IssueCandidate,
    LinkStatus,
    SuggestedFix,
)

__all__ = [
    "WPPage",
    "WPMedia",
    "CrawlerPort",
    "DigitalTwinPort",
    "CheckEnginePort",
    "FixGeneratorPort",
    "LLMClient",
    "AltTextGenerationService",
    "PublishingAdapterPort",
    "GovernancePort",
]


# --- WordPress transfer records ----------------------------------------------


class WPPage(BaseModel):
    """A WordPress page/post as returned by the Publishing_Adapter.

    Milestone 0 reads and writes only the ``content`` field; ``id`` identifies
    the live resource for subsequent writes (Req 6.2).
    """

    id: int
    content: str
    title: str | None = None
    link: str | None = None


class WPMedia(BaseModel):
    """A WordPress media item as returned by the Publishing_Adapter.

    Milestone 0 reads and writes only ``alt_text``; ``id`` identifies the live
    media resource for subsequent writes (Req 6.2).
    """

    id: int
    alt_text: str
    source_url: str | None = None


# --- Subsystem Ports ----------------------------------------------------------


@runtime_checkable
class CrawlerPort(Protocol):
    """The Crawler contract: retrieve pages and probe individual links."""

    def crawl_site(self, start_url: str, max_pages: int) -> list[CrawledPage]:
        """Crawl from ``start_url`` within the same registrable domain, up to
        ``max_pages`` pages, returning one :class:`CrawledPage` per retrieved
        URL (Req 1.1-1.4)."""
        ...

    def check_link_status(self, url: str) -> LinkStatus:
        """Return the observed :class:`LinkStatus` for ``url``; a timeout or
        network failure yields an unreachable status without raising
        (Req 2.3, 2.4)."""
        ...


@runtime_checkable
class DigitalTwinPort(Protocol):
    """The Digital_Twin contract: persist and read crawl state, issues, fixes."""

    def upsert_pages(self, tenant_id: str, pages: list[CrawledPage]) -> None:
        """Insert or update the given ``pages`` for ``tenant_id`` (Req 3.1)."""
        ...

    def get_page(
        self, tenant_id: str, url: str, now: datetime
    ) -> ReadResult[CrawledPage]:
        """Read the stored page for ``url``, judged against ``now`` for
        freshness: :class:`~core.results.Ok` when fresh,
        :class:`~core.results.Stale` when too old to act on, or
        :class:`~core.results.NotFound` when absent (Req 3.4-3.6)."""
        ...

    def persist_issues(
        self, tenant_id: str, issues: list[IssueCandidate]
    ) -> list[Issue]:
        """Persist ``issues`` for ``tenant_id`` and return the stored
        :class:`Issue` records (Req 3.1, 4.8)."""
        ...

    def list_active_issues(self, tenant_id: str) -> list[Issue]:
        """Return the persisted issues for ``tenant_id`` excluding those marked
        ignored (Req 4.11)."""
        ...

    def mark_issue_ignored(self, tenant_id: str, issue_id: str) -> None:
        """Mark the issue ``issue_id`` as ignored for ``tenant_id`` (Req 4.11)."""
        ...

    def persist_fixes(
        self, tenant_id: str, fixes: list[SuggestedFix]
    ) -> list[SuggestedFix]:
        """Persist ``fixes`` for ``tenant_id`` and return the stored records
        (Req 5.1)."""
        ...

    def list_pending_fixes(self, tenant_id: str) -> list[SuggestedFix]:
        """Return the ``pending`` fixes awaiting a governance decision for
        ``tenant_id`` (Req 8.1)."""
        ...

    def list_fixes(self, tenant_id: str) -> list[SuggestedFix]:
        """Return **all** persisted suggested fixes for ``tenant_id`` regardless
        of status. Backs ``GET /fixes`` (Req 10.3)."""
        ...

    def get_fix(self, tenant_id: str, fix_id: str) -> SuggestedFix | None:
        """Return the stored :class:`SuggestedFix` ``fix_id`` for ``tenant_id``,
        or ``None`` when no such fix exists. Used by the Governance_Layer to
        look up the fix targeted by a decision (Req 8.9)."""
        ...

    def update_fix_status(
        self, tenant_id: str, fix_id: str, status: FixStatus
    ) -> SuggestedFix:
        """Set the ``status`` of the stored fix ``fix_id`` and return the updated
        record. The Governance_Layer is the only caller, since it is the sole
        path for a status transition (Req 8.2)."""
        ...

    def append_audit_entry(self, tenant_id: str, entry: AuditEntry) -> AuditEntry:
        """Append one :class:`AuditEntry` to the Audit_Trail for ``tenant_id``
        and return the stored record (Req 9.3, 9.4)."""
        ...

    def list_audit_entries(self, tenant_id: str) -> list[AuditEntry]:
        """Return the tenant's Audit_Trail entries, most-recent first (Req 10.7)."""
        ...


@runtime_checkable
class CheckEnginePort(Protocol):
    """The Check_Engine contract: deterministic, rule-based checks (Req 4.1).

    Each check returns structured :class:`IssueCandidate` objects (or ``None``
    when no issue is found); ``run_all_checks`` aggregates them (Req 4.7-4.10).
    """

    def check_missing_title(self, page: CrawledPage) -> IssueCandidate | None:
        """Flag a page with no title (Req 4.2)."""
        ...

    def check_missing_meta_description(
        self, page: CrawledPage
    ) -> IssueCandidate | None:
        """Flag a page with no meta description (Req 4.2)."""
        ...

    def check_thin_content(self, page: CrawledPage) -> IssueCandidate | None:
        """Flag a page whose word count is below the configured minimum
        (Req 4.3)."""
        ...

    def check_missing_alt_text(self, page: CrawledPage) -> list[IssueCandidate]:
        """Flag each image on the page that lacks alt text (Req 4.2, 5.3)."""
        ...

    def check_broken_links(self, page: CrawledPage) -> list[IssueCandidate]:
        """Flag each link on the page with a client/server error status
        (Req 4.5)."""
        ...

    def check_redirect_chains(self, page: CrawledPage) -> IssueCandidate | None:
        """Flag a page whose redirect chain length meets the configured
        threshold (Req 4.6)."""
        ...

    def check_missing_schema(self, page: CrawledPage) -> IssueCandidate | None:
        """Flag a page with no schema/JSON-LD markup (Req 4.2)."""
        ...

    def check_duplicate_titles(
        self, pages: list[CrawledPage]
    ) -> list[IssueCandidate]:
        """Flag pages that share an identical title with one or more others
        (Req 4.4)."""
        ...

    def run_all_checks(self, pages: list[CrawledPage]) -> list[IssueCandidate]:
        """Run every check across ``pages`` and return all emitted candidates
        (Req 4.7)."""
        ...


@runtime_checkable
class FixGeneratorPort(Protocol):
    """The Fix_Generator contract: a pure transformation from issue to fix."""

    def generate_fix(
        self, issue: Issue, page: CrawledPage
    ) -> SuggestedFix | None:
        """Return exactly one :class:`SuggestedFix` for ``issue`` given
        ``page``, or ``None`` when no fix maps to the issue; never writes to the
        database (Req 5.1, 5.2)."""
        ...


@runtime_checkable
class LLMClient(Protocol):
    """A thin, swappable boundary over whatever LLM/AI provider is configured.

    This is the single seam through which the AI generation layer reaches an
    external model, so the concrete vendor (OpenAI, a local model, a hosted
    endpoint, ...) is injectable and mockable — tests substitute an in-memory
    client and never touch the network. Implementations make **one** attempt and
    surface a transport/provider failure by raising; the
    :class:`AltTextGenerationService` wraps that into a typed
    :class:`~core.exceptions.GenerationError` so callers only ever see the
    orchestrator's typed contract.
    """

    def complete(
        self, prompt: str, *, system: str | None = None, max_output_tokens: int | None = None
    ) -> str:
        """Return the model's text completion for ``prompt``.

        ``system`` is an optional system/steering instruction and
        ``max_output_tokens`` an optional generation cap. Raises on a
        provider/transport failure rather than returning a sentinel.
        """
        ...


@runtime_checkable
class AltTextGenerationService(Protocol):
    """The AI alt-text generation contract (Milestone 1).

    Given the page/image context in an :class:`~core.types.AltTextGenerationInput`,
    proposes accessible alt text as an :class:`~core.types.AltTextGenerationOutput`.
    The operation represents success *or a typed failure*, so it returns a
    :class:`~core.results.Result` (Req 15.5): an :class:`~core.results.Ok`
    carrying the output, or an :class:`~core.results.Err` carrying a
    :class:`~core.exceptions.GenerationError` when the model is unavailable,
    times out, or returns nothing usable. It never raises for a handled
    generation failure, so the Fix_Generator can degrade gracefully to a
    report-only fix instead of crashing the crawl workflow.
    """

    def generate_alt_text(
        self, request: AltTextGenerationInput
    ) -> Result[AltTextGenerationOutput, GenerationError]:
        """Propose alt text for the image described by ``request``.

        Returns :class:`~core.results.Ok` with the proposed
        :class:`~core.types.AltTextGenerationOutput`, or
        :class:`~core.results.Err` with a
        :class:`~core.exceptions.GenerationError` on a handled failure.
        """
        ...


@runtime_checkable
class PublishingAdapterPort(Protocol):
    """The Publishing_Adapter contract: the only writer to the live site.

    Reads pages and media and writes only page/post ``content`` and media
    ``alt_text`` (Req 6.1, 6.2).
    """

    def list_pages(self) -> list[WPPage]:
        """Return the live WordPress pages/posts (Req 6.1)."""
        ...

    def get_page(self, page_id: int) -> WPPage:
        """Return the live page/post identified by ``page_id`` (Req 6.1)."""
        ...

    def update_page_content(self, page_id: int, content: str) -> WPPage:
        """Write ``content`` to the page/post ``page_id`` and return the updated
        record (Req 6.2)."""
        ...

    def get_media(self, media_id: int) -> WPMedia:
        """Return the live media item identified by ``media_id`` (Req 6.1)."""
        ...

    def update_media_alt_text(self, media_id: int, alt_text: str) -> WPMedia:
        """Write ``alt_text`` to the media ``media_id`` and return the updated
        record (Req 6.2)."""
        ...


@runtime_checkable
class GovernancePort(Protocol):
    """The Governance_Layer contract: the only path for a fix status transition
    (Req 8.2). Every operation records the acting ``actor`` and ``rationale`` in
    the Audit_Trail (Req 9.3)."""

    def list_pending_fixes(self, tenant_id: str) -> list[SuggestedFix]:
        """Return the pending fixes awaiting a decision for ``tenant_id``
        (Req 8.1)."""
        ...

    def approve_fix(
        self, tenant_id: str, fix_id: str, actor: str, rationale: str
    ) -> SuggestedFix:
        """Approve the fix ``fix_id`` on behalf of ``actor`` with ``rationale``,
        returning the updated record (Req 8.3-8.5)."""
        ...

    def reject_fix(
        self, tenant_id: str, fix_id: str, actor: str, rationale: str
    ) -> SuggestedFix:
        """Reject the fix ``fix_id`` on behalf of ``actor`` with ``rationale``,
        returning the updated record (Req 8.7)."""
        ...

    def rollback_fix(
        self, tenant_id: str, fix_id: str, actor: str, rationale: str
    ) -> SuggestedFix:
        """Roll back the applied fix ``fix_id`` on behalf of ``actor`` with
        ``rationale``, restoring the audited before-value, and return the
        updated record (Req 9.1, 9.2)."""
        ...
