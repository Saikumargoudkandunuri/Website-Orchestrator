"""Enterprise Knowledge Graph Repository (Phase 2).

Follows SessionMixin + append-only versioned pattern to persist enterprise-scoped
nodes and edges in SQLite/Postgres. Enforces tenant boundaries.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, delete

from intelligence.repositories._session import SessionMixin
from brain.repositories import KnowledgeGraphRepository
from enterprise_intelligence.db import EnterpriseNodeRow, EnterpriseEdgeRow
from enterprise_intelligence.knowledge.models import (
    EnterpriseNode,
    EnterpriseEdge,
    ProvenanceRecord,
)
from enterprise_intelligence.knowledge.enterprise_graph import EnterpriseGraph

__all__ = ["EnterpriseKnowledgeGraphRepository"]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EnterpriseKnowledgeGraphRepository(SessionMixin):
    """Repository managing persistence for Phase 2 Enterprise Knowledge Graph.

    Coordinates loading the underlying M5 site graph via KnowledgeGraphRepository,
    and merging it with the Phase 2 enterprise tables.
    """

    def __init__(
        self,
        session_source: Any,
        tenant_id: str,
        site_graph_repo: KnowledgeGraphRepository,
    ) -> None:
        super().__init__(session_source, tenant_id=tenant_id)
        self._site_graph_repo = site_graph_repo

    def save_node(self, node: EnterpriseNode) -> None:
        """Save a new enterprise node. If version matches or exists, overwrites."""
        tenant = self._resolve_tenant(node.tenant_id)
        with self._session() as session:
            # Check if node exists
            existing = session.execute(
                select(EnterpriseNodeRow).where(
                    EnterpriseNodeRow.tenant_id == tenant,
                    EnterpriseNodeRow.id == node.id,
                )
            ).scalar_one_or_none()

            if existing:
                existing.label = node.label
                existing.properties = node.properties
                existing.confidence = node.confidence
                existing.version = node.version
                existing.provenance = node.provenance.model_dump(mode="json")
                existing.updated_at = _utc_now()
            else:
                row = EnterpriseNodeRow(
                    id=node.id,
                    tenant_id=tenant,
                    site_id=node.site_id,
                    node_type=node.node_type,
                    label=node.label,
                    properties=node.properties,
                    confidence=node.confidence,
                    version=node.version,
                    provenance=node.provenance.model_dump(mode="json"),
                    created_at=node.created_at,
                    updated_at=node.updated_at,
                )
                session.add(row)
            session.commit()

    def save_edge(self, edge: EnterpriseEdge) -> None:
        """Save an enterprise relationship edge."""
        tenant = self._resolve_tenant(edge.tenant_id)
        with self._session() as session:
            existing = session.execute(
                select(EnterpriseEdgeRow).where(
                    EnterpriseEdgeRow.tenant_id == tenant,
                    EnterpriseEdgeRow.id == edge.id,
                )
            ).scalar_one_or_none()

            if existing:
                existing.properties = edge.properties
                existing.confidence = edge.confidence
                existing.provenance = edge.provenance.model_dump(mode="json")
            else:
                row = EnterpriseEdgeRow(
                    id=edge.id,
                    tenant_id=tenant,
                    site_id=edge.site_id,
                    edge_type=edge.edge_type,
                    from_node_id=edge.from_node_id,
                    to_node_id=edge.to_node_id,
                    properties=edge.properties,
                    confidence=edge.confidence,
                    provenance=edge.provenance.model_dump(mode="json"),
                    created_at=edge.created_at,
                )
                session.add(row)
            session.commit()

    def get_enterprise_graph(self, tenant_id: str, site_id: str) -> EnterpriseGraph:
        """Fetch the full integrated graph for a site (M5 base + Phase 2 extensions)."""
        tenant = self._resolve_tenant(tenant_id)
        
        # Load M5 site graph first
        site_graph = self._site_graph_repo.load_graph(tenant_id, site_id)
        
        # Load Phase 2 nodes
        with self._session() as session:
            node_rows = session.execute(
                select(EnterpriseNodeRow).where(
                    EnterpriseNodeRow.tenant_id == tenant,
                    EnterpriseNodeRow.site_id == site_id,
                )
            ).scalars().all()
            
            edge_rows = session.execute(
                select(EnterpriseEdgeRow).where(
                    EnterpriseEdgeRow.tenant_id == tenant,
                    EnterpriseEdgeRow.site_id == site_id,
                )
            ).scalars().all()

            enterprise_nodes = [
                EnterpriseNode(
                    id=r.id,
                    node_type=r.node_type,
                    label=r.label,
                    site_id=r.site_id,
                    tenant_id=r.tenant_id,
                    properties=r.properties,
                    confidence=r.confidence,
                    version=r.version,
                    provenance=ProvenanceRecord.model_validate(r.provenance),
                    created_at=r.created_at,
                    updated_at=r.updated_at,
                )
                for r in node_rows
            ]

            enterprise_edges = [
                EnterpriseEdge(
                    id=r.id,
                    edge_type=r.edge_type,
                    from_node_id=r.from_node_id,
                    to_node_id=r.to_node_id,
                    site_id=r.site_id,
                    tenant_id=r.tenant_id,
                    properties=r.properties,
                    confidence=r.confidence,
                    provenance=ProvenanceRecord.model_validate(r.provenance),
                    created_at=r.created_at,
                )
                for r in edge_rows
            ]

        # Use an empty default site graph if none is persisted yet in M5
        from brain.knowledge_graph.models import WebsiteKnowledgeGraph
        if site_graph is None:
            site_graph = WebsiteKnowledgeGraph(site_id=site_id, tenant_id=tenant_id)

        return EnterpriseGraph(
            tenant_id=tenant_id,
            site_id=site_id,
            site_graph=site_graph,
            enterprise_nodes=enterprise_nodes,
            enterprise_edges=enterprise_edges,
        )
