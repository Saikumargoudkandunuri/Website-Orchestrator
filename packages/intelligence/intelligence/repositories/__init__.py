"""Intelligence persistence layer (Milestone 2).

Append-only, versioned KnowledgeObject storage plus AIInvocation audit records
and crawl-time page snapshots, on a dedicated SQLAlchemy Base so the Milestone 1
schema/migrations are untouched. :func:`create_intelligence_tables` provisions
the tables on a shared engine (the composition root calls it, mirroring how
Milestone 1 calls ``Base.metadata.create_all``).
"""

from sqlalchemy import Engine

from intelligence.repositories.ai_invocation_repository import AIInvocationRepository
from intelligence.repositories.knowledge_object_repository import (
    KnowledgeObjectRepository,
    VersionInfo,
)
from intelligence.repositories.models_orm import (
    AIInvocationRow,
    IntelligenceBase,
    KnowledgeObjectRow,
    PageSnapshotRow,
)
from intelligence.repositories.page_snapshot_repository import PageSnapshotRepository

__all__ = [
    "IntelligenceBase",
    "KnowledgeObjectRow",
    "AIInvocationRow",
    "PageSnapshotRow",
    "KnowledgeObjectRepository",
    "AIInvocationRepository",
    "PageSnapshotRepository",
    "VersionInfo",
    "create_intelligence_tables",
]


def create_intelligence_tables(engine: Engine) -> None:
    """Create the intelligence tables on ``engine`` if they do not exist."""
    IntelligenceBase.metadata.create_all(engine)
