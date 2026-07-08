"""Shared Blackboard for multi-agent coordination (M6 Build Phase F)."""
from __future__ import annotations

import uuid

from agentic.agents.repositories import BlackboardRepository
from agentic.agents.types import JsonValue, JsonObject


class Blackboard:
    """Versioned, append-only shared mission workspace."""

    def __init__(self, repository: BlackboardRepository) -> None:
        self._repo = repository

    def publish_fact(self, tenant_id: str, mission_id: str, key: str, value: JsonValue, publisher: str) -> JsonObject:
        entry_id = f"bb_{uuid.uuid4().hex}"
        version = len(self.get_history(tenant_id, mission_id, key)) + 1
        entry: JsonObject = {
            "id": entry_id,
            "mission_id": mission_id,
            "tenant_id": tenant_id,
            "key": key,
            "value": value,
            "publisher": publisher,
            "version": version,
        }
        self._repo.post_fact(tenant_id, mission_id, entry_id, key, version, entry)
        return entry

    def get_latest_fact(self, tenant_id: str, mission_id: str, key: str) -> JsonValue | None:
        history = self.get_history(tenant_id, mission_id, key)
        if not history:
            return None
        return history[-1]["value"]

    def get_history(self, tenant_id: str, mission_id: str, key: str) -> list[JsonObject]:
        all_facts = self._repo.get_facts(tenant_id, mission_id)
        filtered = [fact for fact in all_facts if fact.get("key") == key]
        return sorted(filtered, key=lambda fact: int(fact.get("version", 0) or 0))

    def list_entries(self, tenant_id: str, mission_id: str) -> list[JsonObject]:
        return self._repo.get_facts(tenant_id, mission_id)
