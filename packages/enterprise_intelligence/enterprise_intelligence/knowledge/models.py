"""Enterprise Knowledge Graph Models (Phase 2).

Extends M5's WebsiteKnowledgeGraph models with enterprise business context,
temporal and causal links, and structural provenance tracking.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field
from brain.knowledge_graph.models import KGNodeType, KGEdgeType

__all__ = [
    "EnterpriseNodeType",
    "EnterpriseEdgeType",
    "ProvenanceRecord",
    "EnterpriseNode",
    "EnterpriseEdge",
]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EnterpriseNodeType(str, Enum):
    """New enterprise business node types alongside M5's site-content nodes."""

    CUSTOMER = "customer"
    ORGANIZATION = "organization"
    TEAM = "team"
    PROJECT = "project"
    CAMPAIGN = "campaign"
    AD = "ad"
    CRM_RECORD = "crm_record"
    PRODUCT = "product"
    REVIEW = "review"
    EMAIL = "email"
    ANALYTICS_FACT = "analytics_fact"
    REVENUE = "revenue"
    AUTOMATION_HISTORY = "automation_history"
    LEARNING_HISTORY = "learning_history"
    DECISION_HISTORY = "decision_history"


class EnterpriseEdgeType(str, Enum):
    """New enterprise edge types, including temporal and causal links."""

    TEMPORAL_STATE = "temporal_state"  # state at time T
    CAUSAL_LINK = "causal_link"        # plausible causation (with confidence)
    OWNERSHIP = "ownership"
    ATTRIBUTION = "attribution"
    ASSOCIATION = "association"


class ProvenanceRecord(BaseModel):
    """Provenance tracking for data auditability.

    Mandatory on every write of a node or edge.
    """

    source_engine: str
    source_operation: str
    produced_at: datetime = Field(default_factory=_utc_now)
    evidence_refs: list[str] = Field(default_factory=list)


class EnterpriseNode(BaseModel):
    """Enterprise knowledge node carrying business/contextual information."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    node_type: str  # Can be KGNodeType (from M5) or EnterpriseNodeType
    label: str
    site_id: str
    tenant_id: str
    properties: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0
    version: int = 1
    provenance: ProvenanceRecord
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)


class EnterpriseEdge(BaseModel):
    """Enterprise edge carrying relationship, temporal, or causal data."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    edge_type: str  # Can be KGEdgeType (from M5) or EnterpriseEdgeType
    from_node_id: str
    to_node_id: str
    site_id: str
    tenant_id: str
    properties: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0
    provenance: ProvenanceRecord
    created_at: datetime = Field(default_factory=_utc_now)
