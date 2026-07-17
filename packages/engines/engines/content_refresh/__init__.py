"""Content Refresh Engine — detects thin, duplicate, and outdated content from
real crawl data (word_count, title/heading hashes, crawled_at) and proposes
concrete, evidence-backed refresh actions.

Reuses the Digital Twin's real persisted pages; never fabricates a content
score. "Outdated" is judged from ``crawled_at`` recency in the absence of a
publish-date signal — this is an honest proxy, documented as such.
"""
from __future__ import annotations

from engines.content_refresh.models import (
    ContentRefreshProposal,
    ContentRefreshReport,
    RefreshFinding,
)
from engines.content_refresh.service import ContentRefreshService

__all__ = [
    "ContentRefreshService",
    "RefreshFinding",
    "ContentRefreshProposal",
    "ContentRefreshReport",
]
