"""Procedural Memory implementation (M6 Build Phase C)."""
from __future__ import annotations

from agentic.memory.models import WorkflowTemplate
from agentic.memory.repositories import ProceduralMemoryRepository


class ProceduralMemory:
    """Stores and queries procedural WorkflowTemplates."""
    
    def __init__(self, repository: ProceduralMemoryRepository) -> None:
        self._repo = repository
        
    def save_template(self, template: WorkflowTemplate) -> None:
        """Save a WorkflowTemplate."""
        self._repo.save(template)
        
    def get_template(self, tenant_id: str, name: str) -> WorkflowTemplate | None:
        """Fetch a template by its workflow name."""
        return self._repo.get_by_name(tenant_id, name)
