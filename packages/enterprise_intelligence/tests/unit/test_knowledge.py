"""Phase 2 — Enterprise Knowledge Graph unit tests.

Tests cover: models schema, provenance enforcement, integrated EnterpriseGraph BFS traversal,
semantic search, and repository operations with tenant isolation checks.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from brain.knowledge_graph.models import WebsiteKnowledgeGraph, KGNode, KGEdge, KGNodeType, KGEdgeType
from brain.repositories import KnowledgeGraphRepository
from brain.db import BrainBase
from enterprise_intelligence.db import create_enterprise_intelligence_tables, EnterpriseIntelligenceBase
from enterprise_intelligence.knowledge.models import (
    EnterpriseNode,
    EnterpriseEdge,
    ProvenanceRecord,
    EnterpriseNodeType,
    EnterpriseEdgeType,
)
from enterprise_intelligence.knowledge.enterprise_graph import EnterpriseGraph
from enterprise_intelligence.knowledge.repository import EnterpriseKnowledgeGraphRepository


def _make_provenance() -> ProvenanceRecord:
    return ProvenanceRecord(
        source_engine="test_engine",
        source_operation="test_operation",
        produced_at=datetime.now(timezone.utc),
        evidence_refs=["ref-1"],
    )


class TestKnowledgeModels:
    def test_node_provenance_mandatory(self):
        # Enforce that provenance is required on node instantiation
        with pytest.raises(ValueError):
            EnterpriseNode(
                node_type=EnterpriseNodeType.CUSTOMER,
                label="Acme Corp",
                site_id="s1",
                tenant_id="t1",
                # missing provenance
            )

    def test_edge_provenance_mandatory(self):
        with pytest.raises(ValueError):
            EnterpriseEdge(
                edge_type=EnterpriseEdgeType.TEMPORAL_STATE,
                from_node_id="n1",
                to_node_id="n2",
                site_id="s1",
                tenant_id="t1",
                # missing provenance
            )

    def test_valid_creation(self):
        prov = _make_provenance()
        node = EnterpriseNode(
            node_type=EnterpriseNodeType.CUSTOMER,
            label="Acme Corp",
            site_id="s1",
            tenant_id="t1",
            provenance=prov,
        )
        assert node.label == "Acme Corp"
        assert node.provenance.source_engine == "test_engine"


class TestEnterpriseGraph:
    @pytest.fixture
    def sample_graph(self) -> EnterpriseGraph:
        # Build a base site graph
        base_graph = WebsiteKnowledgeGraph(
            site_id="s1",
            tenant_id="t1",
            nodes=[
                KGNode(id="page-1", node_type=KGNodeType.PAGE, label="Homepage", site_id="s1", tenant_id="t1"),
                KGNode(id="keyword-1", node_type=KGNodeType.KEYWORD, label="SEO Tool", site_id="s1", tenant_id="t1"),
            ],
            edges=[
                KGEdge(id="e-1", edge_type=KGEdgeType.KEYWORD_TARGETING, from_node_id="page-1", to_node_id="keyword-1", site_id="s1", tenant_id="t1"),
            ]
        )
        
        prov = _make_provenance()
        ent_nodes = [
            EnterpriseNode(
                id="campaign-1",
                node_type=EnterpriseNodeType.CAMPAIGN,
                label="Summer Campaign",
                site_id="s1",
                tenant_id="t1",
                provenance=prov,
                properties={"budget": 5000},
            ),
            EnterpriseNode(
                id="revenue-1",
                node_type=EnterpriseNodeType.REVENUE,
                label="Conversion Revenue",
                site_id="s1",
                tenant_id="t1",
                provenance=prov,
            ),
        ]
        
        ent_edges = [
            EnterpriseEdge(
                id="ee-1",
                edge_type=EnterpriseEdgeType.ATTRIBUTION,
                from_node_id="campaign-1",
                to_node_id="page-1",
                site_id="s1",
                tenant_id="t1",
                provenance=prov,
            ),
            EnterpriseEdge(
                id="ee-2",
                edge_type=EnterpriseEdgeType.CAUSAL_LINK,
                from_node_id="page-1",
                to_node_id="revenue-1",
                site_id="s1",
                tenant_id="t1",
                provenance=prov,
                properties={"confidence": 0.85},
            ),
        ]
        
        return EnterpriseGraph(
            tenant_id="t1",
            site_id="s1",
            site_graph=base_graph,
            enterprise_nodes=ent_nodes,
            enterprise_edges=ent_edges,
        )

    def test_get_node(self, sample_graph):
        node = sample_graph.get_node("page-1")
        assert node is not None
        assert node.label == "Homepage"

        ent_node = sample_graph.get_node("campaign-1")
        assert ent_node is not None
        assert ent_node.label == "Summer Campaign"

    def test_get_neighbors(self, sample_graph):
        neighbors = sample_graph.get_neighbors("page-1")
        # page-1 connects to keyword-1 (site edge), campaign-1 (incoming), and revenue-1 (outgoing)
        neighbor_ids = {n.id for n in neighbors}
        assert "keyword-1" in neighbor_ids
        assert "campaign-1" in neighbor_ids
        assert "revenue-1" in neighbor_ids

    def test_traverse_explainable(self, sample_graph):
        result = sample_graph.traverse_explainable("campaign-1", max_depth=2)
        assert "nodes" in result
        assert "explanations" in result
        
        # campaign-1 -> page-1 -> revenue-1
        assert "campaign-1" in result["nodes"]
        assert "page-1" in result["nodes"]
        assert "revenue-1" in result["nodes"]
        
        # Path details
        assert result["explanations"]["revenue-1"]["path"] == "campaign-1 -> page-1 -> revenue-1"
        assert result["explanations"]["campaign-1"]["provenance"]["source_engine"] == "test_engine"

    def test_semantic_search(self, sample_graph):
        res1 = sample_graph.semantic_search("Summer")
        assert len(res1) == 1
        assert res1[0].id == "campaign-1"

        res2 = sample_graph.semantic_search("SEO")
        assert len(res2) == 1
        assert res2[0].id == "keyword-1"


class TestEnterpriseGraphRepository:
    @pytest.fixture
    def db_session_factory(self):
        engine = create_engine("sqlite:///:memory:")
        BrainBase.metadata.create_all(engine)
        create_enterprise_intelligence_tables(engine)
        return sessionmaker(bind=engine)

    def test_save_and_retrieve_integrated_graph(self, db_session_factory):
        site_repo = KnowledgeGraphRepository(db_session_factory, tenant_id="t1")
        repo = EnterpriseKnowledgeGraphRepository(db_session_factory, tenant_id="t1", site_graph_repo=site_repo)
        
        # Write base M5 graph nodes
        base_graph = WebsiteKnowledgeGraph(
            site_id="s1",
            tenant_id="t1",
            nodes=[
                KGNode(id="p-100", node_type=KGNodeType.PAGE, label="Product Page", site_id="s1", tenant_id="t1"),
            ]
        )
        site_repo.save_graph("t1", base_graph)
        
        # Save enterprise node and edge
        prov = _make_provenance()
        node = EnterpriseNode(
            id="cust-100",
            node_type=EnterpriseNodeType.CUSTOMER,
            label="Enterprise Customer A",
            site_id="s1",
            tenant_id="t1",
            provenance=prov,
        )
        repo.save_node(node)
        
        edge = EnterpriseEdge(
            id="ee-100",
            edge_type=EnterpriseEdgeType.OWNERSHIP,
            from_node_id="cust-100",
            to_node_id="p-100",
            site_id="s1",
            tenant_id="t1",
            provenance=prov,
        )
        repo.save_edge(edge)
        
        # Retrieve graph
        graph = repo.get_enterprise_graph("t1", "s1")
        assert len(graph.site_graph.nodes) == 1
        assert graph.site_graph.nodes[0].id == "p-100"
        assert len(graph.enterprise_nodes) == 1
        assert graph.enterprise_nodes[0].id == "cust-100"
        assert len(graph.enterprise_edges) == 1
        assert graph.enterprise_edges[0].id == "ee-100"

    def test_tenant_isolation(self, db_session_factory):
        site_repo_t1 = KnowledgeGraphRepository(db_session_factory, tenant_id="t1")
        repo_t1 = EnterpriseKnowledgeGraphRepository(db_session_factory, tenant_id="t1", site_graph_repo=site_repo_t1)
        
        site_repo_t2 = KnowledgeGraphRepository(db_session_factory, tenant_id="t2")
        repo_t2 = EnterpriseKnowledgeGraphRepository(db_session_factory, tenant_id="t2", site_graph_repo=site_repo_t2)

        prov = _make_provenance()
        n_t1 = EnterpriseNode(
            id="node-shared-t1",
            node_type=EnterpriseNodeType.CAMPAIGN,
            label="T1 Campaign",
            site_id="s1",
            tenant_id="t1",
            provenance=prov,
        )
        repo_t1.save_node(n_t1)
        
        n_t2 = EnterpriseNode(
            id="node-shared-t2",
            node_type=EnterpriseNodeType.CAMPAIGN,
            label="T2 Campaign",
            site_id="s1",
            tenant_id="t2",
            provenance=prov,
        )
        repo_t2.save_node(n_t2)

        # Separate retrievals
        g_t1 = repo_t1.get_enterprise_graph("t1", "s1")
        g_t2 = repo_t2.get_enterprise_graph("t2", "s1")

        assert len(g_t1.enterprise_nodes) == 1
        assert g_t1.enterprise_nodes[0].label == "T1 Campaign"

        assert len(g_t2.enterprise_nodes) == 1
        assert g_t2.enterprise_nodes[0].label == "T2 Campaign"
