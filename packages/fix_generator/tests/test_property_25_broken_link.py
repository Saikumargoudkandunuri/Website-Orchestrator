"""Property 25 — Broken-link fixes never propose a replacement URL.

Feature: website-orchestrator-milestone-0, Property 25: Broken-link fixes never
propose a replacement URL

Validates: Requirements 5.7

Requirement 5.7: a ``broken_links`` Issue never yields a generated replacement
URL. The Fix_Generator maps broken-link issues to a *report-only*
:class:`SuggestedFix` — its ``proposed_value`` is left empty (``None``), no write
target is set, and it is not auto-applicable. Crucially, the broken link URL(s)
present on the page and referenced in ``issue.detail`` must never be copied into
``proposed_value``.

This property drives :meth:`fix_generator.FixGenerator.generate_fix` with a wide
variety of generated ``broken_links`` issues. Each is paired with a
:class:`CrawledPage` carrying broken links with assorted error statuses, and the
issue ``detail.element`` references one of those broken link URLs. The property
asserts the produced fix proposes NO replacement URL and does not smuggle any of
the broken link URLs into ``proposed_value``.
"""

from __future__ import annotations

from datetime import datetime, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

from core.types import (
    CrawledPage,
    Issue,
    IssueDetail,
    IssueType,
    LinkStatus,
    Severity,
    SuggestedFix,
)
from fix_generator import FixGenerator

# --- Strategies ---------------------------------------------------------------

# The transform never inspects timestamps, so a constant crawl time is fine.
_CRAWLED_AT = datetime(2024, 1, 1, tzinfo=timezone.utc)

_PAGE_URLS = [
    "https://example.com/",
    "https://example.com/about",
    "https://shop.example.com/products/42",
    "http://example.org/page?q=1",
]

# A pool of URLs used for broken links; varied shapes so the generator has many
# distinct strings it could (but must not) copy into proposed_value.
_broken_url_strings = st.one_of(
    st.sampled_from(
        [
            "https://example.com/missing",
            "http://dead.example.net/gone.html",
            "https://cdn.example.org/asset.js?v=3",
            "https://example.com/old/path#frag",
            "ftp://legacy.example.com/file.zip",
            "https://tracker.example.io/pixel.gif",
        ]
    ),
    # Fully arbitrary text keeps the generator honest about never echoing input.
    st.text(min_size=1, max_size=40),
)

# HTTP error / unreachable statuses a broken link may carry.
_error_status_codes = st.one_of(
    st.none(),  # unreachable — no status code
    st.sampled_from([400, 401, 403, 404, 410, 500, 502, 503, 504]),
)


def _broken_links() -> st.SearchStrategy[LinkStatus]:
    """Generate broken links: an error/unreachable status and reachable=False."""

    return st.builds(
        LinkStatus,
        url=_broken_url_strings,
        status_code=_error_status_codes,
        reachable=st.just(False),
    )


@st.composite
def _broken_link_scenarios(draw: st.DrawFn) -> tuple[Issue, CrawledPage]:
    """Build a ``broken_links`` Issue whose detail references one of the page's
    broken link URLs, paired with the CrawledPage that carries those links."""

    # At least one broken link so there is a URL available to (wrongly) copy.
    links = draw(st.lists(_broken_links(), min_size=1, max_size=5))

    page_url = draw(st.sampled_from(_PAGE_URLS))

    # The Check_Engine records the offending link in detail.element; reference
    # one of the actual broken URLs so we can prove the generator never copies
    # it into proposed_value.
    referenced = draw(st.sampled_from([link.url for link in links]))
    element = draw(
        st.sampled_from(
            [
                referenced,
                f"<a href='{referenced}'>broken</a>",
                f"link -> {referenced}",
            ]
        )
    )

    issue = draw(
        st.builds(
            Issue,
            issue_type=st.just(IssueType.BROKEN_LINKS),
            severity=st.sampled_from(list(Severity)),
            description=st.text(min_size=1, max_size=60),
            detail=st.builds(
                IssueDetail,
                page_url=st.just(page_url),
                element=st.just(element),
            ),
            id=st.uuids().map(str),
            tenant_id=st.text(min_size=1, max_size=12),
            ignored=st.just(False),
        )
    )

    page = draw(
        st.builds(
            CrawledPage,
            url=st.just(page_url),
            final_url=st.just(page_url),
            status_code=st.sampled_from([200, 301, 404, 500]),
            links=st.just(links),
            crawled_at=st.just(_CRAWLED_AT),
        )
    )

    return issue, page


# --- Property -----------------------------------------------------------------


@settings(max_examples=200)
@given(scenario=_broken_link_scenarios())
def test_property_25_broken_link_fix_proposes_no_url(
    scenario: tuple[Issue, CrawledPage],
) -> None:
    """For any ``broken_links`` Issue, ``generate_fix`` returns a report-only
    SuggestedFix that proposes no replacement URL and never copies a broken link
    URL into ``proposed_value``.

    Feature: website-orchestrator-milestone-0, Property 25: Broken-link fixes
    never propose a replacement URL

    Validates: Requirements 5.7
    """
    issue, page = scenario
    generator = FixGenerator()

    result = generator.generate_fix(issue, page)

    # A recognized (non-ignored) broken_links issue always yields a fix.
    assert isinstance(result, SuggestedFix)

    # (5.7) No generated replacement URL / value at all.
    assert result.proposed_value is None

    # (5.7) Report-only: no write target, not auto-applicable, no fix type.
    assert result.fix_type is None
    assert result.target_ref is None
    assert result.auto_applicable == 0

    # (5.7) The fix must not smuggle any broken link URL into proposed_value.
    # proposed_value is None above, but assert explicitly against every broken
    # URL (including the one referenced in the issue detail) to guard against a
    # future regression that starts populating it.
    broken_urls = {link.url for link in page.links}
    broken_urls.add(issue.detail.element or "")
    for url in broken_urls:
        assert result.proposed_value != url

    # The originating Issue reference is retained on the report-only fix.
    assert result.issue_id == issue.id
