"""Digital_Twin subsystem — relational, queryable representation of the site.

Stores pages, links, metadata, and detected issues with freshness metadata in a
relational model only — no graph database and no embeddings (Req 3.1, 3.7).
Every table carries a non-null ``tenant_id`` (Req 14.4). Depends only on
Core_Package.
"""

from digital_twin.models import (
    AuditTrail,
    Base,
    Issue,
    Link,
    Page,
    PageMetadata,
    SuggestedFix,
)
from digital_twin.repository import (
    DEFAULT_STALENESS_THRESHOLD_SECONDS,
    DigitalTwinRepository,
)

__all__ = [
    "Base",
    "Page",
    "Link",
    "PageMetadata",
    "Issue",
    "SuggestedFix",
    "AuditTrail",
    "DigitalTwinRepository",
    "DEFAULT_STALENESS_THRESHOLD_SECONDS",
]
