"""Property 21 — Ignored or unmapped issues yield no fix.

Feature: website-orchestrator-milestone-0, Property 21: Ignored or unmapped
issues yield no fix

Validates: Requirements 5.2

Requirement 5.2: WHERE the Issue is marked ignored or the Issue type has no
defined fix mapping, THE Fix_Generator SHALL return None without producing a
SuggestedFix.

This property drives :meth:`fix_generator.FixGenerator.generate_fix` and asserts
it returns ``None`` for the two clauses of Req 5.2:

* **Ignored clause** — for *any* generated :class:`~core.types.Issue` with
  ``ignored=True`` (across every :class:`~core.types.IssueType`, with varied
  detail/tenant, and against varied :class:`~core.types.CrawledPage` values with
  or without matching images), ``generate_fix`` returns ``None``. This is the
  guaranteed path to ``None`` per Req 5.2.
* **Unmapped clause** — an Issue whose type has *no defined fix mapping* (i.e. a
  type absent from the generator's recognized set) also yields ``None`` when not
  ignored. We derive the "unmapped" set robustly as ``IssueType`` members minus
  the generator's recognized set. In the current implementation the generator
  recognizes *all* ``IssueType`` members (``frozenset(IssueType)``), so that set
  is empty; when it is empty we still exercise the unmapped *branch* defensively
  with a synthetic, unrecognized issue type. Should the recognized set ever
  shrink, the property-based unmapped test below activates automatically.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from hypothesis import given, settings
from hypothesis import strategies as st

from core.types import (
    CrawledPage,
    ImageRef,
    Issue,
    IssueDetail,
    IssueType,
    Severity,
)
from fix_generator import FixGenerator

# The generator's recognized/mapped issue-type set. Reading it from the module
# lets us derive the "unmapped" set (Req 5.2) rather than hard-coding it.
from fix_generator.generator import _RECOGNIZED_ISSUE_TYPES

# Issue types with no defined fix mapping = all types minus the recognized set.
_UNMAPPED_ISSUE_TYPES: frozenset[IssueType] = frozenset(IssueType) - _RECOGNIZED_ISSUE_TYPES


# --- Strategies ---------------------------------------------------------------

_text = st.text(max_size=40)
_nonempty_text = st.text(min_size=1, max_size=40)
_issue_types = st.sampled_from(list(IssueType))
_severities = st.sampled_from(list(Severity))


@st.composite
def _image_refs(draw: st.DrawFn) -> ImageRef:
    """An :class:`ImageRef` with a possibly-resolvable media id, an arbitrary
    (possibly empty) filename, and possibly-present alt text."""

    return ImageRef(
        media_id=draw(st.none() | st.integers(min_value=1, max_value=100_000)),
        filename=draw(st.text(max_size=30)),
        alt_text=draw(st.none() | _text),
    )


@st.composite
def _crawled_pages(draw: st.DrawFn) -> CrawledPage:
    """A :class:`CrawledPage` carrying zero or more images, so both the
    "matching images present" and "no images" shapes are exercised."""

    return CrawledPage(
        url=draw(_nonempty_text),
        final_url=draw(_nonempty_text),
        status_code=draw(st.integers(min_value=100, max_value=599)),
        images=draw(st.lists(_image_refs(), max_size=5)),
        crawled_at=datetime.now(timezone.utc),
    )


@st.composite
def _ignored_issues(draw: st.DrawFn) -> Issue:
    """An :class:`Issue` marked ``ignored=True`` spanning all issue types, with
    varied tenant, detail, and severity."""

    return Issue(
        id=draw(_nonempty_text),
        tenant_id=draw(_nonempty_text),
        issue_type=draw(_issue_types),
        severity=draw(_severities),
        description=draw(_nonempty_text),
        detail=IssueDetail(
            page_url=draw(_nonempty_text),
            element=draw(st.none() | _text),
        ),
        ignored=True,
    )


# --- Property: ignored issues yield no fix ------------------------------------


@settings(max_examples=150)
@given(issue=_ignored_issues(), page=_crawled_pages())
def test_property_21_ignored_issue_yields_no_fix(
    issue: Issue, page: CrawledPage
) -> None:
    """For any ignored Issue (any type, any page), ``generate_fix`` returns
    ``None`` and produces no SuggestedFix.

    Feature: website-orchestrator-milestone-0, Property 21: Ignored or unmapped
    issues yield no fix

    Validates: Requirements 5.2
    """
    assert FixGenerator().generate_fix(issue, page) is None


# --- Property/branch: unmapped issue types yield no fix -----------------------

if _UNMAPPED_ISSUE_TYPES:

    @settings(max_examples=150)
    @given(
        issue_type=st.sampled_from(sorted(_UNMAPPED_ISSUE_TYPES, key=lambda t: t.value)),
        id_=_nonempty_text,
        tenant_id=_nonempty_text,
        severity=_severities,
        description=_nonempty_text,
        page=_crawled_pages(),
    )
    def test_property_21_unmapped_type_yields_no_fix(
        issue_type: IssueType,
        id_: str,
        tenant_id: str,
        severity: Severity,
        description: str,
        page: CrawledPage,
    ) -> None:
        """For any non-ignored Issue whose type has no defined fix mapping,
        ``generate_fix`` returns ``None``.

        Feature: website-orchestrator-milestone-0, Property 21: Ignored or
        unmapped issues yield no fix

        Validates: Requirements 5.2
        """
        issue = Issue(
            id=id_,
            tenant_id=tenant_id,
            issue_type=issue_type,
            severity=severity,
            description=description,
            detail=IssueDetail(page_url="https://example.test/", element=None),
            ignored=False,
        )
        assert FixGenerator().generate_fix(issue, page) is None


def test_property_21_unmapped_type_defensive() -> None:
    """Defensively exercise the "no defined fix mapping" branch even when the
    generator currently recognizes every ``IssueType`` (so the derived unmapped
    set is empty). A non-ignored issue carrying an unrecognized type token must
    still yield ``None`` (Req 5.2).

    Feature: website-orchestrator-milestone-0, Property 21: Ignored or unmapped
    issues yield no fix

    Validates: Requirements 5.2
    """
    page = CrawledPage(
        url="https://example.test/",
        final_url="https://example.test/",
        status_code=200,
        crawled_at=datetime.now(timezone.utc),
    )
    # A sentinel type object that is guaranteed absent from the recognized set,
    # standing in for an issue type with no defined fix mapping.
    unmapped_issue = SimpleNamespace(ignored=False, issue_type=object())
    assert FixGenerator().generate_fix(unmapped_issue, page) is None
