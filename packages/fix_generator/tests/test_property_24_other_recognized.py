"""Property 24 — Other recognized issue types yield report-only fixes.

Feature: website-orchestrator-milestone-0, Property 24: Other recognized issue
types yield report-only fixes

Validates: Requirements 5.6

Requirement 5.6: WHEN the Issue is a recognized type OTHER than a resolvable
missing_alt_text, THE Fix_Generator SHALL produce a report-only SuggestedFix
(``auto_applicable=0``) recording a human-readable report-only reason, proposing
no value and no write target, and retaining the originating Issue reference.

This property drives :meth:`fix_generator.FixGenerator.generate_fix` with a
non-ignored :class:`~core.types.Issue` whose ``issue_type`` is one of the
recognized types other than ``missing_alt_text`` (that type is covered by
Properties 22/23). Pages are varied — some carry images, some do not — because
image presence must not affect the report-only outcome for these types.
"""

from __future__ import annotations

from datetime import datetime, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

from core.types import (
    CrawledPage,
    FixStatus,
    ImageRef,
    Issue,
    IssueDetail,
    IssueType,
    Severity,
)
from fix_generator import FixGenerator

# --- Strategies ---------------------------------------------------------------

# Every recognized issue type EXCEPT missing_alt_text — these are the types that
# must yield a report-only fix under Req 5.6.
_OTHER_RECOGNIZED_TYPES = [
    t for t in IssueType if t is not IssueType.MISSING_ALT_TEXT
]

# Non-empty identifier text for Issue.id / tenant_id.
_ids = st.text(min_size=1, max_size=24).filter(lambda s: s.strip() != "")

# Non-empty text for descriptions and page URLs.
_nonblank = st.text(min_size=1, max_size=80).filter(lambda s: s.strip() != "")


@st.composite
def _images(draw: st.DrawFn) -> ImageRef:
    """An arbitrary image reference (present or missing media_id / alt text).

    Image presence and shape must not matter for these issue types, so we
    generate varied images to prove they are ignored.
    """
    return ImageRef(
        media_id=draw(st.one_of(st.none(), st.integers(min_value=1, max_value=10_000))),
        filename=draw(st.text(min_size=0, max_size=30)),
        alt_text=draw(st.one_of(st.none(), st.just(""), _nonblank)),
    )


@settings(max_examples=150)
@given(
    issue_type=st.sampled_from(_OTHER_RECOGNIZED_TYPES),
    issue_id=_ids,
    tenant_id=_ids,
    severity=st.sampled_from(list(Severity)),
    description=_nonblank,
    page_url=_nonblank,
    element=st.one_of(st.none(), _nonblank),
    images=st.lists(_images(), min_size=0, max_size=5),
)
def test_property_24_other_recognized_types_yield_report_only_fixes(
    issue_type: IssueType,
    issue_id: str,
    tenant_id: str,
    severity: Severity,
    description: str,
    page_url: str,
    element: str | None,
    images: list[ImageRef],
) -> None:
    """For any non-ignored Issue whose type is a recognized type other than
    missing_alt_text, ``generate_fix`` returns a report-only SuggestedFix:
    ``auto_applicable == 0``, a non-empty human-readable reason, no proposed
    value, no fix_type, no target_ref, pending status, retaining issue_id and
    tenant_id. Image presence on the page is irrelevant.

    Feature: website-orchestrator-milestone-0, Property 24: Other recognized
    issue types yield report-only fixes

    Validates: Requirements 5.6
    """
    issue = Issue(
        id=issue_id,
        tenant_id=tenant_id,
        issue_type=issue_type,
        severity=severity,
        description=description,
        detail=IssueDetail(page_url=page_url, element=element),
        ignored=False,
    )

    page = CrawledPage(
        url=page_url,
        final_url=page_url,
        status_code=200,
        images=images,
        crawled_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )

    fix = FixGenerator().generate_fix(issue, page)

    # A report-only fix must always be produced for these recognized types.
    assert fix is not None

    # Req 5.6 — report-only: not auto-applicable, no write target, no value,
    # no fix type.
    assert fix.auto_applicable == 0
    assert fix.fix_type is None
    assert fix.target_ref is None
    assert fix.proposed_value is None

    # Req 5.6 — a non-empty, human-readable report-only reason.
    assert fix.reason is not None
    assert fix.reason.strip() != ""

    # Provenance / lifecycle: retains the originating Issue and tenant, pending.
    assert fix.issue_id == issue.id
    assert fix.tenant_id == issue.tenant_id
    assert fix.status == FixStatus.PENDING
