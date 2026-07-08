"""Brain repositories — versioned SiteSynthesis and Knowledge Graph persistence.

Follows the same ``SessionMixin`` + append-only versioned pattern established
in M2's ``KnowledgeObjectRepository`` and M3's ``EngineRepoMixin``.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select

from intelligence.repositories._session import SessionMixin

from brain.db import KGEdgeRow, KGNodeRow, SiteSynthesisRow
from brain.knowledge_graph.models import (
    KGEdge,
    KGEdgeType,
    KGNode,
    KGNodeType,
    WebsiteKnowledgeGraph,
)
from brain.models import SiteSynthesis

__all__ = [
    "SiteSynthesisRepository",
    "KnowledgeGraphRepository",
]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex


class SiteSynthesisRepository(SessionMixin):
    """Append-only versioned repository for ``SiteSynthesis`` records."""

    def next_version(self, tenant_id: str, site_id: str) -> int:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            current = session.execute(
                select(func.max(SiteSynthesisRow.version)).where(
                    SiteSynthesisRow.tenant_id == tenant,
                    SiteSynthesisRow.site_id == site_id,
                )
            ).scalar_one_or_none()
            return (current or 0) + 1

    def save(self, tenant_id: str, synthesis: SiteSynthesis) -> SiteSynthesis:
        tenant = self._resolve_tenant(tenant_id)
        version = self.next_version(tenant_id, synthesis.site_id)
        synthesis = synthesis.model_copy(update={"version": version})
        row = SiteSynthesisRow(
            id=synthesis.id or _new_id(),
            tenant_id=tenant,
            site_id=synthesis.site_id,
            version=version,
            payload=synthesis.model_dump(mode="json"),
            computed_at=_utc_now(),
        )
        with self._session() as session:
            session.add(row)
        return synthesis

    def get_latest(self, tenant_id: str, site_id: str) -> SiteSynthesis | None:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            row = session.execute(
                select(SiteSynthesisRow)
                .where(
                    SiteSynthesisRow.tenant_id == tenant,
                    SiteSynthesisRow.site_id == site_id,
                )
                .order_by(SiteSynthesisRow.version.desc())
                .limit(1)
            ).scalar_one_or_none()
            return SiteSynthesis.model_validate(row.payload) if row else None

    def list_versions(
        self, tenant_id: str, site_id: str
    ) -> list[dict[str, Any]]:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            rows = session.execute(
                select(
                    SiteSynthesisRow.version,
                    SiteSynthesisRow.computed_at,
                )
                .where(
                    SiteSynthesisRow.tenant_id == tenant,
                    SiteSynthesisRow.site_id == site_id,
                )
                .order_by(SiteSynthesisRow.version.desc())
            ).all()
            return [{"version": v, "computed_at": c} for (v, c) in rows]


class KnowledgeGraphRepository(SessionMixin):
    """CRUD for Knowledge Graph nodes and edges, tenant-scoped."""

    def save_graph(
        self,
        tenant_id: str,
        graph: WebsiteKnowledgeGraph,
    ) -> None:
        """Persist the full graph (replace existing nodes/edges for this site)."""
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            # Delete existing nodes and edges for this site.
            session.execute(
                delete(KGEdgeRow).where(
                    KGEdgeRow.tenant_id == tenant,
                    KGEdgeRow.site_id == graph.site_id,
                )
            )
            session.execute(
                delete(KGNodeRow).where(
                    KGNodeRow.tenant_id == tenant,
                    KGNodeRow.site_id == graph.site_id,
                )
            )
            # Insert new nodes.
            for node in graph.nodes:
                session.add(KGNodeRow(
                    id=node.id,
                    tenant_id=tenant,
                    site_id=node.site_id,
                    node_type=node.node_type.value if isinstance(node.node_type, KGNodeType) else node.node_type,
                    label=node.label,
                    properties=node.properties,
                    source_version=node.source_version,
                    created_at=node.created_at,
                    updated_at=node.updated_at,
                ))
            # Insert new edges.
            for edge in graph.edges:
                session.add(KGEdgeRow(
                    id=edge.id,
                    tenant_id=tenant,
                    site_id=edge.site_id,
                    edge_type=edge.edge_type.value if isinstance(edge.edge_type, KGEdgeType) else edge.edge_type,
                    from_node_id=edge.from_node_id,
                    to_node_id=edge.to_node_id,
                    properties=edge.properties,
                    created_at=edge.created_at,
                ))

    def load_graph(
        self,
        tenant_id: str,
        site_id: str,
        *,
        node_type: str | None = None,
    ) -> WebsiteKnowledgeGraph:
        """Load the knowledge graph for a site, optionally filtering by node type."""
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            node_query = select(KGNodeRow).where(
                KGNodeRow.tenant_id == tenant,
                KGNodeRow.site_id == site_id,
            )
            if node_type:
                node_query = node_query.where(KGNodeRow.node_type == node_type)

            node_rows = session.execute(node_query).scalars().all()
            nodes = [
                KGNode(
                    id=r.id,
                    node_type=KGNodeType(r.node_type),
                    label=r.label,
                    site_id=r.site_id,
                    tenant_id=r.tenant_id,
                    properties=r.properties or {},
                    source_version=r.source_version,
                    created_at=r.created_at,
                    updated_at=r.updated_at,
                )
                for r in node_rows
            ]

            node_ids = {n.id for n in nodes}

            edge_query = select(KGEdgeRow).where(
                KGEdgeRow.tenant_id == tenant,
                KGEdgeRow.site_id == site_id,
            )
            edge_rows = session.execute(edge_query).scalars().all()
            edges = [
                KGEdge(
                    id=r.id,
                    edge_type=KGEdgeType(r.edge_type),
                    from_node_id=r.from_node_id,
                    to_node_id=r.to_node_id,
                    site_id=r.site_id,
                    tenant_id=r.tenant_id,
                    properties=r.properties or {},
                    created_at=r.created_at,
                )
                for r in edge_rows
                if not node_type or (r.from_node_id in node_ids and r.to_node_id in node_ids)
            ]

            return WebsiteKnowledgeGraph(
                site_id=site_id,
                tenant_id=tenant,
                nodes=nodes,
                edges=edges,
            )

    def node_count(self, tenant_id: str, site_id: str) -> int:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            return session.execute(
                select(func.count(KGNodeRow.id)).where(
                    KGNodeRow.tenant_id == tenant,
                    KGNodeRow.site_id == site_id,
                )
            ).scalar_one()

    def edge_count(self, tenant_id: str, site_id: str) -> int:
        tenant = self._resolve_tenant(tenant_id)
        with self._session() as session:
            return session.execute(
                select(func.count(KGEdgeRow.id)).where(
                    KGEdgeRow.tenant_id == tenant,
                    KGEdgeRow.site_id == site_id,
                )
            ).scalar_one()
