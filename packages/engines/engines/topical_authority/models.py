"""Topical Authority Engine output models (§4.7).

This is the **canonical** topic clustering model for the whole system.
Milestone 2.1's ``PillarContentFlag.linked_cluster_pages`` and
SiteArchitecture's ``TopicCluster`` are simplified consumer views of this
engine's topic graph (documented as such, not independently re-invented).
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

__all__ = [
    "EntityNode",
    "EntityEdge",
    "EntityGraph",
    "TopicNode",
    "TopicEdge",
    "TopicGraph",
    "TopicalAuthorityReport",
]


class EntityNode(BaseModel):
    """One named entity in the sitewide entity graph."""

    entity_id: str                     # stable hash of entity text + type
    text: str
    entity_type: str = "other"        # person | org | place | product | other
    page_count: int = 0               # how many pages mention this entity
    confidence: float | None = None


class EntityEdge(BaseModel):
    """Co-occurrence link between two entities across the site."""

    from_entity_id: str
    to_entity_id: str
    co_occurrence_count: int = 0
    weight: float = 0.0


class EntityGraph(BaseModel):
    """Sitewide entity graph (§4.7, aggregated from all KO named_entities)."""

    nodes: list[EntityNode] = Field(default_factory=list)
    edges: list[EntityEdge] = Field(default_factory=list)


class TopicNode(BaseModel):
    """One topic cluster node in the sitewide topic graph."""

    topic_id: str
    label: str
    pillar_page_id: str | None = None
    supporting_page_ids: list[str] = Field(default_factory=list)
    depth: int = 0
    coverage_score: float = 0.0


class TopicEdge(BaseModel):
    """Relationship between two topic clusters."""

    from_topic_id: str
    to_topic_id: str
    relationship_type: str = "related"   # related | subtopic | supporting
    weight: float = 0.0


class TopicGraph(BaseModel):
    """Sitewide topic graph — the canonical clustering model (§4.7)."""

    nodes: list[TopicNode] = Field(default_factory=list)
    edges: list[TopicEdge] = Field(default_factory=list)


class TopicalAuthorityReport(BaseModel):
    """Sitewide topical authority analysis (§4.7)."""

    site_id: str
    tenant_id: str
    version: int = 1
    entity_graph: EntityGraph = Field(default_factory=EntityGraph)
    topic_graph: TopicGraph = Field(default_factory=TopicGraph)
    cornerstone_pages: list[str] = Field(default_factory=list)   # page_ids
    supporting_page_map: dict[str, list[str]] = Field(default_factory=dict)  # pillar_id -> supporters
    authority_score: float = 0.0          # composite sitewide score 0.0-1.0
    coverage_score: float = 0.0           # topic coverage 0.0-1.0
    missing_entities: list[str] = Field(default_factory=list)   # AI-inferred gaps
    missing_concepts: list[str] = Field(default_factory=list)
    related_topic_suggestions: list[str] = Field(default_factory=list)
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
