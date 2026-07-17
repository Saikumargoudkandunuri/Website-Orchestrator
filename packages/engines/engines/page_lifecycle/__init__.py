"""Page Lifecycle Engine — decides create/edit/delete/merge/pillar/cluster-expand
actions from real Digital Twin data: the real internal-link graph (authority,
orphans), real content-refresh findings (thin/duplicate), and real page
inventory. Never fabricates a page or a metric; every decision cites the real
evidence it was computed from.
"""
from __future__ import annotations

from engines.page_lifecycle.models import LifecycleDecision, PageLifecycleReport
from engines.page_lifecycle.service import PageLifecycleService

__all__ = ["PageLifecycleService", "LifecycleDecision", "PageLifecycleReport"]
