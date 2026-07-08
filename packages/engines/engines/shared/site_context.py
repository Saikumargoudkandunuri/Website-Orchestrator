"""SiteContext — the shared, read-only sitewide projection (§3.4).

Rather than each engine independently reconstructing the full site graph, a
single ``SiteContext`` is built once per audit from the page-snapshot repository
and shared across all sitewide engines. It is *read-only and cheaply
rebuildable*, not a mutable cross-engine dependency.

Big-O notes (§7 large-site requirement):
- Building ``link_graph`` is O(P * L) where P = pages and L = average links/page.
- Building ``pages`` summary is O(P).
- The builder never loads full KnowledgeObjects — only lightweight PageSummary
  projections — so memory usage scales with P * constant, not P * KO_size.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

__all__ = [
    "PageSummary",
    "LinkGraphEdge",
    "SiteContext",
    "SiteContextBuilder",
]


class PageSummary(BaseModel):
    """A lightweight per-page projection for sitewide analysis.

    Deliberately shallow — holds only the fields sitewide engines need without
    loading the full KnowledgeObject, to keep memory bounded for large sites.
    """

    page_id: str
    url: str
    title: str | None = None
    slug: str | None = None
    word_count: int = 0
    focus_keyphrase: str | None = None
    depth: int = 0          # BFS depth from homepage, 0 = homepage
    has_schema: bool = False
    broken: bool = False
    crawl_id: str | None = None


class LinkGraphEdge(BaseModel):
    """One directed internal link edge."""

    from_page_id: str
    to_page_id: str
    anchor_text: str | None = None
    element_id: str | None = None


class SiteContext(BaseModel):
    """The shared, read-only sitewide view (§3.4)."""

    site_id: str
    tenant_id: str
    crawl_id: str | None = None
    pages: list[PageSummary] = Field(default_factory=list)
    link_graph: list[LinkGraphEdge] = Field(default_factory=list)
    built_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Convenience index built on first access — not serialised.
    _page_by_id: dict[str, PageSummary] | None = None

    def page_by_id(self, page_id: str) -> PageSummary | None:
        if self._page_by_id is None:
            object.__setattr__(
                self, "_page_by_id", {p.page_id: p for p in self.pages}
            )
        return self._page_by_id.get(page_id)  # type: ignore[union-attr]

    def outlinks(self, page_id: str) -> list[LinkGraphEdge]:
        return [e for e in self.link_graph if e.from_page_id == page_id]

    def inlinks(self, page_id: str) -> list[LinkGraphEdge]:
        return [e for e in self.link_graph if e.to_page_id == page_id]


class SiteContextBuilder:
    """Builds a :class:`SiteContext` from page-snapshot data.

    Accepts any iterable of page-dict records so it can be constructed from
    the ``PageSnapshotRepository`` without importing that repo directly (avoids
    a circular dependency).  Callers extract the needed fields and pass them as
    lightweight dicts.
    """

    def __init__(self, site_id: str, tenant_id: str, crawl_id: str | None = None) -> None:
        self._site_id = site_id
        self._tenant_id = tenant_id
        self._crawl_id = crawl_id
        self._pages: list[PageSummary] = []
        self._edges: list[LinkGraphEdge] = []

    def add_page(
        self,
        page_id: str,
        url: str,
        *,
        title: str | None = None,
        slug: str | None = None,
        word_count: int = 0,
        focus_keyphrase: str | None = None,
        has_schema: bool = False,
        broken: bool = False,
        depth: int = 0,
        crawl_id: str | None = None,
    ) -> None:
        self._pages.append(
            PageSummary(
                page_id=page_id,
                url=url,
                title=title,
                slug=slug,
                word_count=word_count,
                focus_keyphrase=focus_keyphrase,
                has_schema=has_schema,
                broken=broken,
                depth=depth,
                crawl_id=crawl_id,
            )
        )

    def add_link(
        self,
        from_page_id: str,
        to_page_id: str,
        *,
        anchor_text: str | None = None,
        element_id: str | None = None,
    ) -> None:
        self._edges.append(
            LinkGraphEdge(
                from_page_id=from_page_id,
                to_page_id=to_page_id,
                anchor_text=anchor_text,
                element_id=element_id,
            )
        )

    def build(self) -> SiteContext:
        return SiteContext(
            site_id=self._site_id,
            tenant_id=self._tenant_id,
            crawl_id=self._crawl_id,
            pages=list(self._pages),
            link_graph=list(self._edges),
        )
