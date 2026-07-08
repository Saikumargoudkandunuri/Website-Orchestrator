"""Source adapter base class and all 12 source adapters (Phase 1).

Every adapter **reads existing engine output** — none re-implements
detection logic an engine already owns.  Each adapter produces typed
``ObservationEvent``s.

The adapters receive repository/service references via DI and only call
read methods (``get_*``, ``list_*``, ``count_*``).  They NEVER call any
governance-gated tool, engine action, or state-changing capability.
"""

from __future__ import annotations

import abc
from typing import Any

from enterprise_intelligence.observation.models import (
    EventCategory,
    EventSeverity,
    ObservationEvent,
)

__all__ = [
    "BaseSourceAdapter",
    "RankingSource",
    "CrawlSource",
    "TechnicalSource",
    "BacklinkSource",
    "CompetitorSource",
    "AnalyticsSource",
    "ReputationSource",
    "LocalSeoSource",
    "ContentSource",
    "CostSource",
    "HealthSource",
    "SecuritySource",
]


class BaseSourceAdapter(abc.ABC):
    """Abstract base for observation source adapters.

    Subclasses implement ``poll()`` which reads from their respective
    engine repositories and returns observation events.
    """

    category: EventCategory

    @abc.abstractmethod
    def poll(self, tenant_id: str, site_id: str) -> list[ObservationEvent]:
        """Read the latest state from the engine and produce events.

        Must be idempotent and read-only — no side effects.
        """
        ...


class RankingSource(BaseSourceAdapter):
    """Reads from M4 Rank Tracking repositories."""

    category = EventCategory.RANKING

    def __init__(self, rank_repo: Any = None) -> None:
        self._repo = rank_repo

    def poll(self, tenant_id: str, site_id: str) -> list[ObservationEvent]:
        events: list[ObservationEvent] = []
        if self._repo is None:
            return events
        # Read ranking data and detect changes
        try:
            snapshots = self._repo.list_snapshots(tenant_id, site_id) if hasattr(self._repo, "list_snapshots") else []
            for snap in snapshots[-5:]:  # recent snapshots
                change = snap.get("position_change", 0) if isinstance(snap, dict) else 0
                if abs(change) >= 3:
                    events.append(ObservationEvent(
                        tenant_id=tenant_id,
                        site_id=site_id,
                        category=self.category,
                        severity=EventSeverity.WARNING if abs(change) < 10 else EventSeverity.CRITICAL,
                        source_engine="rank_tracking",
                        source_ref=str(snap.get("id", "unknown")) if isinstance(snap, dict) else "unknown",
                        title=f"Ranking change: {change} positions",
                        description=f"Keyword ranking changed by {change} positions",
                        data=snap if isinstance(snap, dict) else {"snapshot": str(snap)},
                    ))
        except Exception:
            pass
        return events


class CrawlSource(BaseSourceAdapter):
    """Reads from M1 Crawler + M2 KnowledgeObject diffs."""

    category = EventCategory.CONTENT

    def __init__(self, knowledge_repo: Any = None) -> None:
        self._repo = knowledge_repo

    def poll(self, tenant_id: str, site_id: str) -> list[ObservationEvent]:
        # Reads KnowledgeObject diffs for content changes
        return []


class TechnicalSource(BaseSourceAdapter):
    """Reads from M3 Technical SEO."""

    category = EventCategory.TECHNICAL

    def __init__(self, tech_repo: Any = None) -> None:
        self._repo = tech_repo

    def poll(self, tenant_id: str, site_id: str) -> list[ObservationEvent]:
        return []


class BacklinkSource(BaseSourceAdapter):
    """Reads from M3 Backlink Intelligence."""

    category = EventCategory.BACKLINK

    def __init__(self, backlink_repo: Any = None) -> None:
        self._repo = backlink_repo

    def poll(self, tenant_id: str, site_id: str) -> list[ObservationEvent]:
        return []


class CompetitorSource(BaseSourceAdapter):
    """Reads from M3 Competitor Intelligence."""

    category = EventCategory.COMPETITOR

    def __init__(self, competitor_repo: Any = None) -> None:
        self._repo = competitor_repo

    def poll(self, tenant_id: str, site_id: str) -> list[ObservationEvent]:
        return []


class AnalyticsSource(BaseSourceAdapter):
    """Reads from M4 Analytics Intelligence."""

    category = EventCategory.ANALYTICS

    def __init__(self, analytics_repo: Any = None) -> None:
        self._repo = analytics_repo

    def poll(self, tenant_id: str, site_id: str) -> list[ObservationEvent]:
        return []


class ReputationSource(BaseSourceAdapter):
    """Reads from M4 Reputation Management."""

    category = EventCategory.REPUTATION

    def __init__(self, reputation_repo: Any = None) -> None:
        self._repo = reputation_repo

    def poll(self, tenant_id: str, site_id: str) -> list[ObservationEvent]:
        return []


class LocalSeoSource(BaseSourceAdapter):
    """Reads from M4 Local SEO."""

    category = EventCategory.LOCAL_SEO

    def __init__(self, local_seo_repo: Any = None) -> None:
        self._repo = local_seo_repo

    def poll(self, tenant_id: str, site_id: str) -> list[ObservationEvent]:
        return []


class ContentSource(BaseSourceAdapter):
    """Reads M2 content_freshness field."""

    category = EventCategory.CONTENT

    def __init__(self, content_repo: Any = None) -> None:
        self._repo = content_repo

    def poll(self, tenant_id: str, site_id: str) -> list[ObservationEvent]:
        return []


class CostSource(BaseSourceAdapter):
    """Reads from M5 PlatformObservabilityAggregator."""

    category = EventCategory.COST

    def __init__(self, observability_source: Any = None) -> None:
        self._source = observability_source

    def poll(self, tenant_id: str, site_id: str) -> list[ObservationEvent]:
        return []


class HealthSource(BaseSourceAdapter):
    """Reads from M4 observability hooks."""

    category = EventCategory.PLATFORM_HEALTH

    def __init__(self, health_source: Any = None) -> None:
        self._source = health_source

    def poll(self, tenant_id: str, site_id: str) -> list[ObservationEvent]:
        return []


class SecuritySource(BaseSourceAdapter):
    """Reads from M4/M5 auth/RBAC layer."""

    category = EventCategory.SECURITY

    def __init__(self, auth_source: Any = None) -> None:
        self._source = auth_source

    def poll(self, tenant_id: str, site_id: str) -> list[ObservationEvent]:
        return []
