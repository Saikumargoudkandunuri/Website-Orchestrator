"""The Fixture_Site for the end-to-end proof of the loop (Requirement 11).

This module defines a small, self-contained set of local HTML pages — the
Fixture_Site — that seeds **at least one of every issue type** the Check_Engine
detects end-to-end, plus **exactly one** resolvable missing-alt-text image that
becomes the single Auto_Applicable_Fix (Req 11.3, 11.4):

============================  ============================================
Seeded issue                  Where
============================  ============================================
missing title                 ``/no-title`` — a page with no ``<title>``
missing meta description      ``/no-meta`` — no ``<meta name=description>``
missing alt text (resolvable) ``/gallery`` — one ``<img>`` with no ``alt``
broken link                   ``/blog`` — an ``<a>`` to a 4xx target
redirect chain                ``/deals`` — redirects 3 hops to ``/deals-final``
============================  ============================================

The single missing-alt image (``hero-banner.png``) is the **only** image on the
whole site that lacks alt text, and it is the only image seeded in the mocked
WordPress media store, so after :func:`crawl_fixture` resolves media ids exactly
one image carries a resolvable ``media_id``. The Fix_Generator therefore produces
exactly one auto-applicable ``update_alt_text`` fix (Req 5.3, 11.4); every other
detected issue maps to a report-only fix.

Resolving the auto-applicable image (the media-id gap)
------------------------------------------------------
The Fix_Generator produces an auto-applicable fix only when an image's
``media_id`` is resolvable, but the Crawler parses HTML and always leaves
``media_id=None`` (it has no way to know the WordPress media id from markup).
The harness closes that gap explicitly in :func:`resolve_media_ids`: it matches
each crawled image's filename against the mocked WordPress media store (keyed by
the basename of each media item's ``source_url``) and stamps the matching
``media_id`` onto the image. Because only ``hero-banner.png`` is seeded in the
media store, exactly one image becomes resolvable — a clean, data-driven mapping
rather than crawler magic.

Everything here is local and in-memory: the Crawler is wired with the in-memory
:class:`~e2e.fetcher.InMemoryFetcher`, an allow-all robots fetcher, and the
in-memory :class:`~e2e.fetcher.InMemoryLinkProber`, so no request leaves
localhost (Req 11.1) and no live site is contacted (Req 2.5).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlsplit

from core.interfaces import WPMedia, WPPage
from core.types import CrawledPage, IssueType, LinkStatus
from crawler.crawler import Crawler
from crawler.fetcher import FetchResponse
from crawler.robots import RobotsGate

from e2e.fetcher import InMemoryFetcher, InMemoryLinkProber, allow_all_robots_fetcher
from e2e.mock_wordpress import MockWordPressClient

__all__ = [
    "FixtureSite",
    "build_fixture_site",
    "make_crawler",
    "make_mock_wordpress",
    "crawl_fixture",
    "resolve_media_ids",
    "probe_link_statuses",
    "BASE_URL",
    "START_URL",
    "SEEDED_ISSUE_TYPES",
    "RESOLVABLE_IMAGE_FILENAME",
    "RESOLVABLE_MEDIA_ID",
]

#: The Fixture_Site origin. Everything is under this single registrable domain so
#: the Crawler stays in-domain; nothing here is ever contacted over the network.
BASE_URL = "http://fixture.local"

#: Where the crawl starts.
START_URL = f"{BASE_URL}/"

#: The filename of the single resolvable missing-alt image (the one that becomes
#: the Auto_Applicable_Fix, Req 11.4).
RESOLVABLE_IMAGE_FILENAME = "hero-banner.png"

#: The mocked WordPress media id that image resolves to.
RESOLVABLE_MEDIA_ID = 101

#: The mocked WordPress page id used for the report-only page-content example.
SAMPLE_PAGE_ID = 201

#: The off-domain link seeded as broken (probed as 404).
BROKEN_LINK_URL = "http://external.example/missing-article"

#: The issue types the Fixture_Site is built to seed end-to-end (Req 11.3). The
#: Check_Engine may additionally flag report-only types (thin content, missing
#: schema); those are expected extras and never auto-applicable.
SEEDED_ISSUE_TYPES: frozenset[IssueType] = frozenset(
    {
        IssueType.MISSING_TITLE,
        IssueType.MISSING_META_DESCRIPTION,
        IssueType.MISSING_ALT_TEXT,
        IssueType.BROKEN_LINKS,
        IssueType.REDIRECT_CHAINS,
    }
)


# --- HTML builders ------------------------------------------------------------


def _para(words: int, word: str = "content") -> str:
    """Return a ``<p>`` with ``words`` words so a page clears the thin-content
    threshold when we do not want thin content to be part of the assertion."""
    return "<p>" + " ".join([word] * words) + "</p>"


def _complete_body(heading: str) -> str:
    """A body with enough words to avoid thin-content noise."""
    return f"<h1>{heading}</h1>\n{_para(320, 'word')}"


def _home_html() -> str:
    """The home page: complete, with an image that HAS alt text (no issue), and
    links to every seeded page so the crawl discovers them."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <title>Fixture Home</title>
  <meta name="description" content="The fixture site home page.">
  <script type="application/ld+json">{{"@context":"https://schema.org"}}</script>
</head>
<body>
  <img src="/wp-content/uploads/logo.svg" alt="Site logo">
  <nav>
    <a href="/no-title">Missing title page</a>
    <a href="/no-meta">Missing meta page</a>
    <a href="/gallery">Gallery</a>
    <a href="/blog">Blog</a>
    <a href="/deals">Deals</a>
  </nav>
  {_complete_body("Welcome")}
</body>
</html>"""


def _no_title_html() -> str:
    """Seeds a missing-title issue: no ``<title>`` element (Req 11.3)."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta name="description" content="A page that is missing its title tag.">
  <script type="application/ld+json">{{"@context":"https://schema.org"}}</script>
</head>
<body>{_complete_body("No Title Here")}</body>
</html>"""


def _no_meta_html() -> str:
    """Seeds a missing-meta-description issue: no ``<meta name=description>``."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <title>No Meta Description</title>
  <script type="application/ld+json">{{"@context":"https://schema.org"}}</script>
</head>
<body>{_complete_body("No Meta")}</body>
</html>"""


def _gallery_html() -> str:
    """Seeds the single resolvable missing-alt-text image (Req 11.4).

    ``hero-banner.png`` is the ONLY image on the whole site missing ``alt`` and
    the only image seeded in the mocked media store, so it becomes the one
    Auto_Applicable_Fix. A second image here carries alt text (no issue)."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <title>Gallery</title>
  <meta name="description" content="An image gallery page.">
  <script type="application/ld+json">{{"@context":"https://schema.org"}}</script>
</head>
<body>
  <img src="/wp-content/uploads/{RESOLVABLE_IMAGE_FILENAME}">
  <img src="/wp-content/uploads/team-photo.jpg" alt="The team">
  {_complete_body("Gallery")}
</body>
</html>"""


def _blog_html() -> str:
    """Seeds a broken-link issue: an anchor to an off-domain 4xx target."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <title>Blog</title>
  <meta name="description" content="The blog index.">
  <script type="application/ld+json">{{"@context":"https://schema.org"}}</script>
</head>
<body>
  <a href="{BROKEN_LINK_URL}">An article that no longer exists</a>
  {_complete_body("Blog")}
</body>
</html>"""


def _deals_final_html() -> str:
    """The terminal page of the redirect chain seeded at ``/deals``."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <title>Deals</title>
  <meta name="description" content="Current deals.">
  <script type="application/ld+json">{{"@context":"https://schema.org"}}</script>
</head>
<body>{_complete_body("Deals")}</body>
</html>"""


# --- Fixture assembly ---------------------------------------------------------


@dataclass
class FixtureSite:
    """A fully-assembled, in-memory Fixture_Site for the end-to-end proof.

    Bundles everything the harness needs to drive the loop locally: the seeded
    fetch responses (pages + redirect hops), the seeded link statuses, the
    allow-all robots fetcher, and the mocked WordPress seed (pages + media) with
    the filename -> media-id map used to resolve the one auto-applicable image.
    """

    start_url: str
    fetch_responses: dict[str, FetchResponse]
    link_statuses: dict[str, int | None]
    wp_pages: dict[int, WPPage]
    wp_media: dict[int, WPMedia]
    #: basename(source_url) -> media id, used by :func:`resolve_media_ids`.
    media_id_by_filename: dict[str, int] = field(default_factory=dict)


def _redirect(location: str, *, status: int = 301) -> FetchResponse:
    """A single, non-following redirect response carrying ``Location``."""
    return FetchResponse(
        url="", final_url="", status_code=status, html="", location=location
    )


def _ok(url: str, html: str) -> FetchResponse:
    """A terminal 200 response serving ``html`` for ``url``."""
    return FetchResponse(url=url, final_url=url, status_code=200, html=html)


def build_fixture_site() -> FixtureSite:
    """Assemble the Fixture_Site (Req 11.1-11.4).

    Seeds fetch responses for every page and the ``/deals`` -> ``/deals-final``
    3-hop redirect chain, marks the off-domain blog link broken (404), and seeds
    the mocked WordPress media store with the single resolvable image.
    """
    fetch_responses: dict[str, FetchResponse] = {
        f"{BASE_URL}/": _ok(f"{BASE_URL}/", _home_html()),
        f"{BASE_URL}/no-title": _ok(f"{BASE_URL}/no-title", _no_title_html()),
        f"{BASE_URL}/no-meta": _ok(f"{BASE_URL}/no-meta", _no_meta_html()),
        f"{BASE_URL}/gallery": _ok(f"{BASE_URL}/gallery", _gallery_html()),
        f"{BASE_URL}/blog": _ok(f"{BASE_URL}/blog", _blog_html()),
        # A 3-hop redirect chain: /deals -> /deals-1 -> /deals-2 -> /deals-final.
        # The recorded chain has 4 URLs (>= REDIRECT_CHAIN_THRESHOLD of 3).
        f"{BASE_URL}/deals": _redirect(f"{BASE_URL}/deals-1", status=301),
        f"{BASE_URL}/deals-1": _redirect(f"{BASE_URL}/deals-2", status=302),
        f"{BASE_URL}/deals-2": _redirect(f"{BASE_URL}/deals-final", status=302),
        f"{BASE_URL}/deals-final": _ok(
            f"{BASE_URL}/deals-final", _deals_final_html()
        ),
    }

    # Only the off-domain blog link is broken; every other probed link defaults
    # to 200 in the InMemoryLinkProber.
    link_statuses: dict[str, int | None] = {BROKEN_LINK_URL: 404}

    # Mocked WordPress seed: one media item (the resolvable image, currently with
    # NO alt text) and one sample page for the report-only content example.
    media_source = f"{BASE_URL}/wp-content/uploads/{RESOLVABLE_IMAGE_FILENAME}"
    wp_media = {
        RESOLVABLE_MEDIA_ID: WPMedia(
            id=RESOLVABLE_MEDIA_ID,
            alt_text="",  # missing alt text — the BEFORE value for rollback
            source_url=media_source,
        )
    }
    wp_pages = {
        SAMPLE_PAGE_ID: WPPage(
            id=SAMPLE_PAGE_ID,
            content="<p>Original page content.</p>",
            title="Sample Page",
            link=f"{BASE_URL}/sample",
        )
    }
    media_id_by_filename = {
        _basename(item.source_url): mid
        for mid, item in wp_media.items()
        if item.source_url
    }

    return FixtureSite(
        start_url=START_URL,
        fetch_responses=fetch_responses,
        link_statuses=link_statuses,
        wp_pages=wp_pages,
        wp_media=wp_media,
        media_id_by_filename=media_id_by_filename,
    )


# --- Wiring helpers -----------------------------------------------------------


def make_crawler(site: FixtureSite) -> Crawler:
    """Build a :class:`~crawler.crawler.Crawler` wired to the in-memory seams.

    The fetcher, robots gate, and link prober are all in-memory, so the crawl is
    network-free (Req 11.1, 2.5). ``sleep`` is a no-op so the per-host rate-limit
    pacing does not slow the test down (the pacing logic still runs; it simply
    never waits on the wall clock).
    """
    return Crawler(
        fetcher=InMemoryFetcher(site.fetch_responses),
        robots_gate=RobotsGate(allow_all_robots_fetcher),
        link_prober=InMemoryLinkProber(site.link_statuses),
        sleep=lambda _seconds: None,
    )


def make_mock_wordpress(site: FixtureSite) -> MockWordPressClient:
    """Build the mocked WordPress client seeded from ``site`` (Req 11.2)."""
    return MockWordPressClient(
        pages=dict(site.wp_pages),
        media=dict(site.wp_media),
    )


def resolve_media_ids(pages: list[CrawledPage], site: FixtureSite) -> int:
    """Stamp resolvable WordPress ``media_id``s onto crawled images (Req 11.4).

    The Crawler leaves every image ``media_id=None``. This closes the gap by
    matching each image's filename against the mocked media store
    (``site.media_id_by_filename``) and stamping the matching id in place. Only
    images whose filename is seeded in the media store become resolvable, so with
    the default fixture exactly one image (``hero-banner.png``) is resolved.

    Returns the number of images resolved (1 for the default fixture), so callers
    can assert the invariant.
    """
    resolved = 0
    for page in pages:
        for image in page.images:
            media_id = site.media_id_by_filename.get(image.filename)
            if media_id is not None:
                image.media_id = media_id
                resolved += 1
    return resolved


def probe_link_statuses(pages: list[CrawledPage], crawler: Crawler) -> None:
    """Populate each page's link statuses via ``crawler.check_link_status``.

    The crawl records anchors with ``status_code=None``; broken-link detection
    keys on the observed status, so the harness probes every link through the
    in-memory prober and replaces each :class:`~core.types.LinkStatus` in place
    with the observed result (Req 2.3, 4.5). Stays network-free (the prober is
    in-memory).
    """
    for page in pages:
        page.links = [crawler.check_link_status(link.url) for link in page.links]


def crawl_fixture(
    site: FixtureSite | None = None,
    *,
    crawler: Crawler | None = None,
    max_pages: int = 100,
) -> tuple[list[CrawledPage], Crawler, FixtureSite]:
    """Crawl the Fixture_Site and return loop-ready pages (Req 11.1-11.4).

    Runs the real :class:`~crawler.crawler.Crawler` over the in-memory seams,
    then post-processes the crawled pages so they are ready for the Check_Engine
    and Fix_Generator:

    1. probes every link so broken links carry their observed status;
    2. resolves the one auto-applicable image's ``media_id``.

    Returns the crawled pages, the crawler used (its in-memory fetcher/prober can
    be inspected as spies), and the fixture site.
    """
    site = site if site is not None else build_fixture_site()
    crawler = crawler if crawler is not None else make_crawler(site)

    pages = crawler.crawl_site(site.start_url, max_pages)
    probe_link_statuses(pages, crawler)
    resolve_media_ids(pages, site)
    return pages, crawler, site


def _basename(url: str) -> str:
    """Return the trailing filename component of ``url``."""
    path = urlsplit(url).path
    return path.rsplit("/", 1)[-1] if path else ""
