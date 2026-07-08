"""Agent Registry for listing specialist agents (M6 Build Phase F)."""
from __future__ import annotations

from pydantic import BaseModel, Field

from agentic.agents.repositories import AgentRepository
from agentic.agents.types import SpecialistAgent


class AgentMetadata(BaseModel):
    """Metadata describing a specialist agent profile."""
    name: str
    capabilities: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    cost: float = 0.0
    latency_ms: int = 0
    risk: str = "low"
    confidence: float = 1.0
    tenant_restrictions: list[str] = Field(default_factory=list)
    approval_requirements: list[str] = Field(default_factory=list)


class AgentRegistry:
    """Tenant-scoped registry holding specialist metadata for planner lookup."""

    def __init__(self, repository: AgentRepository | None = None, tenant_id: str | None = None) -> None:
        self._registry: dict[str, AgentMetadata] = {}
        self._repository = repository
        self._tenant_id = tenant_id

    def register(self, metadata: AgentMetadata) -> None:
        self._registry[metadata.name] = metadata
        if self._repository and self._tenant_id:
            self._repository.save_agent(self._tenant_id, metadata.name, metadata.model_dump(mode="json"))

    def register_specialist(self, specialist: SpecialistAgent) -> None:
        self.register(
            AgentMetadata(
                name=specialist.name,
                capabilities=specialist.capabilities,
                tools=specialist.tools,
                skills=specialist.skills,
                cost=specialist.cost,
                latency_ms=specialist.latency_ms,
                risk=specialist.risk,
                confidence=specialist.confidence,
                tenant_restrictions=specialist.tenant_restrictions,
                approval_requirements=specialist.approval_requirements,
            )
        )

    def get_agent(self, name: str) -> AgentMetadata | None:
        return self._registry.get(name)

    def find_by_capability(self, capability: str) -> list[AgentMetadata]:
        return [meta for meta in self._registry.values() if capability in meta.capabilities]

    def list_agents(self) -> list[AgentMetadata]:
        return list(self._registry.values())
