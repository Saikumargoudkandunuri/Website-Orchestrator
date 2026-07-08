"""Property 57 — Created records carry the configured tenant, or creation is rejected.

Feature: website-orchestrator-milestone-0, Property 57: Created records carry the
configured tenant, or creation is rejected

Validates: Requirements 14.5, 14.6

Requirement 14.5: WHEN a record is created in any database table, THE
Website_Orchestrator SHALL set its ``tenant_id`` to the configured Tenant_Id.

Requirement 14.6: IF a record is created in any database table and the Tenant_Id
cannot be determined, THEN THE Website_Orchestrator SHALL reject the record
creation and SHALL NOT persist a record with a missing ``tenant_id``.

The Digital_Twin resolves the tenant to stamp from the call's ``tenant_id``
argument, falling back to the tenant configured on the repository; a candidate is
"usable" only when it is non-empty after stripping surrounding whitespace. This
property drives that resolution across any combination of configured and
call-supplied tenant strings (including ``None``, empty, and whitespace-only):

* When a usable tenant IS resolvable, a created page is stored under exactly that
  resolved ``tenant_id`` — a read under the resolved tenant returns it, while a
  read under a *different* tenant does not — and ``persist_fixes`` returns records
  carrying the resolved ``tenant_id``.
* When NO tenant is resolvable, ``upsert_pages`` is rejected with
  :class:`~core.exceptions.DigitalTwinError` and nothing is persisted (a
  subsequent read under any tenant is :class:`~core.results.NotFound`).

Each example uses a fresh in-memory SQLite database so examples are independent.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.exceptions import DigitalTwinError
from core.results import NotFound, Ok
from core.types import (
    CrawledPage,
    FixStatus,
    IssueCandidate,
    IssueDetail,
    IssueType,
    Severity,
    SuggestedFix,
)

from digital_twin.models import Base
from digital_twin.repository import DigitalTwinRepository

# --- Strategies ---------------------------------------------------------------

# Whitespace-only / empty candidates: these are NOT usable tenants because they
# strip to the empty string.
_blankish = st.sampled_from(["", " ", "   ", "\t", "\n", " \t\n ", "\r\n"])

# Non-empty, non-blank tenant identifiers (usable once stripped).
# Excludes NUL (0x00) and surrogates because PostgreSQL TEXT fields reject both.
_usable_tenant = st.text(
    alphabet=st.characters(blacklist_characters="\x00", blacklist_categories=("Cs",)),
    min_size=1, max_size=30,
).filter(lambda s: s.strip() != "")

# A tenant candidate as it might be supplied: absent (None), blank, or usable.
_tenant_candidate = st.one_of(st.none(), _blankish, _usable_tenant)

# Non-blank text for the page URL so upsert matching on url is meaningful.
# Excludes NUL (0x00) and surrogates because PostgreSQL TEXT fields reject both.
_non_blank = st.text(
    alphabet=st.characters(blacklist_characters="\x00", blacklist_categories=("Cs",)),
    min_size=1, max_size=60,
).filter(lambda s: s.strip() != "")

_utc_datetimes = st.datetimes(
    min_value=datetime(2000, 1, 1),
    max_value=datetime(2100, 1, 1),
    timezones=st.just(timezone.utc),
)


def _resolve(call_tenant: str | None, configured_tenant: str | None) -> str | None:
    """Mirror the repository's tenant resolution: call takes precedence, then
    configured; a usable candidate is non-empty after stripping. Returns the
    resolved tenant, or ``None`` when neither is usable."""
    for candidate in (call_tenant, configured_tenant):
        if candidate is None:
            continue
        resolved = str(candidate).strip()
        if resolved:
            return resolved
    return None


def _fresh_repo(configured_tenant: str | None) -> DigitalTwinRepository:
    """A repository over a fresh in-memory DB with a wide Staleness_Threshold."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    return DigitalTwinRepository(
        factory,
        tenant_id=configured_tenant,
        staleness_threshold=timedelta(days=365_000),
    )


@st.composite
def _pages(draw: st.DrawFn) -> CrawledPage:
    url = draw(_non_blank)
    return CrawledPage(
        url=url,
        final_url=url,
        status_code=draw(st.integers(min_value=100, max_value=599)),
        title=draw(st.one_of(st.none(), _non_blank)),
        meta_description=draw(st.one_of(st.none(), _non_blank)),
        word_count=draw(st.integers(min_value=0, max_value=100_000)),
        has_schema=draw(st.booleans()),
        crawled_at=draw(_utc_datetimes),
    )


@settings(max_examples=100)
@given(
    configured_tenant=_tenant_candidate,
    call_tenant=_tenant_candidate,
    page=_pages(),
)
def test_property_57_tenant_stamping_on_create(
    configured_tenant: str | None,
    call_tenant: str | None,
    page: CrawledPage,
) -> None:
    """For any configured/call tenant combination, a created record carries the
    resolved tenant, or creation is rejected when no tenant is resolvable.

    Feature: website-orchestrator-milestone-0, Property 57: Created records carry
    the configured tenant, or creation is rejected

    Validates: Requirements 14.5, 14.6
    """
    repo = _fresh_repo(configured_tenant)
    resolved = _resolve(call_tenant, configured_tenant)

    if resolved is None:
        # Req 14.6 — no resolvable tenant: the write is rejected and nothing is
        # persisted. A read under any (usable) tenant finds nothing.
        with pytest.raises(DigitalTwinError):
            repo.upsert_pages(call_tenant, [page])

        for probe in ("probe-tenant", "another-tenant"):
            assert isinstance(
                repo.get_page(probe, page.url, now=page.crawled_at), NotFound
            )
        return

    # Req 14.5 — a usable tenant is resolvable: the page is stamped with it.
    repo.upsert_pages(call_tenant, [page])

    # Stored under exactly the resolved tenant.
    stored = repo.get_page(resolved, page.url, now=page.crawled_at)
    assert isinstance(stored, Ok)
    assert stored.unwrap().url == page.url

    # NOT stored under a different tenant.
    other_tenant = resolved + "-different"
    assert isinstance(
        repo.get_page(other_tenant, page.url, now=page.crawled_at), NotFound
    )

    # persist_fixes stamps and returns records carrying the resolved tenant.
    # First, persist an issue so the FK from suggested_fixes to issues is satisfied.
    issue_candidate = IssueCandidate(
        issue_type=IssueType.MISSING_ALT_TEXT,
        severity=Severity.MEDIUM,
        description="test issue for FK",
        detail=IssueDetail(page_url=page.url, element="img"),
    )
    persisted_issues = repo.persist_issues(call_tenant, [issue_candidate])
    assert len(persisted_issues) == 1
    issue_id = persisted_issues[0].id

    fix = SuggestedFix(
        id="fix-1",
        tenant_id="unstamped",
        issue_id=issue_id,
        auto_applicable=0,
        status=FixStatus.PENDING,
    )
    persisted = repo.persist_fixes(call_tenant, [fix])
    assert len(persisted) == 1
    assert persisted[0].tenant_id == resolved

    # Read back under the resolved tenant confirms the stamped record persisted.
    fetched = repo.get_fix(resolved, "fix-1")
    assert fetched is not None
    assert fetched.tenant_id == resolved
