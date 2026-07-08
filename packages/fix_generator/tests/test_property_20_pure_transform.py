"""Property 20 — ``generate_fix`` is a pure transform returning at most one fix.

Feature: website-orchestrator-milestone-0, Property 20: generate_fix is a pure
transform returning at most one fix

Validates: Requirements 5.1

Requirement 5.1: the Fix_Generator transforms an :class:`Issue` (given the
:class:`CrawledPage` it was raised against) into *at most one*
:class:`SuggestedFix` and never writes to the database — it is a pure transform.

This property drives :meth:`fix_generator.FixGenerator.generate_fix` with a wide
variety of generated :class:`Issue` / :class:`CrawledPage` pairs and asserts:

* the return is either ``None`` or exactly one :class:`SuggestedFix` (never a
  list, tuple, or multiple values);
* the transform is **pure / deterministic** — calling it twice with the same
  inputs yields equal results for every field except the freshly-minted ``id``
  (a random uuid per call), so results are compared with ``id`` normalized; and
* the transform does not mutate its inputs — the ``Issue`` and ``CrawledPage``
  are unchanged (by ``model_dump``) after the call.

The Fix_Generator uses no database or network, so nothing needs stubbing here.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from core.types import (
    CrawledPage,
    ImageRef,
    Issue,
    IssueDetail,
    IssueType,
    Severity,
    SuggestedFix,
)
from fix_generator import FixGenerator

# --- Strategies ---------------------------------------------------------------

# A fixed reference datetime keeps CrawledPage construction simple; the transform
# never inspects timestamps, so a constant value does not narrow coverage.
from datetime import datetime, timezone

_CRAWLED_AT = datetime(2024, 1, 1, tzinfo=timezone.utc)

_urls = st.sampled_from(
    [
        "https://example.com/",
        "https://example.com/about",
        "https://shop.example.com/products/42",
        "http://example.org/page?q=1",
    ]
)

# Element text sometimes references an image (by media_id token or filename) and
# sometimes does not; None/blank is also allowed so the "no element" branch runs.
_elements = st.one_of(
    st.none(),
    st.just(""),
    st.text(max_size=40),
    st.builds(lambda mid: f"<img media_id={mid}>", st.integers(min_value=1, max_value=999)),
    st.sampled_from(
        [
            "<img src='/uploads/red-sunset.jpg'>",
            "photo_2023.PNG",
            "banner%20final.jpeg",
            "<img alt=''>",
        ]
    ),
)


def _issues() -> st.SearchStrategy[Issue]:
    """Generate varied persisted Issues across all issue types."""

    return st.builds(
        Issue,
        issue_type=st.sampled_from(list(IssueType)),
        severity=st.sampled_from(list(Severity)),
        description=st.text(min_size=1, max_size=60),
        detail=st.builds(IssueDetail, page_url=_urls, element=_elements),
        id=st.uuids().map(str),
        tenant_id=st.text(min_size=1, max_size=12),
        ignored=st.booleans(),
    )


# Image filenames vary: readable names, extensionless, path-y, percent-encoded,
# and blank/whitespace (which the transform treats as unusable).
_filenames = st.one_of(
    st.sampled_from(
        [
            "red-sunset.jpg",
            "photo_2023.PNG",
            "banner%20final.jpeg",
            "/uploads/2024/hero-image.webp",
            "no-extension",
            "IMG-1234.gif",
        ]
    ),
    st.text(max_size=30),
    st.just(""),
    st.just("   "),
)


def _images() -> st.SearchStrategy[ImageRef]:
    """Generate images with/without media_id and with varied filenames/alt."""

    return st.builds(
        ImageRef,
        media_id=st.one_of(st.none(), st.integers(min_value=1, max_value=999)),
        filename=_filenames,
        alt_text=st.one_of(st.none(), st.just(""), st.text(max_size=30)),
    )


def _pages() -> st.SearchStrategy[CrawledPage]:
    """Generate CrawledPages with and without images."""

    return st.builds(
        CrawledPage,
        url=_urls,
        final_url=_urls,
        status_code=st.sampled_from([200, 301, 404, 500]),
        images=st.lists(_images(), max_size=4),
        crawled_at=st.just(_CRAWLED_AT),
    )


# --- Property -----------------------------------------------------------------


@settings(max_examples=200)
@given(issue=_issues(), page=_pages())
def test_property_20_generate_fix_is_pure_transform(
    issue: Issue, page: CrawledPage
) -> None:
    """For any Issue + CrawledPage, ``generate_fix`` returns None or exactly one
    SuggestedFix, is deterministic (modulo the fresh uuid id), and does not
    mutate its inputs.

    Feature: website-orchestrator-milestone-0, Property 20: generate_fix is a
    pure transform returning at most one fix

    Validates: Requirements 5.1
    """
    generator = FixGenerator()

    # Snapshot inputs to detect any mutation by the transform.
    issue_before = issue.model_dump()
    page_before = page.model_dump()

    result = generator.generate_fix(issue, page)

    # (5.1) At most one fix: the result is either None or a single SuggestedFix,
    # never a collection of fixes.
    assert result is None or isinstance(result, SuggestedFix)
    assert not isinstance(result, (list, tuple, set))

    # (5.1) Purity — inputs are not mutated by the transform.
    assert issue.model_dump() == issue_before
    assert page.model_dump() == page_before

    # (5.1) Determinism — a second call on the same inputs yields the same
    # outcome. The id is a fresh uuid per call, so compare with it normalized.
    result_again = generator.generate_fix(issue, page)

    assert (result is None) == (result_again is None)
    if result is not None and result_again is not None:
        first = result.model_dump()
        second = result_again.model_dump()
        # Each call mints its own uuid; the id must differ, every other field
        # must match exactly.
        assert first["id"] != second["id"]
        first["id"] = second["id"] = "<normalized>"
        assert first == second
