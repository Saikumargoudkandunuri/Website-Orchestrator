"""Site Architecture Engine output models (§4.2).

Sitewide scope: built from SiteContext.link_graph.
Includes a visualization-ready graph export (§4.2 explicit deliverable).
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

__all__ = [
    "HierarchyNode",
    "TopicCluster",
    "GraphNode",
    "GraphEdge",
    "GraphExport",
    "SiteArchitectureReport",
]


class HierarchyNode(BaseModel):
    """One node in the inferred site hierarchy."""

    page_id: str
    url: str
    depth: int = 0
    parent_page_id: str | None = None
    children: list[str] = Field(default_factory=list)  # page_ids of direct children
    link_equity_score: float = 0.0  # PageRank-style score


class TopicCluster(BaseModel):
    """A group of topically related pages (§4.2, extends §13.2 pillar heuristic).

    This is the canonical cluster model — Milestone 2.1's
    ``PillarContentFlag.linked_cluster_pages`` is a simplified consumer view.
    """

    cluster_id: str
    topic_label: str
    pillar_page_id: str | None = None    # cornerstone/pillar page for this cluster
    member_page_ids: list[str] = Field(default_factory=list)
    strength: float = 0.0               # intra-cluster link density, 0.0-1.0
    source: str = "inferred"


class GraphNode(BaseModel):
    """One node in the visualization-ready graph export."""

    id: str           # page_id
    label: str        # title or slug
    depth: int = 0
    score: float = 0.0
    cluster_id: str | None = None


class GraphEdge(BaseModel):
    """One edge in the visualization-ready graph export."""

    source: str    # from page_id
    target: str    # to page_id
    weight: float = 1.0
    anchor_text: str | None = None


class GraphExport(BaseModel):
    """Visualization-ready graph export (§4.2 explicit deliverable)."""

    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


class SiteArchitectureReport(BaseModel):
    """Sitewide site architecture analysis (§4.2)."""

    site_id: str
    tenant_id: str
    version: int = 1
    crawl_id: str | None = None
    hierarchy: list[HierarchyNode] = Field(default_factory=list)
    clusters: list[TopicCluster] = Field(default_factory=list)
    link_equity_scores: dict[str, float] = Field(default_factory=dict)  # page_id -> score
    structure_score: float = 0.0   # composite 0.0-1.0
    graph_export: GraphExport = Field(default_factory=GraphExport)
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
