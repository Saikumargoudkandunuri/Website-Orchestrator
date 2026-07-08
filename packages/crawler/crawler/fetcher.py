"""Crawler HTTP boundary — an injectable fetch abstraction (Req 1.13, 2.5).

The :class:`Crawler` never talks to the network directly. Instead it depends on
the small :class:`Fetcher` Protocol defined here, receiving one concrete
implementation through its constructor. This keeps the crawl logic pure and
lets automated tests substitute an in-memory fake so property runs stay
network-free (Req 2.5) — no live site is ever contacted during tests.

Two pieces make up this boundary:

* :class:`FetchResponse` — the typed, transport-agnostic result of retrieving a
  single URL. A ``fetch`` performs a **single HTTP request and does not follow
  redirects**: when the response is an HTTP redirect the ``location`` target is
  reported so the :class:`~crawler.crawler.Crawler` can walk and record the
  Redirect_Chain itself, bounded by the redirect hard cap (Req 2.1, 2.2). The
  assembled result the crawler builds while walking a chain reuses this record,
  carrying the ordered ``redirect_hops`` traversed and whether the walk was
  ``truncated`` at the cap.
* :class:`Fetcher` — the ``Protocol`` the crawler depends on. The default
  :class:`HttpxFetcher` implements it over ``httpx`` with a bounded timeout, no
  redirect following, and no JavaScript execution (Req 1.13); tests inject their
  own callable/fake, including one that simulates a redirect chain.

Rate limiting (Req 1.9-1.11), the per-request timeout policy (Req 1.12), and
robots.txt gating (Req 1.6-1.8) live in the :class:`Crawler`/later tasks rather
than in the transport, so this boundary stays a thin, replaceable seam.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

import httpx

from core.constants import LINK_TIMEOUT_S, REQUEST_TIMEOUT_S

__all__ = [
    "FetchResponse",
    "Fetcher",
    "HttpxFetcher",
    "LinkProber",
    "HttpxLinkProber",
]


@dataclass(frozen=True, slots=True)
class FetchResponse:
    """The transport-agnostic result of retrieving a single URL.

    A single :meth:`Fetcher.fetch` performs one HTTP request and never follows
    redirects; on a redirect status it reports the ``location`` target so the
    crawler can walk the chain. The crawler also reuses this record to describe
    the *assembled* result of a completed walk, populating ``redirect_hops`` and
    ``truncated`` (Req 2.1, 2.2).

    Attributes:
        url: The URL that was requested (the start URL for an assembled walk).
        final_url: The URL of the final response — for a single hop this equals
            ``url``; for an assembled walk it is the last URL traversed (the
            terminal, non-redirect URL, or the URL the walk stopped at when
            truncated at the hard cap).
        status_code: The observed HTTP status code of the final response.
        html: The raw response body as text (never JavaScript-rendered,
            Req 1.13).
        location: For a single, non-following hop this is the raw ``Location``
            header of a redirect response (possibly relative), or ``None`` when
            the response is not a redirect. It is ``None`` on an assembled walk
            result.
        redirect_hops: The ordered list of URLs traversed by HTTP redirects,
            excluding ``final_url``. Empty for a single hop and when no redirect
            occurred. Populated by the crawler while recording a Redirect_Chain
            (Req 2.1).
        truncated: ``True`` when the crawler stopped following the chain because
            it reached the redirect hard cap (Req 2.2). Always ``False`` for a
            single hop.
    """

    url: str
    final_url: str
    status_code: int
    html: str = ""
    location: str | None = None
    redirect_hops: list[str] = field(default_factory=list)
    truncated: bool = False


@runtime_checkable
class Fetcher(Protocol):
    """The crawler's HTTP boundary: perform one request for ``url`` and return a
    :class:`FetchResponse`.

    Implementations perform a **single** HTTP request and MUST NOT follow
    redirects — a redirect response is returned as-is with its ``location``
    target populated, so the crawler can record the ordered Redirect_Chain and
    enforce the redirect hard cap itself (Req 2.1, 2.2). Implementations must
    not execute JavaScript (Req 1.13). The default implementation is
    :class:`HttpxFetcher`; tests supply an in-memory fake so no live site is
    contacted (Req 2.5).
    """

    def fetch(self, url: str) -> FetchResponse:
        """Perform one request for ``url`` and return its :class:`FetchResponse`."""
        ...


class HttpxFetcher:
    """Default :class:`Fetcher` backed by a synchronous ``httpx`` client.

    Retrieves a page over HTTP(S) with a single request, without executing
    JavaScript (Req 1.13) and **without following redirects**: the client is
    configured with ``follow_redirects=False`` so a redirect response is
    returned as-is with its ``Location`` header exposed as
    :attr:`FetchResponse.location`. The crawler walks and records the chain and
    enforces the redirect hard cap (Req 2.1, 2.2), which guarantees the crawl
    cannot loop indefinitely regardless of the server's redirect graph. A
    per-request timeout guards each call (Req 1.12); the default is
    :data:`core.constants.REQUEST_TIMEOUT_S`.

    The client is created lazily on first use so simply constructing a
    :class:`Crawler` never opens a network resource — important for tests, which
    inject their own fake fetcher and never touch this class.
    """

    def __init__(
        self,
        *,
        timeout_s: float = REQUEST_TIMEOUT_S,
        client: httpx.Client | None = None,
    ) -> None:
        self._timeout_s = timeout_s
        self._client = client

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                follow_redirects=False,
                timeout=self._timeout_s,
            )
        return self._client

    def fetch(self, url: str) -> FetchResponse:
        """Perform one request for ``url`` without following redirects.

        A redirect response is returned as-is with its ``Location`` header (if
        any) exposed as :attr:`FetchResponse.location`; the crawler resolves and
        follows it under the redirect hard cap.
        """
        response = self._get_client().get(url)
        return FetchResponse(
            url=url,
            final_url=url,
            status_code=response.status_code,
            html=response.text,
            location=response.headers.get("location"),
        )

    def close(self) -> None:
        """Close the underlying client if one was created."""
        if self._client is not None:
            self._client.close()
            self._client = None


@runtime_checkable
class LinkProber(Protocol):
    """The crawler's link-status boundary: observe the HTTP status of ``url``.

    An implementation performs a **single** HTTP request for ``url`` and returns
    the observed integer HTTP status code (any status, including 4xx/5xx — the
    link responded, so a status was observed). It MUST raise on a timeout or a
    network failure so the crawler can translate that into an unreachable
    :class:`~core.types.LinkStatus` (Req 2.3, 2.4).

    The default implementation is :class:`HttpxLinkProber`; tests inject an
    in-memory callable so no live site is contacted (Req 2.5).
    """

    def __call__(self, url: str) -> int:
        """Return the observed HTTP status code for ``url`` (raise on failure)."""
        ...


class HttpxLinkProber:
    """Default :class:`LinkProber` backed by a synchronous ``httpx`` client.

    Issues a single ``HEAD`` request for ``url`` and returns the observed HTTP
    status code, using a bounded timeout (default
    :data:`core.constants.LINK_TIMEOUT_S`, 10 s) and never executing JavaScript
    (Req 1.13, 2.3). Any HTTP status is a valid observation — the request
    reached a server, so a status was observed. On a timeout or network failure
    the underlying :class:`httpx.HTTPError` propagates; the crawler catches it
    and reports the link unreachable (Req 2.4).

    The client is created lazily on first use so constructing a
    :class:`~crawler.crawler.Crawler` never opens a network resource — tests
    inject their own callable and never touch this class.
    """

    def __init__(
        self,
        *,
        timeout_s: float = LINK_TIMEOUT_S,
        client: httpx.Client | None = None,
    ) -> None:
        self._timeout_s = timeout_s
        self._client = client

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                follow_redirects=True,
                timeout=self._timeout_s,
            )
        return self._client

    def __call__(self, url: str) -> int:
        """Perform one ``HEAD`` request for ``url`` and return its status code."""
        response = self._get_client().head(url)
        return response.status_code

    def close(self) -> None:
        """Close the underlying client if one was created."""
        if self._client is not None:
            self._client.close()
            self._client = None
