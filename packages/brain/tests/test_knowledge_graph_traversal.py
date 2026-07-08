"""Tests for WebsiteKnowledgeGraph traversal API."""

from __future__ import annotations

from brain.knowledge_graph.models import (
    KGEdge,
    KGEdgeType,
    KGNode,
    KGNodeType,
    WebsiteKnowledgeGraph,
)


def _make_graph() -> WebsiteKnowledgeGraph:
    """Build a small fixture graph for traversal tests.

    Structure:
        p1 --internal_link--> p2
        p2 --internal_link--> p3
        e1 --entity_page_mention--> p1
        t1 --topic_membership--> p1
    """
    return WebsiteKnowledgeGraph(
        site_id="site-1",
        tenant_id="tenant-1",
        nodes=[
            KGNode(id="p1", node_type=KGNodeType.PAGE, label="Home", site_id="site-1", tenant_id="tenant-1"),
            KGNode(id="p2", node_type=KGNodeType.PAGE, label="About", site_id="site-1", tenant_id="tenant-1"),
            KGNode(id="p3", node_type=KGNodeType.PAGE, label="Contact", site_id="site-1", tenant_id="tenant-1"),
            KGNode(id="e1", node_type=KGNodeType.ENTITY, label="Python", site_id="site-1", tenant_id="tenant-1"),
            KGNode(id="t1", node_type=KGNodeType.TOPIC, label="SEO", site_id="site-1", tenant_id="tenant-1"),
        ],
        edges=[
            KGEdge(id="e-1", edge_type=KGEdgeType.INTERNAL_LINK, from_node_id="p1", to_node_id="p2", site_id="site-1", tenant_id="tenant-1"),
            KGEdge(id="e-2", edge_type=KGEdgeType.INTERNAL_LINK, from_node_id="p2", to_node_id="p3", site_id="site-1", tenant_id="tenant-1"),
            KGEdge(id="e-3", edge_type=KGEdgeType.ENTITY_PAGE_MENTION, from_node_id="e1", to_node_id="p1", site_id="site-1", tenant_id="tenant-1"),
            KGEdge(id="e-4", edge_type=KGEdgeType.TOPIC_MEMBERSHIP, from_node_id="t1", to_node_id="p1", site_id="site-1", tenant_id="tenant-1"),
        ],
    )


class TestGraphTraversal:
    """WebsiteKnowledgeGraph traversal methods."""

    def test_get_node(self) -> None:
        graph = _make_graph()
        node = graph.get_node("p1")
        assert node is not None
        assert node.label == "Home"

    def test_get_node_missing(self) -> None:
        graph = _make_graph()
        assert graph.get_node("nonexistent") is None

    def test_nodes_of_type_page(self) -> None:
        graph = _make_graph()
        pages = graph.nodes_of_type(KGNodeType.PAGE)
        assert len(pages) == 3

    def test_nodes_of_type_entity(self) -> None:
        graph = _make_graph()
        entities = graph.nodes_of_type(KGNodeType.ENTITY)
        assert len(entities) == 1

    def test_outgoing_edges(self) -> None:
        graph = _make_graph()
        out = graph.outgoing("p1")
        assert len(out) == 1
        assert out[0].to_node_id == "p2"

    def test_incoming_edges(self) -> None:
        graph = _make_graph()
        inc = graph.incoming("p1")
        # e1 → p1 and t1 → p1
        assert len(inc) == 2

    def test_neighbors_depth_1(self) -> None:
        graph = _make_graph()
        neighbors = graph.neighbors("p1", max_depth=1)
        neighbor_ids = {n.id for n in neighbors}
        # p1 → p2 (outgoing), e1 → p1 (incoming), t1 → p1 (incoming)
        assert "p2" in neighbor_ids
        assert "e1" in neighbor_ids
        assert "t1" in neighbor_ids
        assert "p1" not in neighbor_ids  # self excluded

    def test_neighbors_depth_2(self) -> None:
        graph = _make_graph()
        neighbors = graph.neighbors("p1", max_depth=2)
        neighbor_ids = {n.id for n in neighbors}
        # p3 is reachable through p1 → p2 → p3
        assert "p3" in neighbor_ids

    def test_subgraph_by_type(self) -> None:
        graph = _make_graph()
        page_subgraph = graph.subgraph(node_type=KGNodeType.PAGE)
        assert len(page_subgraph.nodes) == 3
        # Only edges between page nodes should remain
        for e in page_subgraph.edges:
            assert e.from_node_id.startswith("p")
            assert e.to_node_id.startswith("p")

    def test_subgraph_from_root(self) -> None:
        graph = _make_graph()
        sub = graph.subgraph(root_node_id="p1", max_depth=1)
        node_ids = {n.id for n in sub.nodes}
        assert "p1" in node_ids
        assert "p2" in node_ids
        assert "e1" in node_ids
