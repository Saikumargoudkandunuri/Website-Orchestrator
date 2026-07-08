"""EnterpriseGraph wrapping M5 WebsiteKnowledgeGraph (Phase 2).

Integrates M5 site-content nodes/edges with the new enterprise business layers,
enforcing explainable traversals and provenance metrics.
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field

from brain.knowledge_graph.models import WebsiteKnowledgeGraph, KGNode, KGEdge
from enterprise_intelligence.knowledge.models import EnterpriseNode, EnterpriseEdge

__all__ = ["EnterpriseGraph"]


class EnterpriseGraph(BaseModel):
    """Integrated enterprise knowledge graph.

    Wraps M5's site-content graph and combines it with new enterprise-scoped nodes/edges.
    Provides traversals, explainable paths, and search capabilities.
    """

    tenant_id: str
    site_id: str
    
    # Base site content graph from M5
    site_graph: WebsiteKnowledgeGraph = Field(default_factory=lambda: WebsiteKnowledgeGraph(site_id="default", tenant_id="default"))
    
    # Enterprise extension nodes/edges
    enterprise_nodes: list[EnterpriseNode] = Field(default_factory=list)
    enterprise_edges: list[EnterpriseEdge] = Field(default_factory=list)

    # Lazy indices
    _nodes_by_id: dict[str, Any] | None = None
    _outgoing_edges: dict[str, list[Any]] | None = None
    _incoming_edges: dict[str, list[Any]] | None = None

    def _ensure_indices(self) -> None:
        if self._nodes_by_id is not None:
            return
        
        nbi: dict[str, Any] = {}
        # Index site nodes
        for n in self.site_graph.nodes:
            nbi[n.id] = n
        # Index enterprise nodes
        for n in self.enterprise_nodes:
            nbi[n.id] = n

        oe: dict[str, list[Any]] = {}
        ie: dict[str, list[Any]] = {}
        
        # Index site edges
        for e in self.site_graph.edges:
            oe.setdefault(e.from_node_id, []).append(e)
            ie.setdefault(e.to_node_id, []).append(e)
            
        # Index enterprise edges
        for e in self.enterprise_edges:
            oe.setdefault(e.from_node_id, []).append(e)
            ie.setdefault(e.to_node_id, []).append(e)

        object.__setattr__(self, "_nodes_by_id", nbi)
        object.__setattr__(self, "_outgoing_edges", oe)
        object.__setattr__(self, "_incoming_edges", ie)

    def get_node(self, node_id: str) -> Any | None:
        """Retrieve a node by its ID (either site-content or enterprise)."""
        self._ensure_indices()
        return self._nodes_by_id.get(node_id)

    def get_neighbors(self, node_id: str) -> list[Any]:
        """Get all adjacent nodes (neighbors) for a node."""
        self._ensure_indices()
        neighbors_nodes = []
        
        # Outgoing neighbors
        for edge in self._outgoing_edges.get(node_id, []):
            node = self.get_node(edge.to_node_id)
            if node:
                neighbors_nodes.append(node)
                
        # Incoming neighbors
        for edge in self._incoming_edges.get(node_id, []):
            node = self.get_node(edge.from_node_id)
            if node:
                neighbors_nodes.append(node)
                
        return neighbors_nodes

    def traverse_explainable(
        self, start_node_id: str, max_depth: int = 2
    ) -> dict[str, Any]:
        """Perform a BFS traversal returning the reached subgraph and paths for explainability.

        Every reached node is returned with its traversal path and provenance details.
        """
        self._ensure_indices()
        
        visited: dict[str, list[str]] = {start_node_id: [start_node_id]}
        queue: list[str] = [start_node_id]
        
        reached_nodes = {}
        reached_edges = []

        start_node = self.get_node(start_node_id)
        if not start_node:
            return {"nodes": {}, "edges": [], "paths": {}}

        reached_nodes[start_node_id] = start_node

        depth = 0
        while queue and depth < max_depth:
            next_level = []
            for current_id in queue:
                current_path = visited[current_id]
                
                # Check outgoing
                for edge in self._outgoing_edges.get(current_id, []):
                    to_id = edge.to_node_id
                    if to_id not in visited:
                        visited[to_id] = current_path + [to_id]
                        to_node = self.get_node(to_id)
                        if to_node:
                            reached_nodes[to_id] = to_node
                            reached_edges.append(edge)
                            next_level.append(to_id)
                            
                # Check incoming
                for edge in self._incoming_edges.get(current_id, []):
                    from_id = edge.from_node_id
                    if from_id not in visited:
                        visited[from_id] = current_path + [from_id]
                        from_node = self.get_node(from_id)
                        if from_node:
                            reached_nodes[from_id] = from_node
                            reached_edges.append(edge)
                            next_level.append(from_id)
            
            queue = next_level
            depth += 1

        # Format explanation with provenance details
        explanations = {}
        for node_id, path in visited.items():
            node = reached_nodes.get(node_id)
            provenance = getattr(node, "provenance", None)
            explanations[node_id] = {
                "path": " -> ".join(path),
                "provenance": provenance.model_dump() if provenance else "M5 default site content",
                "confidence": getattr(node, "confidence", 1.0),
            }

        return {
            "nodes": reached_nodes,
            "edges": reached_edges,
            "explanations": explanations,
        }

    def semantic_search(self, query: str) -> list[Any]:
        """Perform structured/keyword search over the node labels and properties."""
        self._ensure_indices()
        results = []
        query_lower = query.lower()
        
        # Search site graph nodes
        for node in self.site_graph.nodes:
            if query_lower in node.label.lower() or any(
                query_lower in str(v).lower() for v in node.properties.values()
            ):
                results.append(node)
                
        # Search enterprise nodes
        for node in self.enterprise_nodes:
            if query_lower in node.label.lower() or any(
                query_lower in str(v).lower() for v in node.properties.values()
            ):
                results.append(node)
                
        return results
