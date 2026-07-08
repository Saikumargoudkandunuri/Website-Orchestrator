"""robots.txt fail-closed gating for the Crawler (Req 1.6-1.8).

Before the :class:`~crawler.crawler.Crawler` retrieves any URL it must consult
the origin's ``robots.txt`` and honor its directives (Req 1.6). This module
provides that gate as a small, injectable seam so the crawl logic stays pure and
tests never touch the network.

Two pieces make up the boundary:

* :data:`RobotsFetcher` — the injectable function the gate uses to obtain a
  ``robots.txt`` body. It maps a ``robots.txt`` URL to its text and **raises**
  when the document cannot be retrieved. The default
  :class:`HttpxRobotsFetcher` implements it over ``httpx``; tests inject an
  in-memory callable so no live site is contacted.
* :class:`RobotsGate` — parses each origin's ``robots.txt`` with
  :class:`urllib.robotparser.RobotFileParser` and answers
  :meth:`RobotsGate.allowed`. Results are decided **per origin** and cached, so
  each host's ``robots.txt`` is fetched at most once per crawl.

Fail-closed semantics (Req 1.7): if a ``robots.txt`` cannot be retrieved the
gate maps the failure to :class:`~core.exceptions.RobotsUnavailableError`
internally and :meth:`RobotsGate.allowed` returns ``False`` — the affected URLs
are excluded from retrieval rather than crashing the whole crawl. A URL the
``robots.txt`` explicitly disallows is likewise excluded (Req 1.8).
"""

from __future__ import annotations

from typing import Callable, Protocol, runtime_checkable
from urllib.parse import urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import httpx

from core.constants import REQUEST_TIMEOUT_S
from core.exceptions import RobotsUnavailableError

__all__ = [
    "RobotsFetcher",
    "HttpxRobotsFetcher",
    "RobotsGate",
    "DEFAULT_USER_AGENT",
]

#: The product token the gate matches ``robots.txt`` groups against. ``"*"``
#: selects the wildcard user-agent group, i.e. the directives that apply to any
#: crawler.
DEFAULT_USER_AGENT: str = "*"


@runtime_checkable
class RobotsFetcher(Protocol):
    """Injectable boundary that returns a ``robots.txt`` body for an origin.

    Implementations receive the fully-qualified ``robots.txt`` URL (e.g.
    ``https://example.com/robots.txt``) and return its text. They MUST raise on
    any failure to retrieve the document (network error, non-success status,
    timeout); the raised type is irrelevant because :class:`RobotsGate` maps any
    failure to :class:`~core.exceptions.RobotsUnavailableError` and fails closed.
    """

    def __call__(self, robots_url: str) -> str:
        """Return the text of the ``robots.txt`` at ``robots_url`` or raise."""
        ...


class HttpxRobotsFetcher:
    """Default :class:`RobotsFetcher` backed by a synchronous ``httpx`` client.

    Retrieves ``robots.txt`` over HTTP(S) with a bounded per-request timeout
    (default :data:`core.constants.REQUEST_TIMEOUT_S`) and raises when the
    document cannot be obtained, including on any non-success status code, so
    the gate fails closed (Req 1.7).

    The client is created lazily on first use so simply constructing a
    :class:`RobotsGate`/:class:`~crawler.crawler.Crawler` never opens a network
    resource — tests inject their own callable and never touch this class.
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
                follow_redirects=True,
                timeout=self._timeout_s,
            )
        return self._client

    def __call__(self, robots_url: str) -> str:
        """Fetch ``robots_url``; raise for status so failures fail closed."""
        response = self._get_client().get(robots_url)
        response.raise_for_status()
        return response.text

    def close(self) -> None:
        """Close the underlying client if one was created."""
        if self._client is not None:
            self._client.close()
            self._client = None


class RobotsGate:
    """Decide whether a URL may be retrieved under its origin's ``robots.txt``.

    The gate is consulted before every fetch (Req 1.6). It obtains each origin's
    ``robots.txt`` through the injected :class:`RobotsFetcher`, parses it with
    :class:`urllib.robotparser.RobotFileParser`, and caches the result per origin
    so a host's ``robots.txt`` is fetched at most once.

    Args:
        robots_fetcher: The boundary used to obtain a ``robots.txt`` body.
            Defaults to :class:`HttpxRobotsFetcher`; tests inject an in-memory
            callable so no live site is contacted.
        user_agent: The product token matched against ``robots.txt`` groups.
            Defaults to :data:`DEFAULT_USER_AGENT` (``"*"``).
    """

    #: Sentinel cached for an origin whose ``robots.txt`` could not be fetched,
    #: so the fail-closed decision is remembered without re-fetching.
    _UNAVAILABLE = object()

    def __init__(
        self,
        robots_fetcher: RobotsFetcher | None = None,
        *,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self._robots_fetcher: RobotsFetcher = (
            robots_fetcher if robots_fetcher is not None else HttpxRobotsFetcher()
        )
        self._user_agent = user_agent
        # origin -> RobotFileParser | _UNAVAILABLE
        self._cache: dict[str, object] = {}

    def allowed(self, url: str) -> bool:
        """Return ``True`` only if ``url`` may be retrieved (Req 1.6-1.8).

        A URL is excluded (``False``) when its origin's ``robots.txt`` disallows
        it (Req 1.8) or when that ``robots.txt`` cannot be retrieved — the
        fail-closed case (Req 1.7). The unavailable failure is mapped to
        :class:`~core.exceptions.RobotsUnavailableError` internally and absorbed
        here so a single unreachable ``robots.txt`` excludes only the affected
        URLs rather than crashing the crawl.
        """
        origin = _origin_of(url)
        if not origin:
            # No usable origin to consult a robots.txt for -> fail closed.
            return False
        try:
            parser = self._parser_for(origin)
        except RobotsUnavailableError:
            return False
        return parser.can_fetch(self._user_agent, url)

    def _parser_for(self, origin: str) -> RobotFileParser:
        """Return the cached parser for ``origin`` or fetch and parse it.

        Raises:
            RobotsUnavailableError: If the origin's ``robots.txt`` cannot be
                retrieved. The unavailable state is cached so subsequent URLs on
                the same origin fail closed without another fetch attempt.
        """
        cached = self._cache.get(origin, None)
        if cached is self._UNAVAILABLE:
            raise RobotsUnavailableError(
                f"robots.txt previously unavailable for origin {origin!r}"
            )
        if isinstance(cached, RobotFileParser):
            return cached

        robots_url = origin + "/robots.txt"
        try:
            text = self._robots_fetcher(robots_url)
        except Exception as exc:  # any failure -> fail closed (Req 1.7)
            self._cache[origin] = self._UNAVAILABLE
            raise RobotsUnavailableError(
                f"robots.txt could not be retrieved for origin {origin!r}"
            ) from exc

        parser = RobotFileParser()
        parser.parse(text.splitlines())
        self._cache[origin] = parser
        return parser


def _origin_of(url: str) -> str:
    """Return the ``scheme://netloc`` origin of ``url`` (empty when unusable)."""
    if not isinstance(url, str):
        return ""
    parts = urlsplit(url.strip())
    if not parts.scheme or not parts.netloc:
        return ""
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), "", "", ""))
