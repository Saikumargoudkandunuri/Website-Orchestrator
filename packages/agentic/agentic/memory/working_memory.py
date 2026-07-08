"""Working Memory implementation (M6 Build Phase C).

Short-lived, auto-expiring in-memory cache scoped by tenant.
"""
from __future__ import annotations

import time
from typing import Any


class WorkingMemory:
    """Auto-expiring working memory store."""
    
    def __init__(self) -> None:
        # dict: tenant_id -> key -> (value, expiry_timestamp)
        self._store: dict[str, dict[str, tuple[Any, float]]] = {}
        
    def get(self, tenant_id: str, key: str) -> Any | None:
        tenant_store = self._store.get(tenant_id)
        if not tenant_store:
            return None
        item = tenant_store.get(key)
        if not item:
            return None
        value, expiry = item
        if time.time() > expiry:
            # Expired
            tenant_store.pop(key, None)
            return None
        return value
        
    def set(self, tenant_id: str, key: str, value: Any, ttl_seconds: int = 300) -> None:
        if tenant_id not in self._store:
            self._store[tenant_id] = {}
        self._store[tenant_id][key] = (value, time.time() + ttl_seconds)
        
    def delete(self, tenant_id: str, key: str) -> None:
        tenant_store = self._store.get(tenant_id)
        if tenant_store:
            tenant_store.pop(key, None)
            
    def clear_expired(self) -> None:
        now = time.time()
        for tenant_id, tenant_store in list(self._store.items()):
            for key, (val, expiry) in list(tenant_store.items()):
                if now > expiry:
                    tenant_store.pop(key, None)
