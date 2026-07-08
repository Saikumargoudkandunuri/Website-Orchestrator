"""In-memory Crawler boundaries for the end-to-end proof (Req 11.1, 2.5).

The Requirement 11 end-to-end proof must run entirely against a local
Fixture_Site so that **no request leaves localhost** (Req 11.1) and no live site
is contacted (Req 2.5). The :class:`~crawler.crawler.Crawler` reaches the network
only through three injectable seams — a :class:`~crawler.fetcher.Fetcher`, a
robots.txt fetcher used by :class:`~crawler.robots.RobotsGate`, and a
:class:`~crawler.fetcher.LinkProber`. This module supplies in-memory
implementations of all three, driven by the fixture data in
:mod:`e2e.fixtures`, so the crawl is fully deterministic and network-free.

* :class:`InMemoryFetcher` serves fixture HTML and redirect responses from a
  dictionary. Like a real :class:`~crawler.fetcher.Fetcher` it performs a
  *single* request per call and **never follows redirects**: a redirect entry is
  returned as-is with its ``Location`` target populated so the Crawler walks and
  records the Redirect_Chain itself (Req 2.1, 2.2).
* :func:`allow_all_robots_fetcher` returns an allow-all ``robots.txt`` for any
  origin, so robots gating never contacts a live site while still exercising the
  real :class:`~crawler.robots.RobotsGate` parsing path.
* :class:`InMemoryLinkProber` returns the seeded HTTP status for a probed link
  (defaulting to ``200`` for any link not explicitly seeded), so broken-link
  detection is driven by fixture data rather than a live probe.

None of these open a socket; constructing and using them touches only local
in-memory data.
"""

from __future__ import annotations

from crawler.fetcher import FetchResponse

__all__ = [
    "InMemoryFetcher",
    "InMemoryLinkProber",
    "allow_all_robots_fetcher",
    "ALLOW_ALL_ROBOTS_TXT",
]

#: An allow-all ``robots.txt`` body: the wildcard user-agent group allows every
#: path. Served for every origin so robots gating excludes nothing (Req 1.6).
ALLOW_ALL_ROBOTS_TXT = "User-agent: *\nAllow: /\n"


def allow_all_robots_fetcher(robots_url: str) -> str:
    """Return an allow-all ``robots.txt`` for any ``robots_url`` (Req 2.5).

    A drop-in :class:`~crawler.robots.RobotsFetcher` that never touches the
    network: whatever origin's ``robots.txt`` is requested, it returns a body
    that allows every path, so the real :class:`~crawler.robots.RobotsGate`
    parses it and permits every fixture URL.
    """
    return ALLOW_ALL_ROBOTS_TXT


class InMemoryFetcher:
    """A :class:`~crawler.fetcher.Fetcher` serving fixture pages and redirects.

    Backed by a mapping of URL -> :class:`~crawler.fetcher.FetchResponse`. Each
    :meth:`fetch` performs a single lookup and returns the seeded response
    without following redirects: a redirect entry keeps its ``location`` so the
    Crawler resolves and walks the chain under its redirect hard cap (Req 2.1,
    2.2). A URL with no seeded entry yields a ``404`` response with empty HTML,
    modelling a fixture link that resolves to nothing.

    Every request and its outcome is recorded in :attr:`requests` so a test can
    assert exactly which fixture URLs were retrieved and that nothing left the
    local fixture set (Req 11.1).
    """

    def __init__(self, responses: dict[str, FetchResponse]) -> None:
        self._responses = dict(responses)
        #: Ordered log of every requested URL (spy for network-locality asserts).
        self.requests: list[str] = []

    def fetch(self, url: str) -> FetchResponse:
        """Return the seeded :class:`FetchResponse` for ``url`` (single request).

        Records ``url`` in :attr:`requests`. An unseeded URL returns a ``404``
        empty response rather than raising, mirroring a link that points at a
        missing local resource.
        """
        self.requests.append(url)
        seeded = self._responses.get(url)
        if seeded is not None:
            return seeded
        return FetchResponse(url=url, final_url=url, status_code=404, html="")


class InMemoryLinkProber:
    """A :class:`~crawler.fetcher.LinkProber` returning seeded link statuses.

    Backed by a mapping of URL -> HTTP status code. Probing a seeded URL returns
    its status; probing an unseeded URL returns :attr:`default_status` (``200``
    by default), so only the links a fixture explicitly marks broken produce a
    4xx/5xx. Every probe is recorded in :attr:`probes`.

    The Crawler's :meth:`~crawler.crawler.Crawler.check_link_status` treats *any*
    returned integer as a reachable observation, so to model an unreachable link
    (timeout / network failure) a seeded status may be ``None``, in which case
    this prober raises — the Crawler then reports the link unreachable without
    raising (Req 2.4).
    """

    def __init__(
        self,
        statuses: dict[str, int | None] | None = None,
        *,
        default_status: int = 200,
    ) -> None:
        self._statuses = dict(statuses or {})
        self.default_status = default_status
        #: Ordered log of every probed URL (spy for assertions).
        self.probes: list[str] = []

    def __call__(self, url: str) -> int:
        """Return the seeded HTTP status for ``url`` (raise to model unreachable)."""
        self.probes.append(url)
        status = self._statuses.get(url, self.default_status)
        if status is None:
            raise ConnectionError(f"seeded unreachable link: {url!r}")
        return int(status)
