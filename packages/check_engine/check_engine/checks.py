"""Check_Engine — deterministic, rule-based page-level checks (Req 4.1).

This module implements the :class:`~core.interfaces.CheckEnginePort` page-level
checks. Every check is pure and rule-based: it inspects a single
:class:`~core.types.CrawledPage` and returns structured
:class:`~core.types.IssueCandidate` objects (or ``None``/``[]`` when no issue is
found). No check invokes an LLM and no check emits free text — results are
review flags, not verdicts (Req 4.1, 4.9, 4.10).

Every emitted ``IssueCandidate`` is well-formed: its ``severity`` is one of
``critical | high | medium | low``, its ``description`` is a non-empty
human-readable string, and its ``detail`` identifies the affected page URL plus
the triggering element or location (Req 4.8).

The cross-page ``check_duplicate_titles`` check and the ``run_all_checks``
aggregator complete the :class:`~core.interfaces.CheckEnginePort` contract: the
former flags pages that share an identical title (Req 4.4) and the latter runs
every individual check across a set of pages and returns the aggregated
candidates in a deterministic order (Req 4.7).
"""

from __future__ import annotations

from core.constants import REDIRECT_CHAIN_THRESHOLD, THIN_CONTENT_MIN_WORDS
from core.types import (
    CrawledPage,
    ImageRef,
    IssueCandidate,
    IssueDetail,
    IssueType,
    Severity,
)

__all__ = ["CheckEngine"]


def _is_blank(value: str | None) -> bool:
    """Return True when ``value`` is None or contains only whitespace."""

    return value is None or value.strip() == ""


def _is_error_status(status_code: int | None) -> bool:
    """Return True when ``status_code`` is a client (4xx) or server (5xx)
    error status (Req 4.5)."""

    return status_code is not None and 400 <= status_code <= 599


def _image_label(image: ImageRef) -> str:
    """Human-readable identifier for the triggering image element."""

    if image.media_id is not None:
        return f"media_id={image.media_id} ({image.filename})"
    return f"image '{image.filename}'"


class CheckEngine:
    """Deterministic, rule-based Check_Engine (implements the page-level portion
    of :class:`~core.interfaces.CheckEnginePort`).

    Each method corresponds to exactly one check. Instances are stateless, so a
    single :class:`CheckEngine` may be shared freely across pages and threads.
    """

    # --- Single-value page checks --------------------------------------------

    def check_missing_title(self, page: CrawledPage) -> IssueCandidate | None:
        """Flag a page with no title (Req 4.2)."""

        if not _is_blank(page.title):
            return None
        return IssueCandidate(
            issue_type=IssueType.MISSING_TITLE,
            severity=Severity.HIGH,
            description="Page is missing a title.",
            detail=IssueDetail(page_url=page.url, element="<title>"),
        )

    def check_missing_meta_description(
        self, page: CrawledPage
    ) -> IssueCandidate | None:
        """Flag a page with no meta description (Req 4.2)."""

        if not _is_blank(page.meta_description):
            return None
        return IssueCandidate(
            issue_type=IssueType.MISSING_META_DESCRIPTION,
            severity=Severity.MEDIUM,
            description="Page is missing a meta description.",
            detail=IssueDetail(
                page_url=page.url, element='<meta name="description">'
            ),
        )

    def check_thin_content(self, page: CrawledPage) -> IssueCandidate | None:
        """Flag a page whose word count is below the configured minimum
        (default 300 words) (Req 4.3)."""

        if page.word_count >= THIN_CONTENT_MIN_WORDS:
            return None
        return IssueCandidate(
            issue_type=IssueType.THIN_CONTENT,
            severity=Severity.MEDIUM,
            description=(
                f"Page has thin content: {page.word_count} words is below the "
                f"minimum of {THIN_CONTENT_MIN_WORDS}."
            ),
            detail=IssueDetail(
                page_url=page.url,
                element=f"page body ({page.word_count} words)",
            ),
        )

    def check_redirect_chains(self, page: CrawledPage) -> IssueCandidate | None:
        """Flag a page whose redirect chain length meets or exceeds the
        configured threshold (default 3 hops) (Req 4.6)."""

        hop_count = len(page.redirect_chain.hops)
        if hop_count < REDIRECT_CHAIN_THRESHOLD:
            return None
        return IssueCandidate(
            issue_type=IssueType.REDIRECT_CHAINS,
            severity=Severity.MEDIUM,
            description=(
                f"Page has a redirect chain of {hop_count} hops, at or above "
                f"the threshold of {REDIRECT_CHAIN_THRESHOLD}."
            ),
            detail=IssueDetail(
                page_url=page.url,
                element=" -> ".join(page.redirect_chain.hops),
            ),
        )

    def check_missing_schema(self, page: CrawledPage) -> IssueCandidate | None:
        """Flag a page with no schema/JSON-LD markup (Req 4.2)."""

        if page.has_schema:
            return None
        return IssueCandidate(
            issue_type=IssueType.MISSING_SCHEMA,
            severity=Severity.LOW,
            description="Page has no structured-data (schema) markup.",
            detail=IssueDetail(
                page_url=page.url, element="structured-data (schema/JSON-LD)"
            ),
        )

    # --- Multi-value page checks ---------------------------------------------

    def check_missing_alt_text(
        self, page: CrawledPage
    ) -> list[IssueCandidate]:
        """Flag each image on the page that lacks alt text (Req 4.2, 5.3).

        Returns one :class:`IssueCandidate` per image whose ``alt_text`` is
        absent or blank, and an empty list when every image has alt text.
        """

        candidates: list[IssueCandidate] = []
        for image in page.images:
            if not _is_blank(image.alt_text):
                continue
            candidates.append(
                IssueCandidate(
                    issue_type=IssueType.MISSING_ALT_TEXT,
                    severity=Severity.LOW,
                    description=(
                        f"Image '{image.filename}' is missing alt text."
                    ),
                    detail=IssueDetail(
                        page_url=page.url, element=_image_label(image)
                    ),
                )
            )
        return candidates

    def check_broken_links(self, page: CrawledPage) -> list[IssueCandidate]:
        """Flag each link on the page with a client/server error status
        (Req 4.5).

        Returns one :class:`IssueCandidate` per link whose status code is in the
        4xx/5xx range, and an empty list when no link is broken.
        """

        candidates: list[IssueCandidate] = []
        for link in page.links:
            if not _is_error_status(link.status_code):
                continue
            candidates.append(
                IssueCandidate(
                    issue_type=IssueType.BROKEN_LINKS,
                    severity=Severity.HIGH,
                    description=(
                        f"Link to '{link.url}' returned error status "
                        f"{link.status_code}."
                    ),
                    detail=IssueDetail(
                        page_url=page.url,
                        element=f"{link.url} (status {link.status_code})",
                    ),
                )
            )
        return candidates

    # --- Cross-page checks ---------------------------------------------------

    def check_duplicate_titles(
        self, pages: list[CrawledPage]
    ) -> list[IssueCandidate]:
        """Flag pages that share an identical (non-blank) title (Req 4.4).

        Pages are grouped by their exact title text; every group holding two or
        more pages is a duplicate-title set. One :class:`IssueCandidate` is
        emitted per affected page (so each duplicated page carries a candidate
        locating it), and the candidates preserve the input page order for
        determinism. Pages with a blank or ``None`` title are never treated as
        duplicates.
        """

        # Group page indexes by exact title, preserving first-seen order.
        groups: dict[str, list[int]] = {}
        for index, page in enumerate(pages):
            if _is_blank(page.title):
                continue
            # page.title is non-blank here; narrow for the type checker.
            title = page.title or ""
            groups.setdefault(title, []).append(index)

        # A title is duplicated when two or more pages share it.
        duplicated_indexes = {
            index
            for indexes in groups.values()
            if len(indexes) >= 2
            for index in indexes
        }

        candidates: list[IssueCandidate] = []
        for index, page in enumerate(pages):
            if index not in duplicated_indexes:
                continue
            title = page.title or ""
            share_count = len(groups[title])
            candidates.append(
                IssueCandidate(
                    issue_type=IssueType.DUPLICATE_TITLE,
                    severity=Severity.MEDIUM,
                    description=(
                        f"Title '{title}' is shared by {share_count} pages; "
                        "titles should be unique."
                    ),
                    detail=IssueDetail(
                        page_url=page.url,
                        element=f"<title> '{title}'",
                    ),
                )
            )
        return candidates

    # --- Aggregator ----------------------------------------------------------

    def check_page(self, page: CrawledPage) -> list[IssueCandidate]:
        """Run all single-page checks for ``page`` and return its candidates.

        Excludes the cross-page :meth:`check_duplicate_titles` check, which
        requires the full page set. The result preserves the fixed per-page
        check order used everywhere in this module (Req 4.7).
        """

        candidates: list[IssueCandidate] = []
        for single_check in (
            self.check_missing_title,
            self.check_missing_meta_description,
            self.check_thin_content,
            self.check_redirect_chains,
            self.check_missing_schema,
        ):
            candidate = single_check(page)
            if candidate is not None:
                candidates.append(candidate)
        candidates.extend(self.check_missing_alt_text(page))
        candidates.extend(self.check_broken_links(page))
        return candidates

    def run_all_checks(
        self, pages: list[CrawledPage]
    ) -> list[IssueCandidate]:
        """Run every individual check across ``pages`` and return the
        aggregated candidates (Req 4.7).

        Each page runs through :meth:`check_page`, then the cross-page
        :meth:`check_duplicate_titles` runs across the whole set. The result
        ordering is fully deterministic for a given input.
        """

        candidates: list[IssueCandidate] = []
        for page in pages:
            candidates.extend(self.check_page(page))
        candidates.extend(self.check_duplicate_titles(pages))
        return candidates
