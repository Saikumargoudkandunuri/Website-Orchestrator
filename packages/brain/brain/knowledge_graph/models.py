"""Website Knowledge Graph models (M5 Phase 1).

Extends M3's Topical Authority entity/topic graph model into a persisted,
incrementally-updatable graph store. Nodes represent pages, entities, topics,
keywords, backlinks, and locations. Edges represent the typed relationships
between them.

The graph is queryable (traversal API) independent of any specific engine,
enabling the Decision Engine, Copilot, and any future consumer to traverse
the site as a connected structure rather than twenty independent record sets.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

__all__ = [
    "KGNodeType",
    "KGEdgeType",
    "KGNode",
    "KGEdge",
    "WebsiteKnowledgeGraph",
]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class KGNodeType(str, Enum):
    """Supported Knowledge Graph node types."""

    PAGE = "page"
    ENTITY = "entity"
    TOPIC = "topic"
    KEYWORD = "keyword"
    BACKLINK = "backlink"
    LOCATION = "location"


class KGEdgeType(str, Enum):
    """Supported Knowledge Graph edge types."""

    INTERNAL_LINK = "internal_link"
    ENTITY_COOCCURRENCE = "entity_cooccurrence"
    TOPIC_MEMBERSHIP = "topic_membership"
    KEYWORD_TARGETING = "keyword_targeting"
    BACKLINK_SOURCE_TARGET = "backlink_source_target"
    LOCATION_ASSOCIATION = "location_association"
    TOPIC_RELATIONSHIP = "topic_relationship"
    ENTITY_PAGE_MENTION = "entity_page_mention"


class KGNode(BaseModel):
    """A single node in the Website Knowledge Graph."""

    id: str
    node_type: KGNodeType
    label: str
    site_id: str
    tenant_id: str
    #: Arbitrary typed properties (entity_type, url, confidence, etc.)
    properties: dict[str, Any] = Field(default_factory=dict)
    #: Version of the source data that produced this node (for incremental
    #: updates: if the source version hasn't changed, skip recomputation).
    source_version: int = 0
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)


class KGEdge(BaseModel):
    """A typed, directed edge in the Website Knowledge Graph."""

    id: str
    edge_type: KGEdgeType
    from_node_id: str
    to_node_id: str
    site_id: str
    tenant_id: str
    #: Edge-specific properties (weight, anchor_text, co-occurrence count, etc.)
    properties: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utc_now)


class WebsiteKnowledgeGraph(BaseModel):
    """Container for a site's Knowledge Graph with traversal methods.

    This is the in-memory representation used for queries; persistence
    is handled by ``KnowledgeGraphRepository``.
    """

    site_id: str
    tenant_id: str
    nodes: list[KGNode] = Field(default_factory=list)
    edges: list[KGEdge] = Field(default_factory=list)
    built_at: datetime = Field(default_factory=_utc_now)

    # --- Lazy-built indices (not serialized) ---
    _nodes_by_id: dict[str, KGNode] | None = None
    _nodes_by_type: dict[KGNodeType, list[KGNode]] | None = None
    _outgoing_edges: dict[str, list[KGEdge]] | None = None
    _incoming_edges: dict[str, list[KGEdge]] | None = None

    def _ensure_indices(self) -> None:
        if self._nodes_by_id is not None:
            return
        nbi: dict[str, KGNode] = {}
        nbt: dict[KGNodeType, list[KGNode]] = {}
        for n in self.nodes:
            nbi[n.id] = n
            nbt.setdefault(n.node_type, []).append(n)
        oe: dict[str, list[KGEdge]] = {}
        ie: dict[str, list[KGEdge]] = {}
        for e in self.edges:
            oe.setdefault(e.from_node_id, []).append(e)
            ie.setdefault(e.to_node_id, []).append(e)
        object.__setattr__(self, "_nodes_by_id", nbi)
        object.__setattr__(self, "_nodes_by_type", nbt)
        object.__setattr__(self, "_outgoing_edges", oe)
        object.__setattr__(self, "_incoming_edges", ie)

    def get_node(self, node_id: str) -> KGNode | None:
        self._ensure_indices()
        return self._nodes_by_id.get(node_id)  # type: ignore[union-attr]

    def nodes_of_type(self, node_type: KGNodeType) -> list[KGNode]:
        self._ensure_indices()
        return list(self._nodes_by_type.get(node_type, []))  # type: ignore[union-attr]

    def outgoing(self, node_id: str) -> list[KGEdge]:
        self._ensure_indices()
        return list(self._outgoing_edges.get(node_id, []))  # type: ignore[union-attr]

    def incoming(self, node_id: str) -> list[KGEdge]:
        self._ensure_indices()
        return list(self._incoming_edges.get(node_id, []))  # type: ignore[union-attr]

    def neighbors(self, node_id: str, max_depth: int = 1) -> list[KGNode]:
        """Return nodes reachable from ``node_id`` within ``max_depth`` hops."""
        self._ensure_indices()
        visited: set[str] = {node_id}
        frontier: set[str] = {node_id}
        for _ in range(max_depth):
            next_frontier: set[str] = set()
            for nid in frontier:
                for edge in self._outgoing_edges.get(nid, []):  # type: ignore[union-attr]
                    if edge.to_node_id not in visited:
                        visited.add(edge.to_node_id)
                        next_frontier.add(edge.to_node_id)
                for edge in self._incoming_edges.get(nid, []):  # type: ignore[union-attr]
                    if edge.from_node_id not in visited:
                        visited.add(edge.from_node_id)
                        next_frontier.add(edge.from_node_id)
            frontier = next_frontier
            if not frontier:
                break
        visited.discard(node_id)
        return [self._nodes_by_id[nid] for nid in visited if nid in self._nodes_by_id]  # type: ignore[union-attr]

    def subgraph(
        self,
        node_type: KGNodeType | None = None,
        max_depth: int | None = None,
        root_node_id: str | None = None,
    ) -> "WebsiteKnowledgeGraph":
        """Return a filtered subgraph."""
        self._ensure_indices()
        if root_node_id and max_depth is not None:
            neighbor_nodes = self.neighbors(root_node_id, max_depth)
            root = self.get_node(root_node_id)
            if root:
                neighbor_nodes = [root] + neighbor_nodes
            if node_type:
                neighbor_nodes = [n for n in neighbor_nodes if n.node_type == node_type]
            node_ids = {n.id for n in neighbor_nodes}
            filtered_edges = [
                e for e in self.edges
                if e.from_node_id in node_ids and e.to_node_id in node_ids
            ]
            return WebsiteKnowledgeGraph(
                site_id=self.site_id,
                tenant_id=self.tenant_id,
                nodes=neighbor_nodes,
                edges=filtered_edges,
            )
        if node_type:
            filtered_nodes = self.nodes_of_type(node_type)
            node_ids = {n.id for n in filtered_nodes}
            filtered_edges = [
                e for e in self.edges
                if e.from_node_id in node_ids and e.to_node_id in node_ids
            ]
            return WebsiteKnowledgeGraph(
                site_id=self.site_id,
                tenant_id=self.tenant_id,
                nodes=filtered_nodes,
                edges=filtered_edges,
            )
        return self
