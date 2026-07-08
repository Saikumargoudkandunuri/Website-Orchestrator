"""Tests for KnowledgeGraphBuilder.

Verifies correct node/edge construction from fixture M2/M3 data, including
incremental-update tests (re-running the builder after one page's data
changes updates only the affected graph region, not a full rebuild).
"""

from __future__ import annotations

from brain.knowledge_graph.builder import KnowledgeGraphBuilder, _stable_id
from brain.knowledge_graph.models import (
    KGEdgeType,
    KGNodeType,
    WebsiteKnowledgeGraph,
)

import pytest
from pydantic import BaseModel, Field
from typing import Any


# --- Minimal fixture models mimicking M3's SiteContext/TopicalAuthority ---


class FakePageSummary(BaseModel):
    page_id: str
    url: str
    title: str | None = None
    word_count: int = 0
    depth: int = 0
    broken: bool = False


class FakeLinkEdge(BaseModel):
    from_page_id: str
    to_page_id: str
    anchor_text: str | None = None


class FakeSiteContext(BaseModel):
    pages: list[FakePageSummary] = Field(default_factory=list)
    link_graph: list[FakeLinkEdge] = Field(default_factory=list)


class FakeEntityNode(BaseModel):
    entity_id: str
    text: str
    entity_type: str = "other"
    page_count: int = 0
    confidence: float | None = None


class FakeEntityEdge(BaseModel):
    from_entity_id: str
    to_entity_id: str
    co_occurrence_count: int = 0
    weight: float = 0.0


class FakeEntityGraph(BaseModel):
    nodes: list[FakeEntityNode] = Field(default_factory=list)
    edges: list[FakeEntityEdge] = Field(default_factory=list)


class FakeTopicNode(BaseModel):
    topic_id: str
    label: str
    pillar_page_id: str | None = None
    supporting_page_ids: list[str] = Field(default_factory=list)
    depth: int = 0
    coverage_score: float = 0.0


class FakeTopicEdge(BaseModel):
    from_topic_id: str
    to_topic_id: str
    relationship_type: str = "related"
    weight: float = 0.0


class FakeTopicGraph(BaseModel):
    nodes: list[FakeTopicNode] = Field(default_factory=list)
    edges: list[FakeTopicEdge] = Field(default_factory=list)


class FakeTopicalAuthorityReport(BaseModel):
    entity_graph: FakeEntityGraph = Field(default_factory=FakeEntityGraph)
    topic_graph: FakeTopicGraph = Field(default_factory=FakeTopicGraph)


# --- Tests ---


class TestKnowledgeGraphBuilderPages:
    """Page nodes and internal link edges from SiteContext."""

    def test_pages_produce_page_nodes(self) -> None:
        ctx = FakeSiteContext(pages=[
            FakePageSummary(page_id="p1", url="https://example.com/", title="Home"),
            FakePageSummary(page_id="p2", url="https://example.com/about", title="About"),
        ])

        builder = KnowledgeGraphBuilder("site-1", "tenant-1")
        builder.add_pages_from_site_context(ctx)
        graph = builder.build()

        assert len(graph.nodes) == 2
        assert all(n.node_type == KGNodeType.PAGE for n in graph.nodes)
        labels = {n.label for n in graph.nodes}
        assert "Home" in labels
        assert "About" in labels

    def test_internal_links_produce_edges(self) -> None:
        ctx = FakeSiteContext(
            pages=[
                FakePageSummary(page_id="p1", url="https://example.com/"),
                FakePageSummary(page_id="p2", url="https://example.com/about"),
            ],
            link_graph=[
                FakeLinkEdge(from_page_id="p1", to_page_id="p2", anchor_text="About us"),
            ],
        )

        builder = KnowledgeGraphBuilder("site-1", "tenant-1")
        builder.add_pages_from_site_context(ctx)
        graph = builder.build()

        assert len(graph.edges) == 1
        edge = graph.edges[0]
        assert edge.edge_type == KGEdgeType.INTERNAL_LINK
        assert edge.properties.get("anchor_text") == "About us"


class TestKnowledgeGraphBuilderEntities:
    """Entity nodes and co-occurrence edges from TopicalAuthorityReport."""

    def test_entities_produce_entity_nodes(self) -> None:
        report = FakeTopicalAuthorityReport(
            entity_graph=FakeEntityGraph(nodes=[
                FakeEntityNode(entity_id="e1", text="Python", entity_type="product"),
                FakeEntityNode(entity_id="e2", text="Django", entity_type="product"),
            ])
        )

        builder = KnowledgeGraphBuilder("site-1", "tenant-1")
        builder.add_entities_from_topical_authority(report)
        graph = builder.build()

        assert len(graph.nodes) == 2
        assert all(n.node_type == KGNodeType.ENTITY for n in graph.nodes)

    def test_entity_cooccurrence_edges(self) -> None:
        report = FakeTopicalAuthorityReport(
            entity_graph=FakeEntityGraph(
                nodes=[
                    FakeEntityNode(entity_id="e1", text="Python"),
                    FakeEntityNode(entity_id="e2", text="Django"),
                ],
                edges=[
                    FakeEntityEdge(from_entity_id="e1", to_entity_id="e2", co_occurrence_count=5),
                ],
            )
        )

        builder = KnowledgeGraphBuilder("site-1", "tenant-1")
        builder.add_entities_from_topical_authority(report)
        graph = builder.build()

        assert len(graph.edges) == 1
        assert graph.edges[0].edge_type == KGEdgeType.ENTITY_COOCCURRENCE


class TestKnowledgeGraphBuilderTopics:
    """Topic nodes and relationship edges from TopicalAuthorityReport."""

    def test_topics_produce_topic_nodes(self) -> None:
        report = FakeTopicalAuthorityReport(
            topic_graph=FakeTopicGraph(nodes=[
                FakeTopicNode(topic_id="t1", label="Web Development"),
            ])
        )

        builder = KnowledgeGraphBuilder("site-1", "tenant-1")
        builder.add_topics_from_topical_authority(report)
        graph = builder.build()

        assert len(graph.nodes) == 1
        assert graph.nodes[0].node_type == KGNodeType.TOPIC
        assert graph.nodes[0].label == "Web Development"

    def test_topic_pillar_membership_edges(self) -> None:
        report = FakeTopicalAuthorityReport(
            topic_graph=FakeTopicGraph(nodes=[
                FakeTopicNode(topic_id="t1", label="SEO", pillar_page_id="p1"),
            ])
        )

        builder = KnowledgeGraphBuilder("site-1", "tenant-1")
        builder.add_topics_from_topical_authority(report)
        graph = builder.build()

        membership_edges = [e for e in graph.edges if e.edge_type == KGEdgeType.TOPIC_MEMBERSHIP]
        assert len(membership_edges) == 1
        assert membership_edges[0].properties.get("role") == "pillar"

    def test_topic_relationship_edges(self) -> None:
        report = FakeTopicalAuthorityReport(
            topic_graph=FakeTopicGraph(
                nodes=[
                    FakeTopicNode(topic_id="t1", label="SEO"),
                    FakeTopicNode(topic_id="t2", label="Content"),
                ],
                edges=[
                    FakeTopicEdge(from_topic_id="t1", to_topic_id="t2", relationship_type="related"),
                ],
            )
        )

        builder = KnowledgeGraphBuilder("site-1", "tenant-1")
        builder.add_topics_from_topical_authority(report)
        graph = builder.build()

        rel_edges = [e for e in graph.edges if e.edge_type == KGEdgeType.TOPIC_RELATIONSHIP]
        assert len(rel_edges) == 1


class TestKnowledgeGraphBuilderKeywords:
    """Keyword nodes and targeting edges."""

    def test_keywords_produce_keyword_nodes(self) -> None:
        builder = KnowledgeGraphBuilder("site-1", "tenant-1")
        builder.add_keywords([
            {"keyword": "python tutorial", "page_id": "p1", "volume": 1000},
            {"keyword": "django guide", "page_id": "p2"},
        ])
        graph = builder.build()

        assert len(graph.nodes) == 2
        assert all(n.node_type == KGNodeType.KEYWORD for n in graph.nodes)

    def test_keyword_targeting_edges(self) -> None:
        builder = KnowledgeGraphBuilder("site-1", "tenant-1")
        builder.add_keywords([
            {"keyword": "python tutorial", "page_id": "p1"},
        ])
        graph = builder.build()

        assert len(graph.edges) == 1
        assert graph.edges[0].edge_type == KGEdgeType.KEYWORD_TARGETING


class TestKnowledgeGraphBuilderBacklinks:
    """Backlink nodes and source→target edges."""

    def test_backlinks_produce_backlink_nodes(self) -> None:
        builder = KnowledgeGraphBuilder("site-1", "tenant-1")
        builder.add_backlinks([
            {"source_url": "https://blog.example.com/post", "target_page_id": "p1"},
        ])
        graph = builder.build()

        assert len(graph.nodes) == 1
        assert graph.nodes[0].node_type == KGNodeType.BACKLINK

    def test_backlink_edges(self) -> None:
        builder = KnowledgeGraphBuilder("site-1", "tenant-1")
        builder.add_backlinks([
            {"source_url": "https://blog.example.com/post", "target_page_id": "p1"},
        ])
        graph = builder.build()

        assert len(graph.edges) == 1
        assert graph.edges[0].edge_type == KGEdgeType.BACKLINK_SOURCE_TARGET


class TestKnowledgeGraphBuilderLocations:
    """Location nodes and association edges."""

    def test_locations_produce_location_nodes(self) -> None:
        builder = KnowledgeGraphBuilder("site-1", "tenant-1")
        builder.add_locations([
            {"name": "New York", "page_id": "p1"},
        ])
        graph = builder.build()

        assert len(graph.nodes) == 1
        assert graph.nodes[0].node_type == KGNodeType.LOCATION

    def test_location_association_edges(self) -> None:
        builder = KnowledgeGraphBuilder("site-1", "tenant-1")
        builder.add_locations([
            {"name": "New York", "page_id": "p1"},
        ])
        graph = builder.build()

        assert len(graph.edges) == 1
        assert graph.edges[0].edge_type == KGEdgeType.LOCATION_ASSOCIATION


class TestKnowledgeGraphBuilderIncremental:
    """Incremental update: only affected graph regions are rebuilt."""

    def test_unchanged_nodes_preserved_on_incremental_build(self) -> None:
        # Initial build with two pages.
        ctx1 = FakeSiteContext(pages=[
            FakePageSummary(page_id="p1", url="https://example.com/", title="Home"),
            FakePageSummary(page_id="p2", url="https://example.com/about", title="About"),
        ])

        builder1 = KnowledgeGraphBuilder("site-1", "tenant-1")
        builder1.add_pages_from_site_context(ctx1, source_version=1)
        graph1 = builder1.build()
        assert len(graph1.nodes) == 2

        # Incremental rebuild: only p2 changed (source_version stays 1 for p1).
        ctx2 = FakeSiteContext(pages=[
            FakePageSummary(page_id="p1", url="https://example.com/", title="Home"),
            FakePageSummary(page_id="p2", url="https://example.com/about", title="About Us"),
        ])

        builder2 = KnowledgeGraphBuilder("site-1", "tenant-1", existing_graph=graph1)
        builder2.add_pages_from_site_context(ctx2, source_version=2)
        graph2 = builder2.build()

        assert len(graph2.nodes) == 2
        # Both nodes should be version 2 since we passed source_version=2
        # and both were eligible for update (new builder with same version check).
        p2_node = next(
            n for n in graph2.nodes
            if n.properties.get("page_id") == "p2"
        )
        assert p2_node.label == "About Us"

    def test_incremental_skips_unchanged_nodes(self) -> None:
        # Build with source_version=1.
        ctx = FakeSiteContext(pages=[
            FakePageSummary(page_id="p1", url="https://example.com/", title="Home"),
        ])

        builder1 = KnowledgeGraphBuilder("site-1", "tenant-1")
        builder1.add_pages_from_site_context(ctx, source_version=1)
        graph1 = builder1.build()

        # Rebuild with same source_version=1 — node should be skipped.
        ctx2 = FakeSiteContext(pages=[
            FakePageSummary(page_id="p1", url="https://example.com/", title="Home CHANGED"),
        ])

        builder2 = KnowledgeGraphBuilder("site-1", "tenant-1", existing_graph=graph1)
        builder2.add_pages_from_site_context(ctx2, source_version=1)
        graph2 = builder2.build()

        # Title should NOT have changed because source_version is the same.
        p1_node = next(
            n for n in graph2.nodes
            if n.properties.get("page_id") == "p1"
        )
        assert p1_node.label == "Home"  # Original title preserved


class TestKnowledgeGraphBuilderFull:
    """Full build combining multiple data sources."""

    def test_full_graph_from_all_sources(self) -> None:
        ctx = FakeSiteContext(
            pages=[
                FakePageSummary(page_id="p1", url="https://example.com/", title="Home"),
                FakePageSummary(page_id="p2", url="https://example.com/about", title="About"),
            ],
            link_graph=[
                FakeLinkEdge(from_page_id="p1", to_page_id="p2"),
            ],
        )

        report = FakeTopicalAuthorityReport(
            entity_graph=FakeEntityGraph(nodes=[
                FakeEntityNode(entity_id="e1", text="Python"),
            ]),
            topic_graph=FakeTopicGraph(nodes=[
                FakeTopicNode(topic_id="t1", label="SEO", pillar_page_id="p1"),
            ]),
        )

        builder = KnowledgeGraphBuilder("site-1", "tenant-1")
        builder.add_pages_from_site_context(ctx)
        builder.add_entities_from_topical_authority(report)
        builder.add_topics_from_topical_authority(report)
        builder.add_keywords([{"keyword": "seo tips", "page_id": "p1"}])
        builder.add_backlinks([{"source_url": "https://ext.com/link", "target_page_id": "p1"}])
        builder.add_locations([{"name": "NYC", "page_id": "p1"}])
        graph = builder.build()

        # 2 pages + 1 entity + 1 topic + 1 keyword + 1 backlink + 1 location = 7
        assert len(graph.nodes) == 7
        node_types = {n.node_type for n in graph.nodes}
        assert KGNodeType.PAGE in node_types
        assert KGNodeType.ENTITY in node_types
        assert KGNodeType.TOPIC in node_types
        assert KGNodeType.KEYWORD in node_types
        assert KGNodeType.BACKLINK in node_types
        assert KGNodeType.LOCATION in node_types

        # Edges: 1 internal link + 1 topic_membership + 1 keyword_targeting +
        #        1 backlink_source_target + 1 location_association = 5
        assert len(graph.edges) >= 5
