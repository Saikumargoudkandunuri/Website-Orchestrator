"""Crawler — polite, safe, same-domain page retrieval (Req 1).

This module implements :class:`Crawler`, the concrete
:class:`core.interfaces.CrawlerPort`. Task 5.1 establishes the crawl skeleton
and the two invariants that must hold before anything is retrieved:

* **Input validation first (Req 1.1, 1.5).** A malformed ``start_url`` (not a
  valid ``http``/``https`` URL) or a ``max_pages`` outside the inclusive range
  ``[1, 10000]`` raises :class:`~core.exceptions.InvalidCrawlRequest` and
  nothing is retrieved.
* **Same-domain retrieval (Req 1.2, 1.3, 1.4).** Retrieval starts at
  ``start_url`` and follows only links on the same registrable domain (via
  :func:`core.utils.same_registrable_domain`); out-of-domain URLs are excluded
  from retrieval. Retrieval stops once ``max_pages`` pages have been retrieved.

The crawl performs a breadth-first traversal from ``start_url``, retrieving each
in-domain page through an injectable :class:`~crawler.fetcher.Fetcher`, parsing
its HTML with BeautifulSoup over the ``lxml`` parser (never executing
JavaScript, Req 1.13), and discovering further links from anchor tags.

Before any URL is retrieved (including ``start_url``) the crawl consults the
origin's ``robots.txt`` through an injectable :class:`~crawler.robots.RobotsGate`
and honors its directives (Req 1.6): a disallowed URL is excluded (Req 1.8), and
a URL whose ``robots.txt`` cannot be retrieved is excluded by failing closed
(Req 1.7).

Between requests to a single host the crawl enforces a polite pacing policy
(task 5.3, Req 1.9-1.12): the configured ``Rate_Limit`` is a hard floor
(default 1000 ms) that is never reduced to crawl faster; while a host's observed
response time exceeds the degradation threshold (default 2000 ms) the delay is
raised to at least double the floor; and a request whose observed duration
exceeds the per-request timeout (default 30 s) is abandoned. Timing goes through
an injectable ``clock`` and an injectable ``sleep`` so tests stay deterministic
and network-free.

HTTP redirects are recorded rather than silently followed (task 5.4, Req 2.1,
2.2). The injected :class:`~crawler.fetcher.Fetcher` performs a single request
per call and never follows redirects; the crawl walks a redirect chain itself,
recording each hop in order, and stops at the configurable redirect hard cap
(default :data:`core.constants.REDIRECT_HARD_CAP`, clamped to the inclusive
bounds ``[1, 50]``), marking the recorded chain ``truncated``. Because the walk
is bounded by the cap it can never loop indefinitely, even on a cyclic redirect
graph.

Link-status probing (task 5.5, Req 2.3, 2.4) observes a single link's HTTP
status through an injectable :class:`~crawler.fetcher.LinkProber` under a default
10 s timeout (:data:`core.constants.LINK_TIMEOUT_S`). Any observed status makes
the link reachable; a timeout or network failure yields an unreachable
:class:`~core.types.LinkStatus` without raising.

Depends only on Core_Package; cross-subsystem contracts come from the Protocols
and typed records published there (Req 12, 15).
"""

from __future__ import annotations

import time
from collections import deque
from datetime import datetime
from typing import Callable
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from core.constants import (
    DEFAULT_RATE_LIMIT_MS,
    DEGRADATION_THRESHOLD_MS,
    REDIRECT_HARD_CAP,
    REQUEST_TIMEOUT_S,
)
from core.exceptions import InvalidCrawlRequest
from core.types import CrawledPage, ImageRef, LinkStatus, RedirectChain
from core.utils import normalize_url, same_registrable_domain, utc_now

from crawler.fetcher import (
    Fetcher,
    FetchResponse,
    HttpxFetcher,
    HttpxLinkProber,
    LinkProber,
)
from crawler.robots import RobotsGate

__all__ = [
    "Crawler",
    "MIN_PAGES",
    "MAX_PAGES",
    "MIN_REDIRECT_CAP",
    "MAX_REDIRECT_CAP",
]

#: Inclusive lower/upper bounds for ``max_pages`` (Req 1.1, 1.5).
MIN_PAGES: int = 1
MAX_PAGES: int = 10000

#: Inclusive lower/upper bounds for the redirect hard cap (Req 2.2). The
#: configured cap is clamped into this range; the default is
#: :data:`core.constants.REDIRECT_HARD_CAP`.
MIN_REDIRECT_CAP: int = 1
MAX_REDIRECT_CAP: int = 50

#: URL schemes the crawler will retrieve. Anchors using any other scheme
#: (``mailto:``, ``tel:``, ``javascript:``, ``data:`` ...) are never retrieved.
_RETRIEVABLE_SCHEMES: frozenset[str] = frozenset({"http", "https"})

#: The HTTP status codes treated as redirects the crawler records and follows
#: (Req 2.1). Any other status is terminal.
_REDIRECT_STATUSES: frozenset[int] = frozenset({301, 302, 303, 307, 308})

#: The HTML parser BeautifulSoup uses. ``lxml`` is fast and lenient and never
#: executes JavaScript (Req 1.13).
_HTML_PARSER: str = "lxml"


class Crawler:
    """Retrieve same-domain pages politely and safely (Req 1).

    Implements :class:`core.interfaces.CrawlerPort`. External boundaries are
    injected so the crawl logic stays pure and fully testable without a network:

    Args:
        fetcher: The HTTP boundary used to retrieve a URL. Defaults to
            :class:`~crawler.fetcher.HttpxFetcher`; tests inject an in-memory
            fake so no live site is contacted (Req 2.5).
        robots_gate: The gate consulted before every fetch to honor the origin's
            ``robots.txt`` (Req 1.6-1.8). Defaults to a
            :class:`~crawler.robots.RobotsGate` over the network; tests inject a
            gate backed by an in-memory ``robots.txt`` fetcher so no live site is
            contacted.
        clock: A callable returning the current UTC time. It stamps
            ``crawled_at`` on each :class:`~core.types.CrawledPage` and measures
            per-host request pacing and response durations (Req 1.9-1.12).
            Defaults to :func:`core.utils.utc_now`; tests inject a fake clock so
            timing is deterministic without real waiting.
        sleep: A callable that pauses for the given number of seconds, used to
            honor the per-host delay between requests. Defaults to
            :func:`time.sleep`; tests inject a recorder so the enforced delays
            can be asserted without real waiting.
        rate_limit_ms: The per-host delay floor in milliseconds, treated as a
            correctness constraint and never reduced to crawl faster (Req 1.9,
            1.10). Defaults to :data:`core.constants.DEFAULT_RATE_LIMIT_MS`.
        degradation_threshold_ms: The observed-response-time threshold in
            milliseconds above which the per-host delay is doubled (Req 1.11).
            Defaults to :data:`core.constants.DEGRADATION_THRESHOLD_MS`.
        request_timeout_s: The per-request timeout in seconds; a request whose
            observed duration exceeds it is abandoned (Req 1.12). Defaults to
            :data:`core.constants.REQUEST_TIMEOUT_S`.
        redirect_hard_cap: The maximum number of HTTP redirects to follow for a
            single starting URL before the crawl stops and marks the recorded
            Redirect_Chain ``truncated`` (Req 2.2). Clamped into the inclusive
            bounds ``[MIN_REDIRECT_CAP, MAX_REDIRECT_CAP]`` = ``[1, 50]``.
            Defaults to :data:`core.constants.REDIRECT_HARD_CAP` (10).
        link_prober: The boundary used by :meth:`check_link_status` to observe a
            single link's HTTP status (Req 2.3, 2.4). A callable that returns the
            observed integer status code and raises on a timeout or network
            failure. Defaults to :class:`~crawler.fetcher.HttpxLinkProber` with a
            :data:`core.constants.LINK_TIMEOUT_S` (10 s) timeout; tests inject an
            in-memory callable so no live site is contacted (Req 2.5).
    """

    def __init__(
        self,
        fetcher: Fetcher | None = None,
        *,
        robots_gate: RobotsGate | None = None,
        clock: Callable[[], datetime] = utc_now,
        sleep: Callable[[float], None] = time.sleep,
        rate_limit_ms: float = DEFAULT_RATE_LIMIT_MS,
        degradation_threshold_ms: float = DEGRADATION_THRESHOLD_MS,
        request_timeout_s: float = REQUEST_TIMEOUT_S,
        redirect_hard_cap: int = REDIRECT_HARD_CAP,
        link_prober: LinkProber | None = None,
    ) -> None:
        self._fetcher: Fetcher = fetcher if fetcher is not None else HttpxFetcher()
        self._robots_gate: RobotsGate = (
            robots_gate if robots_gate is not None else RobotsGate()
        )
        self._link_prober: LinkProber = (
            link_prober if link_prober is not None else HttpxLinkProber()
        )
        self._clock = clock
        self._sleep = sleep
        self._rate_limit_ms = rate_limit_ms
        self._degradation_threshold_ms = degradation_threshold_ms
        self._request_timeout_s = request_timeout_s
        # Clamp the redirect hard cap into the required bounds so an
        # out-of-range configuration can never disable the loop guard or make
        # it degenerate (Req 2.2).
        self._redirect_hard_cap = _bounded_redirect_cap(redirect_hard_cap)

        # Per-host pacing state (keyed by lower-cased netloc):
        #   _last_request_at: when the host was last contacted, so the next
        #       request waits out the remaining delay floor.
        #   _host_degraded: whether the host's last observed response time
        #       exceeded the degradation threshold, doubling the next delay.
        self._last_request_at: dict[str, datetime] = {}
        self._host_degraded: dict[str, bool] = {}

    # -- Public API (CrawlerPort) ---------------------------------------------

    def crawl_site(self, start_url: str, max_pages: int) -> list[CrawledPage]:
        """Crawl from ``start_url`` within its registrable domain (Req 1.1-1.5).

        Validates the request first: an invalid ``start_url`` or an out-of-range
        ``max_pages`` raises :class:`~core.exceptions.InvalidCrawlRequest`
        before any retrieval occurs (Req 1.5). Otherwise retrieves pages
        breadth-first starting at ``start_url``, following only same-domain
        links (Req 1.2, 1.3), and stops once ``max_pages`` pages have been
        retrieved (Req 1.4).

        Returns:
            One :class:`~core.types.CrawledPage` per retrieved URL, in retrieval
            order.
        """
        self._validate_request(start_url, max_pages)

        start_normalized = normalize_url(start_url)
        # ``seen`` guards against re-queuing a URL (and thus loops); it holds
        # every URL ever enqueued, not just those already retrieved.
        seen: set[str] = {start_normalized}
        queue: deque[str] = deque([start_normalized])
        pages: list[CrawledPage] = []

        while queue and len(pages) < max_pages:
            current_url = queue.popleft()

            # Consult robots.txt before retrieving (Req 1.6). A disallowed URL
            # (Req 1.8) or one whose robots.txt cannot be retrieved (fail closed,
            # Req 1.7) is excluded — never passed to the page fetcher. This
            # applies to ``start_url`` as well.
            if not self._robots_gate.allowed(current_url):
                continue

            response = self._fetch_following_redirects(current_url)
            if response is None:
                # Retrieval failed, timed out, or was otherwise abandoned; skip
                # this URL and continue the crawl (Req 1.12).
                continue

            page = self._build_page(current_url, response)
            pages.append(page)

            # Discover further work: enqueue only unseen, same-domain links
            # (Req 1.2, 1.3). Out-of-domain links are recorded on the page but
            # never retrieved.
            for link in page.links:
                candidate = normalize_url(link.url)
                if not candidate or candidate in seen:
                    continue
                if not same_registrable_domain(start_url, candidate):
                    continue
                seen.add(candidate)
                queue.append(candidate)

        return pages

    def check_link_status(self, url: str) -> LinkStatus:
        """Return the observed HTTP status of ``url`` (Req 2.3, 2.4).

        Issues a single request for ``url`` through the injected
        :class:`~crawler.fetcher.LinkProber` under a default timeout of
        :data:`core.constants.LINK_TIMEOUT_S` (10 s, configurable on the prober):

        * On a response, the observed integer status code is reported and the
          link is ``reachable`` — *any* HTTP status counts as an observation,
          since a server responded (Req 2.3).
        * On a timeout or network failure the prober raises; this method catches
          it and returns an unreachable :class:`~core.types.LinkStatus`
          (``status_code=None``, ``reachable=False``) without raising (Req 2.4).

        Under automated tests the prober is an in-memory fake, so this operates
        only against local fixtures and never contacts a live site (Req 2.5).
        """
        try:
            status_code = self._link_prober(url)
        except Exception:
            # A timeout or network failure yields an unreachable result rather
            # than propagating (Req 2.4).
            return LinkStatus(url=url, status_code=None, reachable=False)
        # A response was observed — any HTTP status means the link is reachable.
        return LinkStatus(url=url, status_code=int(status_code), reachable=True)

    # -- Validation -----------------------------------------------------------

    def _validate_request(self, start_url: str, max_pages: int) -> None:
        """Reject a malformed ``start_url`` or out-of-range ``max_pages`` (Req 1.5).

        Raises:
            InvalidCrawlRequest: If ``start_url`` is not a valid http/https URL
                or ``max_pages`` is not an int in ``[1, 10000]``. Raised before
                any retrieval, so nothing is fetched.
        """
        if not _is_valid_start_url(start_url):
            raise InvalidCrawlRequest(
                f"start_url is not a valid http/https URL: {start_url!r}"
            )
        # bool is a subclass of int; reject it explicitly so True/False are not
        # silently accepted as 1/0.
        if isinstance(max_pages, bool) or not isinstance(max_pages, int):
            raise InvalidCrawlRequest(
                f"max_pages must be an integer in [{MIN_PAGES}, {MAX_PAGES}]"
            )
        if not (MIN_PAGES <= max_pages <= MAX_PAGES):
            raise InvalidCrawlRequest(
                f"max_pages must be in [{MIN_PAGES}, {MAX_PAGES}], got {max_pages}"
            )

    # -- Retrieval / parsing --------------------------------------------------

    def _paced_fetch(self, url: str) -> FetchResponse | None:
        """Fetch ``url`` under the per-host pacing policy (Req 1.9-1.12).

        Enforces the per-host delay before contacting the host, measures the
        observed response duration with the injected clock, and:

        * returns ``None`` if the fetch raises (a failure is skipped, not fatal);
        * returns ``None`` if the observed duration exceeds the per-request
          timeout — the request is abandoned (Req 1.12);
        * otherwise returns the :class:`~crawler.fetcher.FetchResponse`.

        Regardless of outcome the host's last-contact time and degradation state
        are updated so subsequent requests to the same host are paced correctly.
        Robots.txt gating (task 5.2) happens in :meth:`crawl_site` before this is
        called, so a disallowed or robots-unavailable URL never reaches here.
        """
        host = _host_of(url)
        self._respect_rate_limit(host)

        start = self._clock()
        try:
            response = self._fetcher.fetch(url)
        except Exception:
            # A failed request still counts as contacting the host: record the
            # time so the next request to this host is paced from now.
            self._last_request_at[host] = self._clock()
            return None

        end = self._clock()
        self._last_request_at[host] = end

        duration_ms = _elapsed_ms(start, end)
        # A host whose observed response time exceeds the degradation threshold
        # has its next delay doubled; one that recovers returns to the floor
        # (Req 1.11).
        self._host_degraded[host] = duration_ms > self._degradation_threshold_ms

        # Abandon a request that exceeded the per-request timeout (Req 1.12).
        if duration_ms > self._request_timeout_s * 1000.0:
            return None

        return response

    def _fetch_following_redirects(self, url: str) -> FetchResponse | None:
        """Retrieve ``url``, walking and recording its Redirect_Chain (Req 2.1, 2.2).

        Each hop is retrieved through :meth:`_paced_fetch`, so per-host pacing,
        degradation backoff, and the per-request timeout (Req 1.9-1.12) apply to
        every hop. Because the injected fetcher never follows redirects, this
        method walks the chain itself:

        * A response with a redirect status (301, 302, 303, 307, 308) and a
          usable ``Location`` is recorded as a hop and followed (Req 2.1). A
          redirect without a usable target is treated as terminal.
        * Following stops once :data:`self._redirect_hard_cap` redirects have
          been followed and the next response is still a redirect; the chain is
          recorded up to that point and marked ``truncated`` (Req 2.2). The
          bound guarantees the walk terminates even on a cyclic redirect graph.

        Returns:
            An assembled :class:`~crawler.fetcher.FetchResponse` whose
            ``final_url`` is the last URL traversed, ``redirect_hops`` are the
            ordered redirecting URLs (excluding ``final_url``), and ``truncated``
            reflects whether the hard cap was hit; or ``None`` if any hop was
            abandoned (failure or timeout, Req 1.12).
        """
        current = url
        traversed: list[str] = []
        truncated = False
        followed = 0
        response: FetchResponse | None = None

        while True:
            response = self._paced_fetch(current)
            if response is None:
                # A failed or timed-out hop abandons the whole retrieval.
                return None
            traversed.append(current)

            if response.status_code not in _REDIRECT_STATUSES:
                # Terminal (non-redirect) response: the chain ends here.
                break

            target = _resolve_redirect_target(current, response.location)
            if target is None:
                # A redirect we cannot follow (no/relative-invalid Location or a
                # non-http(s) target) ends the chain at the current URL.
                break

            if followed >= self._redirect_hard_cap:
                # The cap has been reached and the chain would continue: stop
                # following and mark the recorded chain truncated (Req 2.2).
                truncated = True
                break

            followed += 1
            current = target

        # ``traversed`` is [start, hop1, ..., final]; the final entry is the
        # final_url and the rest are the recorded redirect hops (Req 2.1).
        return FetchResponse(
            url=url,
            final_url=traversed[-1],
            status_code=response.status_code,
            html=response.html,
            location=None,
            redirect_hops=traversed[:-1],
            truncated=truncated,
        )

    def _respect_rate_limit(self, host: str) -> None:
        """Sleep out any remaining per-host delay before contacting ``host``.

        The delay floor is the configured ``Rate_Limit`` (never reduced for
        speed, Req 1.9, 1.10); while the host is degraded it is at least doubled
        (Req 1.11). If enough time has already elapsed since the last request to
        this host, no sleep occurs.
        """
        last = self._last_request_at.get(host)
        if last is None:
            # First request to this host: nothing to wait for.
            return

        required_ms = self._required_delay_ms(host)
        elapsed_ms = _elapsed_ms(last, self._clock())
        remaining_ms = required_ms - elapsed_ms
        if remaining_ms > 0:
            self._sleep(remaining_ms / 1000.0)

    def _required_delay_ms(self, host: str) -> float:
        """Return the minimum delay before the next request to ``host`` (ms).

        This is the ``Rate_Limit`` floor, doubled while the host is degraded
        (Req 1.9-1.11). The floor is never reduced below the configured value.
        """
        if self._host_degraded.get(host, False):
            return 2.0 * self._rate_limit_ms
        return float(self._rate_limit_ms)

    def _build_page(self, url: str, response: FetchResponse) -> CrawledPage:
        """Build a :class:`~core.types.CrawledPage` from a fetch response.

        Parses the HTML with BeautifulSoup/``lxml`` (no JavaScript, Req 1.13)
        and extracts title, meta description, word count, anchor links, and
        images. The ordered Redirect_Chain the walk recorded (and whether it was
        truncated at the hard cap) is carried on ``response`` (Req 2.1, 2.2).
        """
        soup = BeautifulSoup(response.html or "", _HTML_PARSER)
        final_url = response.final_url or url

        return CrawledPage(
            url=url,
            final_url=final_url,
            status_code=response.status_code,
            title=_extract_title(soup),
            meta_description=_extract_meta_description(soup),
            word_count=_count_words(soup),
            html=response.html or "",
            links=_extract_links(soup, final_url),
            images=_extract_images(soup, final_url),
            redirect_chain=_build_redirect_chain(response),
            has_schema=_has_schema(soup),
            crawled_at=self._clock(),
        )


# --- URL validation -----------------------------------------------------------


def _is_valid_start_url(url: object) -> bool:
    """Return ``True`` when ``url`` is a syntactically valid http/https URL."""
    if not isinstance(url, str) or not url.strip():
        return False
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return False
    return parts.scheme.lower() in _RETRIEVABLE_SCHEMES and bool(parts.hostname)


# --- Timing / pacing helpers --------------------------------------------------


def _host_of(url: str) -> str:
    """Return the lower-cased host (netloc) of ``url`` for per-host pacing.

    Requests are paced per host (Req 1.9), so the host is the pacing key. An
    unparseable URL yields an empty string, which simply groups such URLs under
    a shared key rather than crashing.
    """
    if not isinstance(url, str):
        return ""
    return urlsplit(url).netloc.lower()


def _elapsed_ms(start: datetime, end: datetime) -> float:
    """Return the elapsed milliseconds between two clock readings.

    Never negative: a non-monotonic clock reading is clamped to ``0.0`` so a
    backwards jump can never fabricate a delay or a spurious timeout.
    """
    delta_ms = (end - start).total_seconds() * 1000.0
    return delta_ms if delta_ms > 0 else 0.0


# --- HTML extraction helpers --------------------------------------------------


def _extract_title(soup: BeautifulSoup) -> str | None:
    """Return the trimmed ``<title>`` text, or ``None`` when absent/empty."""
    if soup.title is None or soup.title.string is None:
        return None
    title = soup.title.string.strip()
    return title or None


def _extract_meta_description(soup: BeautifulSoup) -> str | None:
    """Return the ``<meta name="description">`` content, or ``None``."""
    tag = soup.find("meta", attrs={"name": "description"})
    if tag is None:
        return None
    content = tag.get("content")
    if not isinstance(content, str):
        return None
    content = content.strip()
    return content or None


def _count_words(soup: BeautifulSoup) -> int:
    """Return the number of whitespace-delimited words in the page text."""
    text = soup.get_text(separator=" ", strip=True)
    return len(text.split())


def _extract_links(soup: BeautifulSoup, base_url: str) -> list[LinkStatus]:
    """Discover anchor links, resolved against ``base_url`` (Req 1.2, 1.3).

    Returns one :class:`~core.types.LinkStatus` per retrievable (http/https)
    anchor target, de-duplicated in document order. Link *status* is not probed
    here — ``status_code`` is left ``None`` and ``reachable`` ``False`` until
    task 5.5 populates observed statuses; downstream broken-link detection keys
    on ``status_code`` rather than this placeholder.
    """
    links: list[LinkStatus] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        resolved = _resolve_href(base_url, anchor["href"])
        if resolved is None or resolved in seen:
            continue
        seen.add(resolved)
        links.append(LinkStatus(url=resolved, status_code=None, reachable=False))
    return links


def _extract_images(soup: BeautifulSoup, base_url: str) -> list[ImageRef]:
    """Extract image references and their existing alt text.

    Populates :class:`~core.types.ImageRef` for each ``<img>`` with a ``src``,
    deriving the filename from the resolved URL. The WordPress ``media_id`` is
    left unresolved here (resolved later by the Fix_Generator, Req 5.3/5.5).
    """
    images: list[ImageRef] = []
    for img in soup.find_all("img"):
        src = img.get("src")
        if not isinstance(src, str) or not src.strip():
            continue
        resolved = urljoin(base_url, src.strip())
        filename = _filename_from_url(resolved)
        if not filename:
            continue
        alt = img.get("alt")
        alt_text = alt.strip() if isinstance(alt, str) and alt.strip() else None
        images.append(ImageRef(media_id=None, filename=filename, alt_text=alt_text))
    return images


def _has_schema(soup: BeautifulSoup) -> bool:
    """Return ``True`` when the page carries JSON-LD schema markup."""
    return soup.find("script", attrs={"type": "application/ld+json"}) is not None


def _build_redirect_chain(response: FetchResponse) -> RedirectChain:
    """Build a :class:`~core.types.RedirectChain` from the fetch response.

    The chain is the ordered list of URLs actually traversed — the recorded
    redirecting URLs followed by the final URL (Req 2.1) — and carries the
    ``truncated`` flag set when the walk stopped at the redirect hard cap
    (Req 2.2). A response with no redirects yields an empty chain.
    """
    if not response.redirect_hops:
        return RedirectChain()
    hops = [*response.redirect_hops, response.final_url]
    return RedirectChain(hops=hops, truncated=response.truncated)


# --- URL helpers --------------------------------------------------------------


def _bounded_redirect_cap(cap: object) -> int:
    """Clamp ``cap`` into the inclusive bounds ``[1, 50]`` (Req 2.2).

    A non-integer or out-of-range value is coerced to a valid cap so the
    redirect-walk loop guard can never be disabled or made degenerate. ``bool``
    is rejected as a source value (it is an ``int`` subclass) and falls back to
    the default cap.
    """
    if isinstance(cap, bool) or not isinstance(cap, int):
        cap = REDIRECT_HARD_CAP
    return max(MIN_REDIRECT_CAP, min(MAX_REDIRECT_CAP, cap))


def _resolve_redirect_target(current_url: str, location: str | None) -> str | None:
    """Resolve a redirect ``Location`` against ``current_url`` (Req 2.1).

    Returns the absolute http/https target with any fragment stripped, or
    ``None`` when there is no usable location (missing/blank) or the target is
    not a retrievable http(s) URL — in which case the chain ends at
    ``current_url`` rather than being followed further.
    """
    if not isinstance(location, str) or not location.strip():
        return None
    resolved = urljoin(current_url, location.strip())
    parts = urlsplit(resolved)
    if parts.scheme.lower() not in _RETRIEVABLE_SCHEMES or not parts.hostname:
        return None
    return resolved.split("#", 1)[0]


def _resolve_href(base_url: str, href: str) -> str | None:
    """Resolve ``href`` against ``base_url``; return ``None`` if not retrievable.

    Fragment-only links and non-http(s) schemes (``mailto:``, ``tel:``,
    ``javascript:`` ...) are dropped. The fragment is stripped from the result
    so ``/a`` and ``/a#section`` are treated as one URL.
    """
    if not isinstance(href, str):
        return None
    href = href.strip()
    if not href or href.startswith("#"):
        return None

    resolved = urljoin(base_url, href)
    parts = urlsplit(resolved)
    if parts.scheme.lower() not in _RETRIEVABLE_SCHEMES:
        return None
    # Drop the fragment for stable comparison/enqueuing.
    return resolved.split("#", 1)[0]


def _filename_from_url(url: str) -> str:
    """Return the trailing filename component of ``url`` (path basename)."""
    path = urlsplit(url).path
    return path.rsplit("/", 1)[-1] if path else ""
