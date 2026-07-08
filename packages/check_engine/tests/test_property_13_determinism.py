"""Property 13 — Check_Engine checks are deterministic.

Feature: website-orchestrator-milestone-0, Property 13: Checks are deterministic

Validates: Requirements 4.1

Requirement 4.1: THE Check_Engine SHALL run deterministic, rule-based checks
(no LLM), so that for any given input the emitted issue candidates are fully
reproducible.

This property drives :class:`~check_engine.CheckEngine` with a Hypothesis-generated
list of varied :class:`~core.types.CrawledPage` records and asserts that running
the same check twice on the same input yields the *identical* result — same order,
same content. Because :class:`~core.types.IssueCandidate` is a Pydantic model,
``==`` compares field values, so equal lists mean byte-for-byte reproducible
candidates.

The page strategy is intentionally broad so every branch of every check is
exercised across runs:

* ``title`` — blank / present, and deliberately drawn from a *small* pool so
  duplicates recur across pages (exercising ``check_duplicate_titles``).
* ``meta_description`` — blank / present.
* ``word_count`` — spans the thin-content threshold (below / at / above 300).
* ``images`` — mixes images with and without alt text, with/without media ids.
* ``links`` — mixes ok (2xx/3xx) and error (4xx/5xx) status codes, plus None.
* ``redirect_chain`` — hop counts spanning the redirect threshold (0..threshold+2).
* ``has_schema`` — True / False.
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
    LinkStatus,
    RedirectChain,
)

# --- Strategies ---------------------------------------------------------------

# A small pool of titles so duplicates recur across pages (drives duplicate-title
# grouping). Includes blank/None so the missing-title check also fires.
_titles = st.sampled_from([None, "", "   ", "Home", "About", "Home", "Contact"])

# Meta description: blank variants plus real text.
_meta_descriptions = st.one_of(
    st.sampled_from([None, "", "   "]),
    st.text(min_size=1, max_size=40),
)

# Word counts straddling the thin-content threshold (default 300).
_word_counts = st.integers(
    min_value=0, max_value=THIN_CONTENT_MIN_WORDS + 50
)

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
        media_id=draw(st.one_of(st.none(), st.integers(min_value=1, max_value=9999))),
        filename=draw(st.text(min_size=1, max_size=20).filter(lambda s: s.strip() != "")),
        alt_text=draw(
            st.one_of(st.sampled_from([None, "", "   "]), st.text(min_size=1, max_size=20))
        ),
    )


@st.composite
def _redirect_chains(draw: st.DrawFn) -> RedirectChain:
    """A redirect chain whose hop count spans the redirect threshold."""
    hop_count = draw(st.integers(min_value=0, max_value=REDIRECT_CHAIN_THRESHOLD + 2))
    hops = [f"https://example.com/hop{i}" for i in range(hop_count)]
    return RedirectChain(hops=hops, truncated=draw(st.booleans()))


@st.composite
def _pages(draw: st.DrawFn) -> CrawledPage:
    """A varied CrawledPage exercising every check branch."""
    url = draw(st.text(min_size=1, max_size=30).filter(lambda s: s.strip() != ""))
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


# --- Property -----------------------------------------------------------------


@settings(max_examples=200)
@given(pages=_page_lists)
def test_property_13_checks_are_deterministic(pages: list[CrawledPage]) -> None:
    """For any set of pages, running the full aggregator (and each individual
    check) twice produces the identical list of IssueCandidate objects — same
    order and same content.

    Feature: website-orchestrator-milestone-0, Property 13: Checks are deterministic

    Validates: Requirements 4.1
    """
    engine = CheckEngine()

    # The aggregator is fully reproducible across two calls on the same input.
    first = engine.run_all_checks(pages)
    second = engine.run_all_checks(pages)
    assert first == second

    # A fresh engine instance yields the same result (no hidden shared state).
    assert CheckEngine().run_all_checks(pages) == first

    # Every individual check is likewise deterministic across two calls.
    for page in pages:
        assert engine.check_missing_title(page) == engine.check_missing_title(page)
        assert engine.check_missing_meta_description(
            page
        ) == engine.check_missing_meta_description(page)
        assert engine.check_thin_content(page) == engine.check_thin_content(page)
        assert engine.check_redirect_chains(page) == engine.check_redirect_chains(page)
        assert engine.check_missing_schema(page) == engine.check_missing_schema(page)
        assert engine.check_missing_alt_text(page) == engine.check_missing_alt_text(page)
        assert engine.check_broken_links(page) == engine.check_broken_links(page)

    # The cross-page duplicate-title check is deterministic across two calls.
    assert engine.check_duplicate_titles(pages) == engine.check_duplicate_titles(pages)
