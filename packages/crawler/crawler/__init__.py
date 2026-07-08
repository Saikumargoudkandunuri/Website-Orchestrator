"""Crawler subsystem — discovers and retrieves same-domain pages politely.

Depends only on Core_Package; cross-subsystem interaction happens through the
Protocols and typed records published in Core_Package.

Public API:

* :class:`~crawler.crawler.Crawler` — the concrete
  :class:`core.interfaces.CrawlerPort`.
* :class:`~crawler.fetcher.Fetcher` / :class:`~crawler.fetcher.FetchResponse` /
  :class:`~crawler.fetcher.HttpxFetcher` — the injectable HTTP boundary.
* :class:`~crawler.robots.RobotsGate` /
  :class:`~crawler.robots.HttpxRobotsFetcher` — the injectable robots.txt
  fail-closed gate consulted before every fetch (Req 1.6-1.8).
"""

from crawler.crawler import MAX_PAGES, MIN_PAGES, Crawler
from crawler.fetcher import (
    Fetcher,
    FetchResponse,
    HttpxFetcher,
    HttpxLinkProber,
    LinkProber,
)
from crawler.robots import HttpxRobotsFetcher, RobotsFetcher, RobotsGate

__all__ = [
    "Crawler",
    "MIN_PAGES",
    "MAX_PAGES",
    "Fetcher",
    "FetchResponse",
    "HttpxFetcher",
    "LinkProber",
    "HttpxLinkProber",
    "RobotsGate",
    "RobotsFetcher",
    "HttpxRobotsFetcher",
]
