"""Property 1 — Retrieval stays within the same registrable domain.

Feature: website-orchestrator-milestone-0, Property 1: Retrieval stays within
the same registrable domain.

**Validates: Requirements 1.2, 1.3**

The Crawler restricts retrieval to URLs on the same *registrable* domain as
``start_url`` — a host or subdomain sharing the same eTLD+1 (Req 1.2) — and
excludes every out-of-domain URL from retrieval (Req 1.3).

This property drives the crawl with an in-memory fetcher whose pages contain a
generated mix of same-registrable-domain links (varied subdomains and paths)
and off-domain links (a different registrable domain, possibly with its own
subdomains). Crawling with a generous ``max_pages``, it asserts two things for
any such generated site:

1. Every returned :class:`~core.types.CrawledPage` has the same registrable
   domain as ``start_url`` (Req 1.2).
2. The fetcher was never asked to retrieve an off-domain URL — the exclusion
   happens *before* retrieval, not after (Req 1.3).

Everything runs network-free: an in-memory fetcher maps URL -> FetchResponse,
an allow-all :class:`RobotsGate` (empty ``robots.txt``) permits every URL, and
per-host pacing is disabled so the run is fast and deterministic (Req 2.5).
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from core.utils import normalize_url, registrable_domain, same_registrable_domain

from crawler import Crawler, FetchResponse, RobotsGate

# --- In-memory boundaries -----------------------------------------------------


class FakeFetcher:
    """In-memory :class:`crawler.fetcher.Fetcher` mapping URL -> FetchResponse.

    Records every URL the crawler asks it to retrieve so the test can assert no
    out-of-domain URL was ever fetched (Req 1.3). Keys are normalized URLs to
    match what the crawler enqueues via :func:`core.utils.normalize_url`.
    """

    def __init__(self, pages: dict[str, str]) -> None:
        self._pages = pages
        self.requested: list[str] = []

    def fetch(self, url: str) -> FetchResponse:
        self.requested.append(url)
        html = self._pages.get(url, "")
        status = 200 if url in self._pages else 404
        return FetchResponse(url=url, final_url=url, status_code=status, html=html)


def _allow_all_gate() -> RobotsGate:
    """A network-free robots gate whose empty robots.txt allows every URL."""
    return RobotsGate(lambda _robots_url: "")


def _crawler(fetcher: FakeFetcher) -> Crawler:
    """Build a Crawler with the fake fetcher, allow-all robots, and no pacing."""
    return Crawler(
        fetcher,
        robots_gate=_allow_all_gate(),
        sleep=lambda _seconds: None,
        rate_limit_ms=0,
    )


def _page(links: list[str]) -> str:
    """Render an HTML page whose body anchors point at every URL in ``links``."""
    anchors = "".join(f'<a href="{href}">link</a>' for href in links)
    return (
        "<html><head><title>Page</title></head>"
        f"<body>some words here {anchors}</body></html>"
    )


# --- Generators ---------------------------------------------------------------

# A small vocabulary of registered names and public suffixes. Combining a name
# with a suffix yields a registrable domain (eTLD+1); ``co.uk`` exercises a
# multi-label public suffix so the property covers more than the naive
# "last two labels" case.
_DOMAIN_LABELS = ["example", "acme", "widgets", "foosite", "barcorp", "testco"]
_SUFFIXES = ["com", "org", "net", "io", "co.uk"]

# Subdomain prefixes (including the empty apex and a deep multi-label one) so
# retrieval must recognise any host *under* the same registrable domain
# (Req 1.2), not just the bare apex.
_SUBDOMAINS = ["", "www.", "blog.", "shop.", "app.", "sub.deep."]

# Path suffixes (including the empty root) so same-domain targets vary by path
# as well as by host.
_PATHS = ["", "about", "contact", "products", "team/alice", "blog/post-1", "a", "b/c"]


@st.composite
def _registrable_domains(draw: st.DrawFn) -> str:
    """Draw a registrable domain such as ``acme.com`` or ``testco.co.uk``."""
    label = draw(st.sampled_from(_DOMAIN_LABELS))
    suffix = draw(st.sampled_from(_SUFFIXES))
    return f"{label}.{suffix}"


def _url(subdomain: str, domain: str, path: str) -> str:
    """Build a normalized https URL from a subdomain, domain, and path."""
    host = f"{subdomain}{domain}"
    raw = f"https://{host}/{path}" if path else f"https://{host}"
    return normalize_url(raw)


_host_specs = st.tuples(st.sampled_from(_SUBDOMAINS), st.sampled_from(_PATHS))


@st.composite
def _scenarios(draw: st.DrawFn) -> tuple[str, FakeFetcher, list[str]]:
    """Generate a start URL and an in-memory site mixing same/off-domain links.

    Returns ``(start_url, fetcher, off_urls)`` where the fetcher's start page
    links to an interleaved mix of same-registrable-domain URLs (present in the
    fetcher and expected to be retrievable) and off-domain URLs (a different
    registrable domain, absent from the fetcher and expected to be excluded).
    """
    start_domain = draw(_registrable_domains())
    start_sub, start_path = draw(_host_specs)
    start_url = _url(start_sub, start_domain, start_path)

    # Same-registrable-domain targets, varied by subdomain and path.
    same_specs = draw(st.lists(_host_specs, max_size=6))
    same_urls = [_url(sub, start_domain, path) for sub, path in same_specs]

    # Off-domain targets: a registrable domain different from the start's,
    # combined with arbitrary subdomains/paths so an off-domain host that
    # merely *looks* similar is still correctly excluded.
    off_domains = draw(
        st.lists(
            _registrable_domains().filter(lambda d: d != start_domain),
            max_size=6,
        )
    )
    off_specs = draw(
        st.lists(_host_specs, min_size=len(off_domains), max_size=max(len(off_domains), 1))
    )
    off_urls = [
        _url(sub, dom, path)
        for dom, (sub, path) in zip(off_domains, off_specs)
    ]

    # De-duplicate while preserving order; drop any off URL that happens to
    # collide with the start or a same-domain URL string (registrable domains
    # differ, so this is defensive only).
    same_unique: list[str] = []
    for u in same_urls:
        if u not in same_unique:
            same_unique.append(u)
    known = {start_url, *same_unique}
    off_unique: list[str] = []
    for u in off_urls:
        if u not in known and u not in off_unique:
            off_unique.append(u)

    # Interleave same-domain and off-domain links on the start page so the mix
    # is genuine rather than grouped.
    interleaved: list[str] = []
    for i in range(max(len(same_unique), len(off_unique))):
        if i < len(same_unique):
            interleaved.append(same_unique[i])
        if i < len(off_unique):
            interleaved.append(off_unique[i])

    pages: dict[str, str] = {start_url: _page(interleaved)}
    # Same-domain targets are reachable leaf pages (present in the fetcher).
    for u in same_unique:
        pages.setdefault(u, _page([]))
    # Off-domain URLs are deliberately absent from the fetcher: if the crawler
    # ever fetched one it would 404 AND be recorded in ``requested`` — either
    # way the assertions below catch the violation.

    return start_url, FakeFetcher(pages), off_unique


# --- Property -----------------------------------------------------------------


@given(scenario=_scenarios())
def test_retrieval_stays_within_the_same_registrable_domain(
    scenario: tuple[str, FakeFetcher, list[str]],
) -> None:
    """Every retrieved page shares the start's registrable domain; no off-domain
    URL is ever fetched (Req 1.2, 1.3)."""
    start_url, fetcher, off_urls = scenario
    crawler = _crawler(fetcher)

    # A generous cap so the crawl is never truncated before exploring the whole
    # generated in-domain graph — isolating the same-domain restriction from
    # the max_pages bound (which Property 2 covers).
    pages = crawler.crawl_site(start_url, 10000)

    start_reg = registrable_domain(start_url)

    # (1) Every returned page is on the same registrable domain (Req 1.2).
    for page in pages:
        assert same_registrable_domain(page.url, start_url), (
            f"retrieved off-domain page {page.url!r}; "
            f"start registrable domain is {start_reg!r}"
        )
        assert registrable_domain(page.url) == start_reg

    # (2) The fetcher was never asked to retrieve an off-domain URL — exclusion
    # happens before retrieval (Req 1.3).
    for requested in fetcher.requested:
        assert same_registrable_domain(requested, start_url), (
            f"fetcher was asked to retrieve off-domain URL {requested!r}"
        )
    off_domain_set = set(off_urls)
    assert off_domain_set.isdisjoint(fetcher.requested)

    # The start URL itself is always retrieved (sanity: the crawl did run).
    assert any(page.url == start_url for page in pages)
