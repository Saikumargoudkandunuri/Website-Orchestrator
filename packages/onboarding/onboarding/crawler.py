"""InitialCrawler — perform the first full crawl right after verification.

Reuses the existing :class:`~crawler.crawler.Crawler` (CrawlerPort) rather than
re-implementing retrieval. It drives the crawler from the website URL, then
persists the crawled pages through the existing
:class:`~digital_twin.repository.DigitalTwinRepository` (upsert_pages), keeping
the Digital_Twin as the single source of crawl truth.

The crawler is injectable: a fake CrawlerPort can be supplied for tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.interfaces import CrawlerPort
from core.types import CrawledPage

from digital_twin.repository import DigitalTwinRepository

__all__ = ["CrawlSummary", "InitialCrawler"]


@dataclass
class CrawlSummary:
    """A concise summary of an initial crawl."""

    website_id: str
    pages: int = 0
    posts: int = 0
    media: int = 0
    internal_links: int = 0
    external_links: int = 0
    issues: int = 0
    crawled_pages: list[CrawledPage] = field(default_factory=list)


class InitialCrawler:
    """Run the initial crawl and persist results to the Digital_Twin."""

    def __init__(
        self,
        crawler: CrawlerPort,
        digital_twin: DigitalTwinRepository,
        *,
        tenant_id: str,
    ) -> None:
        self._crawler = crawler
        self._digital_twin = digital_twin
        self._tenant_id = tenant_id

    def crawl(self, website_id: str, start_url: str, max_pages: int = 100) -> CrawlSummary:
        """Crawl ``start_url`` and persist the pages to the Digital_Twin."""
        pages = self._crawler.crawl_site(start_url, max_pages)
        self._digital_twin.upsert_pages(self._tenant_id, pages)

        summary = CrawlSummary(website_id=website_id)
        summary.crawled_pages = pages
        summary.pages = len(pages)
        internal = 0
        external = 0
        for page in pages:
            for link in page.links:
                if _same_host(link.url, start_url):
                    internal += 1
                else:
                    external += 1
        summary.internal_links = internal
        summary.external_links = external
        # Posts are pages whose URL looks like a blog post (heuristic).
        summary.posts = sum(1 for p in pages if "/blog/" in p.url or "/posts/" in p.url)
        summary.media = sum(len(p.images) for p in pages)
        return summary


def _same_host(a: str, b: str) -> bool:
    from urllib.parse import urlsplit

    try:
        return urlsplit(a).hostname == urlsplit(b).hostname
    except Exception:  # noqa: BLE001
        return False
