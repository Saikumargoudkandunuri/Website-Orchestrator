"""Content Generation repositories."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from intelligence.repositories._session import SessionMixin
from growth.db import ContentGenerationAssetRow
from growth.shared.content_asset import ContentAsset, ContentAssetStatus

__all__ = ["ContentAssetRepository"]


class ContentAssetRepository(SessionMixin):
    """CRUD + governance operations for ContentAsset entities."""

    def save(self, asset: ContentAsset) -> ContentAsset:
        now = datetime.now(timezone.utc)
        with self._session() as session:
            existing = session.get(ContentGenerationAssetRow, asset.id)
            if existing:
                existing.status = asset.status.value
                existing.payload = asset.model_dump(mode="json")
                existing.updated_at = now
            else:
                row = ContentGenerationAssetRow(
                    id=asset.id,
                    tenant_id=asset.tenant_id,
                    organization_id=asset.organization_id,
                    client_id=asset.client_id,
                    site_id=asset.site_id,
                    page_id=asset.page_id,
                    asset_type=asset.asset_type.value,
                    status=asset.status.value,
                    payload=asset.model_dump(mode="json"),
                    created_at=asset.created_at,
                    updated_at=now,
                )
                session.add(row)
        return asset

    def get(self, asset_id: str) -> ContentAsset | None:
        with self._session() as session:
            row = session.get(ContentGenerationAssetRow, asset_id)
            if row is None:
                return None
            return ContentAsset.model_validate(row.payload)

    def list_by_site(self, tenant_id: str, site_id: str,
                     status: ContentAssetStatus | None = None) -> list[ContentAsset]:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            q = select(ContentGenerationAssetRow).where(
                ContentGenerationAssetRow.tenant_id == tenant,
                ContentGenerationAssetRow.site_id == site_id,
            )
            if status is not None:
                q = q.where(ContentGenerationAssetRow.status == status.value)
            rows = session.execute(q.order_by(
                ContentGenerationAssetRow.payload["created_at"].desc()
            )).scalars().all()
            return [ContentAsset.model_validate(r.payload) for r in rows]

    def list_review_queue(self, tenant_id: str) -> list[ContentAsset]:
        """Return all assets in in_review or pending status across all sites."""
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            rows = session.execute(
                select(ContentGenerationAssetRow).where(
                    ContentGenerationAssetRow.tenant_id == tenant,
                    ContentGenerationAssetRow.status.in_(["in_review", "pending"]),
                )
            ).scalars().all()
            return [ContentAsset.model_validate(r.payload) for r in rows]

    # Cross-tenant isolation test helper
    def get_by_site_unchecked(self, site_id: str) -> list[ContentAsset]:
        """UNSAFE: no tenant check. Used only in isolation tests to verify
        that tenant-A data is not visible to tenant-B."""
        with self._session() as session:
            rows = session.execute(
                select(ContentGenerationAssetRow).where(
                    ContentGenerationAssetRow.site_id == site_id,
                )
            ).scalars().all()
            return [ContentAsset.model_validate(r.payload) for r in rows]
