"""Core_Package typed records — the shared data contracts every subsystem
exchanges (Req 12.1, 12.5, 15.1).

These Pydantic v2 models are the canonical inter-subsystem records named in the
Glossary: ``CrawledPage``, ``LinkStatus``, ``RedirectChain``, ``ImageRef``,
``IssueCandidate``, ``Issue``, ``SuggestedFix``, ``AuditEntry``, and
``CrawlSummary``, together with the enums (``IssueType``, ``Severity``,
``FixType``, ``FixStatus``) and the small helper models (``IssueDetail``,
``TargetRef``) they rely on.

Per Requirement 15, this module imports nothing internal to the orchestrator
beyond (optionally) ``core.constants``; all subsystems consume these types from
here rather than duplicating them locally (Req 12.5).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

__all__ = [
    "IssueType",
    "Severity",
    "FixType",
    "FixStatus",
    "RedirectChain",
    "LinkStatus",
    "ImageRef",
    "IssueDetail",
    "TargetRef",
    "CrawledPage",
    "IssueCandidate",
    "Issue",
    "SuggestedFix",
    "AltTextGenerationInput",
    "AltTextGenerationOutput",
    "AuditEntry",
    "CrawlSummary",
]


# --- Enumerations -------------------------------------------------------------


class IssueType(str, Enum):
    """The deterministic check types the Check_Engine can emit (Req 4.2)."""

    MISSING_TITLE = "missing_title"
    MISSING_META_DESCRIPTION = "missing_meta_description"
    THIN_CONTENT = "thin_content"
    MISSING_ALT_TEXT = "missing_alt_text"
    BROKEN_LINKS = "broken_links"
    REDIRECT_CHAINS = "redirect_chains"
    MISSING_SCHEMA = "missing_schema"
    DUPLICATE_TITLE = "duplicate_title"


class Severity(str, Enum):
    """Severity levels an IssueCandidate may carry (Req 4.8)."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FixType(str, Enum):
    """The write operations a SuggestedFix may target.

    Milestone 0 writes only media ``alt_text`` and page/post ``content``; no
    other field is writable (Req 6.2).
    """

    UPDATE_ALT_TEXT = "update_alt_text"
    UPDATE_PAGE_CONTENT = "update_page_content"


class FixStatus(str, Enum):
    """The governance state-machine states for a SuggestedFix (Req 8, Req 9)."""

    PENDING = "pending"
    APPROVED = "approved"
    APPLIED = "applied"
    REJECTED = "rejected"
    ROLLED_BACK = "rolled_back"


# --- Crawler records ----------------------------------------------------------


class RedirectChain(BaseModel):
    """The ordered sequence of URLs traversed by HTTP redirects (Req 2.1, 2.2)."""

    hops: list[str] = Field(default_factory=list)  # ordered URLs traversed
    truncated: bool = False  # True if stopped at the hard cap


class LinkStatus(BaseModel):
    """The observed status of a single link (Req 2.3, 2.4)."""

    url: str
    status_code: int | None = None  # None when unreachable
    reachable: bool


class ImageRef(BaseModel):
    """A reference to an image found on a page (Req 5.3, 5.5)."""

    media_id: int | None = None  # WordPress media id, when resolvable
    filename: str  # image filename (used to derive heuristic alt text)
    alt_text: str | None = None  # existing alt text, if any


class CrawledPage(BaseModel):
    """A record produced by the Crawler for a single retrieved URL (Req 1.1)."""

    url: str
    final_url: str
    status_code: int
    title: str | None = None
    meta_description: str | None = None
    word_count: int = 0
    html: str = ""
    links: list[LinkStatus] = Field(default_factory=list)
    images: list[ImageRef] = Field(default_factory=list)
    redirect_chain: RedirectChain = Field(default_factory=RedirectChain)
    has_schema: bool = False
    crawled_at: datetime  # UTC


# --- Check_Engine records -----------------------------------------------------


class IssueDetail(BaseModel):
    """Locates an issue on a page: the page URL plus the triggering element or
    location (Req 4.8)."""

    page_url: str
    element: str | None = None  # triggering element or location


class IssueCandidate(BaseModel):
    """A structured issue emitted by the Check_Engine (Req 4.8, 4.9)."""

    issue_type: IssueType
    severity: Severity  # critical | high | medium | low
    description: str = Field(min_length=1)  # non-empty, human-readable
    detail: IssueDetail  # page URL + triggering element/location


class Issue(IssueCandidate):
    """A persisted IssueCandidate stored in the Digital_Twin, which may be
    marked ignored (Req 4.11)."""

    id: str
    tenant_id: str
    ignored: bool = False


# --- Fix_Generator / Governance records ---------------------------------------


class TargetRef(BaseModel):
    """Identifies the live resource a fix writes to (Req 5.3)."""

    media_id: int | None = None
    page_id: int | None = None


class SuggestedFix(BaseModel):
    """A persisted record proposing a change to resolve an Issue (Req 5.1).

    Milestone 1 note — generation provenance
    ----------------------------------------
    ``generation_model`` and ``generation_confidence`` record *how* a fix's
    ``proposed_value`` was produced when it came from the AI generation layer
    (the :class:`~core.interfaces.AltTextGenerationService`): the model/version
    that produced it and the model's self-reported confidence (``0.0``-``1.0``),
    when available. They are ``None`` for fixes produced by the deterministic
    filename heuristic or for report-only fixes, so existing Milestone 0 records
    remain valid. These fields carry provenance only; they never grant an
    unattended-publish path — every fix still requires Governance approval.
    """

    id: str
    tenant_id: str
    issue_id: str
    fix_type: FixType | None = None
    auto_applicable: int  # 0 or 1
    target_ref: TargetRef | None = None  # media_id/page_id for the write
    proposed_value: str | None = None  # e.g. alt text
    reason: str | None = None  # human-readable, for report-only
    status: FixStatus = FixStatus.PENDING
    generation_model: str | None = None  # AI model/version, when AI-generated
    generation_confidence: float | None = None  # 0.0-1.0, when the model reports it


# --- AI generation records ----------------------------------------------------


class AltTextGenerationInput(BaseModel):
    """The context handed to the AI alt-text generation layer for one image.

    Carries everything the :class:`~core.interfaces.AltTextGenerationService`
    needs to propose accessible alt text: the page the image sits on
    (``page_url`` and optional ``page_title``), any ``surrounding_text`` the
    crawler captured near the image, the ``image_url`` itself, and the image's
    ``existing_alt_text`` (``None``/empty when missing). The service must remain
    functional with degraded context — any of the optional fields may be
    ``None`` when the crawler could not extract them.
    """

    page_url: str
    page_title: str | None = None
    surrounding_text: str | None = None
    image_url: str
    existing_alt_text: str | None = None
    #: Optional hard character budget the caller wants the alt text to fit
    #: within (accessibility guidance is ~125 chars). The service treats it as a
    #: strong instruction; the Fix_Generator still enforces the limit as a
    #: business rule and can retry with a tighter budget.
    max_length: int | None = None


class AltTextGenerationOutput(BaseModel):
    """The result the AI alt-text generation layer returns for one image.

    ``alt_text`` is the proposed accessible description, ``model`` names the
    model/version that produced it (for provenance and auditing), and
    ``confidence`` is the model's self-reported confidence in ``[0.0, 1.0]`` when
    it provides one (``None`` otherwise). Validation of length and emptiness is
    the Fix_Generator's responsibility (Req 5.4-style business rules), not this
    record's.
    """

    alt_text: str
    model: str
    confidence: float | None = None


class AuditEntry(BaseModel):
    """A single ordered entry in the Audit_Trail (Req 9.3, 9.4)."""

    id: str
    tenant_id: str
    fix_id: str
    actor: str = Field(min_length=1)  # non-empty; human in M0
    rationale: str = Field(min_length=1)  # non-empty
    transition: str  # e.g. "pending->approved"
    before_value: str | None = None  # freshly-read live value for auto-applicable
    created_at: datetime  # UTC, ordering key


# --- API_Surface summary ------------------------------------------------------


class CrawlSummary(BaseModel):
    """The summary returned by ``POST /crawl`` (Req 10.1).

    Reports the number of pages crawled, the count of issues grouped by issue
    type, and the counts of Auto_Applicable_Fix versus Report_Only_Fix records.
    """

    pages_crawled: int = 0
    issues_by_type: dict[IssueType, int] = Field(default_factory=dict)
    auto_applicable_count: int = 0
    report_only_count: int = 0
