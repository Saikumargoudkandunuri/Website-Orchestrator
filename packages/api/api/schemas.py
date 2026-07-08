"""API_Surface request/response schemas.

Pydantic models for the HTTP boundary. The response summary is the Core_Package
:class:`~core.types.CrawlSummary`, reused directly so the API never duplicates a
shared record (Req 12.5).

:class:`CrawlRequest` validates the ``POST /crawl`` body at the boundary so a
missing/blank start URL or a non-positive page count is rejected *before* any
subsystem runs, with no crawl and no persistence (Req 10.11). FastAPI surfaces a
failed validation as an automatic ``422 Unprocessable Entity`` invalid-input
response.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

__all__ = ["CrawlRequest", "DecisionRequest"]


class CrawlRequest(BaseModel):
    """The ``POST /crawl`` request body (Req 10.1, 10.11).

    ``start_url`` must be a non-blank string and ``max_pages`` a positive
    integer. These boundary constraints reject invalid input before the handler
    delegates to any subsystem (Req 10.11); the Crawler additionally validates
    that ``start_url`` is a well-formed http/https URL and that ``max_pages`` is
    within its supported range, raising before retrieving anything.
    """

    start_url: str = Field(
        ...,
        min_length=1,
        description="The URL to begin crawling from (must be non-blank).",
    )
    max_pages: int = Field(
        ...,
        gt=0,
        description="The maximum number of pages to retrieve (must be positive).",
    )

    @field_validator("start_url")
    @classmethod
    def _start_url_not_blank(cls, value: str) -> str:
        """Reject a whitespace-only start URL (Req 10.11)."""
        if not value or not value.strip():
            raise ValueError("start_url must be a non-blank URL")
        return value


class DecisionRequest(BaseModel):
    """The body for a governance decision — ``approve``/``reject``/``rollback``.

    Every governance decision records the acting ``actor`` and the ``rationale``
    in the Audit_Trail (Req 9.3, 9.4), and both fields must be non-empty
    (Req 8.11). These boundary constraints reject a missing or blank actor or
    rationale before the handler delegates to the Governance_Layer; FastAPI
    surfaces a failed validation as an automatic ``422 Unprocessable Entity``.
    The Governance_Layer additionally validates the same constraints, so a
    decision that somehow reaches it with an empty actor/rationale still fails
    closed as an :class:`~core.exceptions.InvalidDecisionError`.
    """

    actor: str = Field(
        ...,
        min_length=1,
        description="The identity responsible for the decision (non-blank).",
    )
    rationale: str = Field(
        ...,
        min_length=1,
        description="The human-readable reason for the decision (non-blank).",
    )

    @field_validator("actor", "rationale")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        """Reject a whitespace-only actor or rationale (Req 8.11)."""
        if not value or not value.strip():
            raise ValueError("must be a non-blank value")
        return value
