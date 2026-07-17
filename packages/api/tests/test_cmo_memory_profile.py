"""Milestone 5 — onboarding business-profile fields in CMO memory.

The account-creation wizard collects business context (competitors, target
keywords, business category, country, language, timezone) once. This is
stored in the same durable CMO memory document as the rest of the business
profile — no new persistence layer — and must round-trip through
``update_profile``/``load`` and appear in ``public_view``.
"""
from __future__ import annotations

from api.cmo_memory import CMOMemoryStore


def test_update_profile_persists_new_business_context_fields() -> None:
    store = CMOMemoryStore(repository=None)  # ephemeral fallback, no DB needed
    store.update_profile(
        tenant_id="tenant-a",
        site="example.com",
        profile={
            "competitors": ["rival1.com", "rival2.com"],
            "target_keywords": ["seo audit", "site health"],
            "business_category": "SaaS",
            "country": "US",
            "language": "en",
            "timezone": "America/New_York",
        },
    )
    memory = store.load(tenant_id="tenant-a", site="example.com")
    assert memory["competitors"] == ["rival1.com", "rival2.com"]
    assert memory["target_keywords"] == ["seo audit", "site health"]
    assert memory["business_category"] == "SaaS"
    assert memory["country"] == "US"
    assert memory["timezone"] == "America/New_York"


def test_public_view_surfaces_business_context_fields() -> None:
    store = CMOMemoryStore(repository=None)
    store.update_profile(
        tenant_id="tenant-b",
        site="example.com",
        profile={"business_category": "E-commerce", "country": "DE"},
    )
    memory = store.load(tenant_id="tenant-b", site="example.com")
    view = store.public_view(memory)
    assert view["business_category"] == "E-commerce"
    assert view["country"] == "DE"


def test_default_memory_has_business_context_defaults() -> None:
    from api.cmo_memory import default_memory

    memory = default_memory(tenant_id="t", site="s")
    assert memory["target_keywords"] == []
    assert memory["business_category"] == ""
    assert memory["language"] == "en"
    assert memory["timezone"] == "UTC"
