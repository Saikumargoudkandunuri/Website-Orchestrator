"""Property 19 — Ignored issues are excluded from active reporting.

Feature: website-orchestrator-milestone-0, Property 19: Ignored issues are
excluded from active reporting

Validates: Requirements 4.11

Requirement 4.11: WHEN an issue is marked ignored, THE Digital_Twin SHALL
exclude it from active reporting (``list_active_issues``) while retaining it in
storage.

This property drives
:meth:`digital_twin.repository.DigitalTwinRepository.persist_issues`, then marks
an arbitrary subset of the persisted issues ignored via
:meth:`~digital_twin.repository.DigitalTwinRepository.mark_issue_ignored`, and
asserts that :meth:`~digital_twin.repository.DigitalTwinRepository.list_active_issues`
returns *exactly* the complement — every non-ignored issue and none of the
ignored ones.

``persist_issues`` requires the referenced page (``issue.detail.page_url``) to
already be stored for the tenant, so each example first upserts a single page
and points every generated candidate's ``detail.page_url`` at it.

Each example uses a fresh in-memory SQLite database (the ORM uses generic column
types, so no PostgreSQL or Docker is required) so examples are independent.
"""

from __future__ import annotations

from datetime import datetime, timezone

from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.types import (
    CrawledPage,
    IssueCandidate,
    IssueDetail,
    IssueType,
    Severity,
)

from digital_twin.models import Base
from digital_twin.repository import DigitalTwinRepository

TENANT = "tenant-a"
PAGE_URL = "https://example.com/page"

# --- Strategies ---------------------------------------------------------------

_issue_types = st.sampled_from(list(IssueType))
_severities = st.sampled_from(list(Severity))
# Non-empty, non-blank descriptions (IssueCandidate.description has min_length=1).
# Excludes NUL (0x00) and surrogates because PostgreSQL TEXT fields reject both.
_descriptions = st.text(
    alphabet=st.characters(blacklist_characters="\x00", blacklist_categories=("Cs",)),
    min_size=1, max_size=40,
).filter(lambda s: s.strip() != "")


def _candidate(issue_type: IssueType, severity: Severity, description: str) -> IssueCandidate:
    """An IssueCandidate whose detail points at the single stored page."""
    return IssueCandidate(
        issue_type=issue_type,
        severity=severity,
        description=description,
        detail=IssueDetail(page_url=PAGE_URL, element="head"),
    )


@st.composite
def _candidates_and_mask(draw: st.DrawFn) -> tuple[list[IssueCandidate], list[bool]]:
    """Draw N (>=1) issue candidates plus an ignore-mask of the same length.

    ``mask[i] is True`` means the i-th persisted issue will be marked ignored.
    """
    n = draw(st.integers(min_value=1, max_value=15))
    candidates = [
        _candidate(
            draw(_issue_types),
            draw(_severities),
            draw(_descriptions),
        )
        for _ in range(n)
    ]
    mask = draw(st.lists(st.booleans(), min_size=n, max_size=n))
    return candidates, mask


def _fresh_repo() -> DigitalTwinRepository:
    """A repository over a fresh in-memory DB with the tenant configured."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    return DigitalTwinRepository(factory, tenant_id=TENANT)


def _seed_page(repo: DigitalTwinRepository) -> None:
    """Store the single page every candidate references (persist_issues needs it)."""
    repo.upsert_pages(
        TENANT,
        [
            CrawledPage(
                url=PAGE_URL,
                final_url=PAGE_URL,
                status_code=200,
                crawled_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            )
        ],
    )


@settings(max_examples=200)
@given(data=_candidates_and_mask())
def test_property_19_ignored_issues_excluded_from_active_reporting(
    data: tuple[list[IssueCandidate], list[bool]],
) -> None:
    """For any persisted issues with an arbitrary subset marked ignored,
    ``list_active_issues`` returns exactly the non-ignored issues.

    Feature: website-orchestrator-milestone-0, Property 19: Ignored issues are
    excluded from active reporting

    Validates: Requirements 4.11
    """
    candidates, mask = data
    repo = _fresh_repo()
    _seed_page(repo)

    stored = repo.persist_issues(TENANT, candidates)
    assert len(stored) == len(candidates)

    all_ids = {issue.id for issue in stored}
    ignored_ids = {issue.id for issue, ignore in zip(stored, mask) if ignore}
    expected_active_ids = all_ids - ignored_ids

    for issue_id in ignored_ids:
        repo.mark_issue_ignored(TENANT, issue_id)

    active = repo.list_active_issues(TENANT)
    active_ids = {issue.id for issue in active}

    # The active set is exactly the complement of the ignored set: every
    # non-ignored issue is present and no ignored issue leaks through (Req 4.11).
    assert active_ids == expected_active_ids
    assert active_ids.isdisjoint(ignored_ids)
