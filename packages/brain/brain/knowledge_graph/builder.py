"""KnowledgeGraphBuilder — assembles the Website Knowledge Graph from M2/M3/M4 outputs.

Consumes existing engine outputs (KnowledgeObjects, TopicalAuthority, SiteContext,
Backlinks, Keywords, LocalSEO) to build a connected graph structure.  Supports
incremental updates: tracks node source versions so only affected graph regions
are rebuilt when underlying data changes.

This is the direct evolution of M3's ``SiteContextBuilder`` pattern — it reads
from the same sources and more, producing a richer, queryable structure.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any

from brain.knowledge_graph.models import (
    KGEdge,
    KGEdgeType,
    KGNode,
    KGNodeType,
    WebsiteKnowledgeGraph,
)

__all__ = ["KnowledgeGraphBuilder"]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _stable_id(*parts: str) -> str:
    """Deterministic node/edge ID from component parts."""
    return hashlib.sha256(":".join(parts).encode()).hexdigest()[:24]


def _new_edge_id() -> str:
    return uuid.uuid4().hex[:24]


class KnowledgeGraphBuilder:
    """Incrementally builds a ``WebsiteKnowledgeGraph`` from engine outputs.

    Usage::

        builder = KnowledgeGraphBuilder(site_id, tenant_id)
        builder.add_pages_from_site_context(site_context)
        builder.add_entities_from_topical_authority(ta_report)
        builder.add_topics_from_topical_authority(ta_report)
        builder.add_keywords_from_keyword_report(kw_report)
        builder.add_backlinks_from_backlink_report(bl_report)
        builder.add_locations_from_local_seo(local_report)
        graph = builder.build()

    For incremental updates, pass an ``existing_graph`` to the constructor.
    The builder compares source_version on existing nodes and only replaces
    nodes/edges whose source data has changed.
    """

    def __init__(
        self,
        site_id: str,
        tenant_id: str,
        *,
        existing_graph: WebsiteKnowledgeGraph | None = None,
    ) -> None:
        self._site_id = site_id
        self._tenant_id = tenant_id
        self._nodes: dict[str, KGNode] = {}
        self._edges: list[KGEdge] = []
        # Load existing graph state for incremental comparison.
        self._existing_versions: dict[str, int] = {}
        if existing_graph:
            for node in existing_graph.nodes:
                self._existing_versions[node.id] = node.source_version
            # Carry forward existing nodes/edges as baseline.
            for node in existing_graph.nodes:
                self._nodes[node.id] = node
            self._edges = list(existing_graph.edges)

    def _should_update(self, node_id: str, source_version: int) -> bool:
        """Return True if this node's source has changed since last build."""
        existing = self._existing_versions.get(node_id)
        return existing is None or existing != source_version

    def _remove_edges_for_node(self, node_id: str) -> None:
        """Remove all edges touching ``node_id`` before rebuilding them."""
        self._edges = [
            e for e in self._edges
            if e.from_node_id != node_id and e.to_node_id != node_id
        ]

    def add_pages_from_site_context(
        self, site_context: Any, *, source_version: int = 0
    ) -> None:
        """Add page nodes and internal link edges from M3's SiteContext."""
        # Remove stale page edges first.
        pages_to_update: set[str] = set()

        for page in site_context.pages:
            node_id = _stable_id("page", self._site_id, page.page_id)
            if not self._should_update(node_id, source_version):
                continue
            pages_to_update.add(node_id)
            self._remove_edges_for_node(node_id)
            self._nodes[node_id] = KGNode(
                id=node_id,
                node_type=KGNodeType.PAGE,
                label=page.title or page.url,
                site_id=self._site_id,
                tenant_id=self._tenant_id,
                properties={
                    "page_id": page.page_id,
                    "url": page.url,
                    "word_count": page.word_count,
                    "depth": page.depth,
                    "broken": page.broken,
                },
                source_version=source_version,
            )

        # Add internal link edges.
        for link in site_context.link_graph:
            from_id = _stable_id("page", self._site_id, link.from_page_id)
            to_id = _stable_id("page", self._site_id, link.to_page_id)
            if from_id in pages_to_update or to_id in pages_to_update:
                self._edges.append(KGEdge(
                    id=_new_edge_id(),
                    edge_type=KGEdgeType.INTERNAL_LINK,
                    from_node_id=from_id,
                    to_node_id=to_id,
                    site_id=self._site_id,
                    tenant_id=self._tenant_id,
                    properties={"anchor_text": link.anchor_text},
                ))

    def add_entities_from_topical_authority(
        self, report: Any, *, source_version: int = 0
    ) -> None:
        """Add entity nodes and co-occurrence edges from TopicalAuthorityReport."""
        if not hasattr(report, "entity_graph"):
            return
        eg = report.entity_graph

        for entity in eg.nodes:
            node_id = _stable_id("entity", self._site_id, entity.entity_id)
            if not self._should_update(node_id, source_version):
                continue
            self._remove_edges_for_node(node_id)
            self._nodes[node_id] = KGNode(
                id=node_id,
                node_type=KGNodeType.ENTITY,
                label=entity.text,
                site_id=self._site_id,
                tenant_id=self._tenant_id,
                properties={
                    "entity_id": entity.entity_id,
                    "entity_type": entity.entity_type,
                    "page_count": entity.page_count,
                    "confidence": entity.confidence,
                },
                source_version=source_version,
            )

        for edge in eg.edges:
            from_id = _stable_id("entity", self._site_id, edge.from_entity_id)
            to_id = _stable_id("entity", self._site_id, edge.to_entity_id)
            self._edges.append(KGEdge(
                id=_new_edge_id(),
                edge_type=KGEdgeType.ENTITY_COOCCURRENCE,
                from_node_id=from_id,
                to_node_id=to_id,
                site_id=self._site_id,
                tenant_id=self._tenant_id,
                properties={
                    "co_occurrence_count": edge.co_occurrence_count,
                    "weight": edge.weight,
                },
            ))

    def add_topics_from_topical_authority(
        self, report: Any, *, source_version: int = 0
    ) -> None:
        """Add topic nodes and relationship edges from TopicalAuthorityReport."""
        if not hasattr(report, "topic_graph"):
            return
        tg = report.topic_graph

        for topic in tg.nodes:
            node_id = _stable_id("topic", self._site_id, topic.topic_id)
            if not self._should_update(node_id, source_version):
                continue
            self._remove_edges_for_node(node_id)
            self._nodes[node_id] = KGNode(
                id=node_id,
                node_type=KGNodeType.TOPIC,
                label=topic.label,
                site_id=self._site_id,
                tenant_id=self._tenant_id,
                properties={
                    "topic_id": topic.topic_id,
                    "pillar_page_id": topic.pillar_page_id,
                    "coverage_score": topic.coverage_score,
                    "depth": topic.depth,
                },
                source_version=source_version,
            )

            # Topic → pillar page membership edge
            if topic.pillar_page_id:
                page_node_id = _stable_id("page", self._site_id, topic.pillar_page_id)
                self._edges.append(KGEdge(
                    id=_new_edge_id(),
                    edge_type=KGEdgeType.TOPIC_MEMBERSHIP,
                    from_node_id=page_node_id,
                    to_node_id=node_id,
                    site_id=self._site_id,
                    tenant_id=self._tenant_id,
                    properties={"role": "pillar"},
                ))

            # Supporting pages → topic edges
            for sp_id in topic.supporting_page_ids:
                page_node_id = _stable_id("page", self._site_id, sp_id)
                self._edges.append(KGEdge(
                    id=_new_edge_id(),
                    edge_type=KGEdgeType.TOPIC_MEMBERSHIP,
                    from_node_id=page_node_id,
                    to_node_id=node_id,
                    site_id=self._site_id,
                    tenant_id=self._tenant_id,
                    properties={"role": "supporting"},
                ))

        for edge in tg.edges:
            from_id = _stable_id("topic", self._site_id, edge.from_topic_id)
            to_id = _stable_id("topic", self._site_id, edge.to_topic_id)
            self._edges.append(KGEdge(
                id=_new_edge_id(),
                edge_type=KGEdgeType.TOPIC_RELATIONSHIP,
                from_node_id=from_id,
                to_node_id=to_id,
                site_id=self._site_id,
                tenant_id=self._tenant_id,
                properties={
                    "relationship_type": edge.relationship_type,
                    "weight": edge.weight,
                },
            ))

    def add_keywords(
        self,
        keywords: list[dict[str, Any]],
        *,
        source_version: int = 0,
    ) -> None:
        """Add keyword nodes and targeting edges.

        ``keywords`` is a list of dicts with at minimum ``keyword``, ``page_id``.
        """
        for kw in keywords:
            keyword_text = kw.get("keyword", "")
            page_id = kw.get("page_id")
            node_id = _stable_id("keyword", self._site_id, keyword_text)
            if not self._should_update(node_id, source_version):
                continue
            self._remove_edges_for_node(node_id)
            self._nodes[node_id] = KGNode(
                id=node_id,
                node_type=KGNodeType.KEYWORD,
                label=keyword_text,
                site_id=self._site_id,
                tenant_id=self._tenant_id,
                properties={k: v for k, v in kw.items() if k != "keyword"},
                source_version=source_version,
            )
            if page_id:
                page_node_id = _stable_id("page", self._site_id, page_id)
                self._edges.append(KGEdge(
                    id=_new_edge_id(),
                    edge_type=KGEdgeType.KEYWORD_TARGETING,
                    from_node_id=page_node_id,
                    to_node_id=node_id,
                    site_id=self._site_id,
                    tenant_id=self._tenant_id,
                ))

    def add_backlinks(
        self,
        backlinks: list[dict[str, Any]],
        *,
        source_version: int = 0,
    ) -> None:
        """Add backlink nodes and source→target edges."""
        for bl in backlinks:
            source_url = bl.get("source_url", "")
            target_page_id = bl.get("target_page_id")
            node_id = _stable_id("backlink", self._site_id, source_url)
            if not self._should_update(node_id, source_version):
                continue
            self._remove_edges_for_node(node_id)
            self._nodes[node_id] = KGNode(
                id=node_id,
                node_type=KGNodeType.BACKLINK,
                label=source_url,
                site_id=self._site_id,
                tenant_id=self._tenant_id,
                properties={k: v for k, v in bl.items() if k != "source_url"},
                source_version=source_version,
            )
            if target_page_id:
                page_node_id = _stable_id("page", self._site_id, target_page_id)
                self._edges.append(KGEdge(
                    id=_new_edge_id(),
                    edge_type=KGEdgeType.BACKLINK_SOURCE_TARGET,
                    from_node_id=node_id,
                    to_node_id=page_node_id,
                    site_id=self._site_id,
                    tenant_id=self._tenant_id,
                ))

    def add_locations(
        self,
        locations: list[dict[str, Any]],
        *,
        source_version: int = 0,
    ) -> None:
        """Add location nodes and associations to pages."""
        for loc in locations:
            loc_name = loc.get("name", "")
            page_id = loc.get("page_id")
            node_id = _stable_id("location", self._site_id, loc_name)
            if not self._should_update(node_id, source_version):
                continue
            self._remove_edges_for_node(node_id)
            self._nodes[node_id] = KGNode(
                id=node_id,
                node_type=KGNodeType.LOCATION,
                label=loc_name,
                site_id=self._site_id,
                tenant_id=self._tenant_id,
                properties={k: v for k, v in loc.items() if k != "name"},
                source_version=source_version,
            )
            if page_id:
                page_node_id = _stable_id("page", self._site_id, page_id)
                self._edges.append(KGEdge(
                    id=_new_edge_id(),
                    edge_type=KGEdgeType.LOCATION_ASSOCIATION,
                    from_node_id=page_node_id,
                    to_node_id=node_id,
                    site_id=self._site_id,
                    tenant_id=self._tenant_id,
                ))

    def build(self) -> WebsiteKnowledgeGraph:
        """Assemble and return the ``WebsiteKnowledgeGraph``."""
        return WebsiteKnowledgeGraph(
            site_id=self._site_id,
            tenant_id=self._tenant_id,
            nodes=list(self._nodes.values()),
            edges=list(self._edges),
        )
