"""Crawl-time page-snapshot persistence (Milestone 2 integration seam).

Milestone 1's Digital_Twin does not persist a page's images/HTML or expose pages
by id, so the intelligence layer stores the crawl-time ``CrawledPage`` snapshot
it analyzes. This lets the on-demand ``/analyze`` endpoint and re-analysis run
against real page data without re-crawling, and provides the site's known URLs /
slugs for link-suggestion and slug-collision validation. Keyed by the stable
``page_id`` (see :mod:`intelligence.identifiers`); latest snapshot wins.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from core.types import CrawledPage
from intelligence.repositories._session import SessionMixin
from intelligence.repositories.models_orm import PageSnapshotRow

__all__ = ["PageSnapshotRepository"]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PageSnapshotRepository(SessionMixin):
    def upsert(
        self,
        tenant_id: str,
        page_id: str,
        page: CrawledPage,
        *,
        crawl_id: str | None = None,
    ) -> None:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            existing = session.get(PageSnapshotRow, page_id)
            if existing is None:
                existing = PageSnapshotRow(page_id=page_id)
                session.add(existing)
            existing.tenant_id = tenant
            existing.url = page.url
            existing.crawl_id = crawl_id
            existing.crawled_page = page.model_dump(mode="json")
            existing.created_at = _utc_now()

    def get(self, tenant_id: str, page_id: str) -> CrawledPage | None:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            row = session.get(PageSnapshotRow, page_id)
            if row is None or row.tenant_id != tenant:
                return None
            return CrawledPage.model_validate(row.crawled_page)

    def known_urls(self, tenant_id: str) -> list[str]:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            rows = session.execute(
                select(PageSnapshotRow.url).where(PageSnapshotRow.tenant_id == tenant)
            ).all()
            return [u for (u,) in rows]
