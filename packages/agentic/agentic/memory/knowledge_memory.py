"""Knowledge Memory implementation (M6 Build Phase C).

Acts as a read-through index over M1-M5 data repositories.
"""
from __future__ import annotations

from typing import Any

from brain.decision.repositories import DecisionRepository, HistoricalOutcomeRepository
from brain.repositories import KnowledgeGraphRepository, SiteSynthesisRepository
from intelligence.repositories.ai_invocation_repository import AIInvocationRepository
from intelligence.repositories.knowledge_object_repository import KnowledgeObjectRepository


class KnowledgeMemory:
    """Indexes and references upstream intelligence and execution state (M1-M5)."""
    
    def __init__(
        self,
        ko_repo: KnowledgeObjectRepository | None = None,
        kg_repo: KnowledgeGraphRepository | None = None,
        decision_repo: DecisionRepository | None = None,
        synthesis_repo: SiteSynthesisRepository | None = None,
        historical_repo: HistoricalOutcomeRepository | None = None,
        ai_invocation_repo: AIInvocationRepository | None = None,
    ) -> None:
        self._ko_repo = ko_repo
        self._kg_repo = kg_repo
        self._decision_repo = decision_repo
        self._synthesis_repo = synthesis_repo
        self._historical_repo = historical_repo
        self._ai_invocation_repo = ai_invocation_repo
        
    def get_latest_synthesis(self, tenant_id: str, site_id: str) -> Any | None:
        if self._synthesis_repo:
            return self._synthesis_repo.get_latest_synthesis(tenant_id, site_id)
        return None
        
    def get_knowledge_graph(self, tenant_id: str, site_id: str) -> Any | None:
        if self._kg_repo:
            return self._kg_repo.load_graph(tenant_id, site_id)
        return None
        
    def get_latest_page_audit(self, tenant_id: str, page_id: str) -> Any | None:
        if self._ko_repo:
            # Reuses M2 knowledge object
            return self._ko_repo.get_latest(tenant_id, page_id)
        return None

    def list_decisions(self, tenant_id: str, site_id: str) -> list[Any]:
        if self._decision_repo:
            return self._decision_repo.get_all_for_site(tenant_id, site_id)
        return []

    def get_historical_outcome(self, tenant_id: str, decision_id: str) -> Any | None:
        if self._historical_repo:
            return self._historical_repo.get_by_decision(tenant_id, decision_id)
        return None

    def list_ai_invocations(self, tenant_id: str, page_id: str) -> list[Any]:
        if self._ai_invocation_repo:
            return self._ai_invocation_repo.list_for_page(tenant_id, page_id)
        return []
