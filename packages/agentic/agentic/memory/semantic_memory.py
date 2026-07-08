"""Semantic Memory implementation (M6 Build Phase C)."""
from __future__ import annotations

from agentic.memory.models import SemanticFact
from agentic.memory.repositories import SemanticMemoryRepository


class SemanticMemory:
    """Stores and queries SemanticFacts."""
    
    def __init__(self, repository: SemanticMemoryRepository) -> None:
        self._repo = repository
        
    def save_fact(self, fact: SemanticFact) -> None:
        """Store or update a semantic fact."""
        self._repo.save(fact)
        
    def get_fact(self, tenant_id: str, key: str) -> SemanticFact | None:
        """Retrieve a semantic fact by key."""
        return self._repo.get(tenant_id, key)
