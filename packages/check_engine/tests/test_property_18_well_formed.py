"""Property 18 — Every emitted issue candidate is well-formed and structured.

Feature: website-orchestrator-milestone-0, Property 18: Every emitted issue candidate is well-formed and structured

Validates: Requirements 4.8, 4.9

Requirement 4.8: Every emitted ``IssueCandidate`` SHALL be well-formed — its
``severity`` is one of ``critical | high | medium | low``, its ``description``
is a non-empty human-readable string, and its ``detail`` identifies the affected
page URL plus the triggering element or location.

Requirement 4.9: Emitted issues SHALL be structured (a proper ``IssueCandidate``
object), not free text.

This property drives :class:`~check_engine.CheckEngine` with a broad,
Hypothesis-generated list of :class:`~core.types.CrawledPage` records — varied to
trigger every check (missing titles, blank meta, thin content, missing-alt
images, broken links, redirect chains, missing schema, duplicate titles) — and
asserts that EVERY candidate returned by ``run_all_checks`` *and* by each
individual check is a structurally well-formed ``IssueCandidate``:

* it is an ``isinstance`` of :class:`~core.types.IssueCandidate` (Req 4.9 —
  structured, not free text);
* its ``issue_type`` is a valid :class:`~core.types.IssueType`;
* its ``severity`` is a valid :class:`~core.types.Severity`
  (``critical | high | medium | low``) (Req 4.8);
* its ``description`` is a non-empty (stripped) string (Req 4.8);
* its ``detail`` is an :class:`~core.types.IssueDetail` whose ``page_url`` is a
  non-empty string that matches a real input page url, and whose
  ``element`` is a non-empty (stripped) location (Req 4.8).

The page strategy mirrors the broad style of ``test_property_13_determinism.py``
so every branch of every check is exercised.
"""

from __future__ import annotations

from datetime import datetime, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

from check_engine import CheckEngine
from core.constants import REDIRECT_CHAIN_THRESHOLD, THIN_CONTENT_MIN_WORDS
from core.types import (
    CrawledPage,
    ImageRef,
    IssueCandidate,
    IssueDetail,
    IssueType,
    LinkStatus,
    RedirectChain,
    Severity,
)

# --- Strategies ---------------------------------------------------------------

# A small pool of titles so duplicates recur across pages (drives the
# duplicate-title check). Includes blank/None so the missing-title check fires.
_titles = st.sampled_from([None, "", "   ", "Home", "About", "Home", "Contact"])

# Meta description: blank variants plus real text (drives missing-meta check).
_meta_descriptions = st.one_of(
    st.sampled_from([None, "", "   "]),
    st.text(min_size=1, max_size=40),
)

# Word counts straddling the thin-content threshold (default 300).
_word_counts = st.integers(min_value=0, max_value=THIN_CONTENT_MIN_WORDS + 50)

# Status codes spanning ok (2xx/3xx), error (4xx/5xx), and unreachable (None).
_status_codes = st.one_of(
    st.none(),
    st.sampled_from([200, 201, 301, 302, 399, 400, 404, 410, 500, 503, 599]),
)


@st.composite
def _links(draw: st.DrawFn) -> LinkStatus:
    """A link with a varied (ok / error / None) status code."""
    status = draw(_status_codes)
    return LinkStatus(
        url=draw(st.text(min_size=1, max_size=30)),
        status_code=status,
        reachable=status is not None,
    )


@st.composite
def _images(draw: st.DrawFn) -> ImageRef:
    """An image that may or may not have alt text and a media id."""
    return ImageRef(
        media_id=draw(
            st.one_of(st.none(), st.integers(min_value=1, max_value=9999))
        ),
        filename=draw(
            st.text(min_size=1, max_size=20).filter(lambda s: s.strip() != "")
        ),
        alt_text=draw(
            st.one_of(
                st.sampled_from([None, "", "   "]),
                st.text(min_size=1, max_size=20),
            )
        ),
    )


@st.composite
def _redirect_chains(draw: st.DrawFn) -> RedirectChain:
    """A redirect chain whose hop count spans the redirect threshold."""
    hop_count = draw(
        st.integers(min_value=0, max_value=REDIRECT_CHAIN_THRESHOLD + 2)
    )
    hops = [f"https://example.com/hop{i}" for i in range(hop_count)]
    return RedirectChain(hops=hops, truncated=draw(st.booleans()))


@st.composite
def _pages(draw: st.DrawFn) -> CrawledPage:
    """A varied CrawledPage exercising every check branch."""
    url = draw(
        st.text(min_size=1, max_size=30).filter(lambda s: s.strip() != "")
    )
    return CrawledPage(
        url=url,
        final_url=url,
        status_code=draw(st.sampled_from([200, 301, 404, 500])),
        title=draw(_titles),
        meta_description=draw(_meta_descriptions),
        word_count=draw(_word_counts),
        links=draw(st.lists(_links(), max_size=4)),
        images=draw(st.lists(_images(), max_size=4)),
        redirect_chain=draw(_redirect_chains()),
        has_schema=draw(st.booleans()),
        crawled_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )


_page_lists = st.lists(_pages(), max_size=6)


# --- Helper -------------------------------------------------------------------


def _assert_well_formed(
    candidate: IssueCandidate, valid_page_urls: set[str]
) -> None:
    """Assert a single candidate is a structured, well-formed IssueCandidate.

    Encodes Requirements 4.8 (well-formed) and 4.9 (structured, not free text).
    """
    # Req 4.9: structured — a proper IssueCandidate object, not free text.
    assert isinstance(candidate, IssueCandidate)

    # issue_type is a valid IssueType.
    assert isinstance(candidate.issue_type, IssueType)

    # Req 4.8: severity is one of critical | high | medium | low.
    assert isinstance(candidate.severity, Severity)
    assert candidate.severity in {
        Severity.CRITICAL,
        Severity.HIGH,
        Severity.MEDIUM,
        Severity.LOW,
    }

    # Req 4.8: description is a non-empty, human-readable string.
    assert isinstance(candidate.description, str)
    assert candidate.description.strip() != ""

    # Req 4.8: detail identifies the affected page URL + triggering element.
    assert isinstance(candidate.detail, IssueDetail)
    assert isinstance(candidate.detail.page_url, str)
    assert candidate.detail.page_url.strip() != ""
    # The page URL locates a real input page (page-level and cross-page checks).
    assert candidate.detail.page_url in valid_page_urls
    # The triggering element/location is present and non-empty.
    assert candidate.detail.element is not None
    assert candidate.detail.element.strip() != ""


# --- Property -----------------------------------------------------------------


@settings(max_examples=200)
@given(pages=_page_lists)
def test_property_18_every_candidate_is_well_formed(
    pages: list[CrawledPage],
) -> None:
    """Every candidate emitted by the aggregator and by each individual check is
    a structurally well-formed ``IssueCandidate``.

    Feature: website-orchestrator-milestone-0, Property 18: Every emitted issue candidate is well-formed and structured

    Validates: Requirements 4.8, 4.9
    """
    engine = CheckEngine()
    valid_page_urls = {page.url for page in pages}

    # The aggregated output: every emitted candidate is well-formed.
    for candidate in engine.run_all_checks(pages):
        _assert_well_formed(candidate, valid_page_urls)

    # Every individual page-level check likewise emits only well-formed
    # candidates (single-value checks return a candidate or None).
    for page in pages:
        for single_check in (
            engine.check_missing_title,
            engine.check_missing_meta_description,
            engine.check_thin_content,
            engine.check_redirect_chains,
            engine.check_missing_schema,
        ):
            candidate = single_check(page)
            if candidate is not None:
                _assert_well_formed(candidate, valid_page_urls)

        # Multi-value page checks return lists of candidates.
        for candidate in engine.check_missing_alt_text(page):
            _assert_well_formed(candidate, valid_page_urls)
        for candidate in engine.check_broken_links(page):
            _assert_well_formed(candidate, valid_page_urls)

    # The cross-page duplicate-title check emits only well-formed candidates.
    for candidate in engine.check_duplicate_titles(pages):
        _assert_well_formed(candidate, valid_page_urls)
