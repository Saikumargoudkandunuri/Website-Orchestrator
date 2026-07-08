"""Episodic Memory implementation (M6 Build Phase C)."""
from __future__ import annotations

from agentic.memory.models import ExperienceEpisode
from agentic.memory.repositories import EpisodicMemoryRepository


class EpisodicMemory:
    """Stores and queries ExperienceEpisodes."""
    
    def __init__(self, repository: EpisodicMemoryRepository) -> None:
        self._repo = repository
        
    def record_episode(self, episode: ExperienceEpisode) -> None:
        """Record an experience episode."""
        self._repo.save(episode)
        
    def list_episodes(self, tenant_id: str) -> list[ExperienceEpisode]:
        """List all episodes for a tenant."""
        return self._repo.get_all(tenant_id)
