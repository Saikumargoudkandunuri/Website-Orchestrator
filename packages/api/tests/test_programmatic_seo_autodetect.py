"""Milestone 5 — Automatic Landing Page Generator auto-detects need from the
account's own onboarding-collected business profile (never fabricated) when
no explicit ``entities`` are supplied.
"""
from __future__ import annotations

from api.agent_tools import _tool_programmatic_seo_plan


class _FakeCtx:
    domain = "example.com"

    def __init__(self, memory: dict) -> None:
        self._memory = memory

    def cmo_memory(self) -> dict:
        return self._memory


def test_auto_detects_services_and_competitors_from_cmo_memory() -> None:
    ctx = _FakeCtx({
        "products_services": ["SEO Audit", "Content Writing"],
        "competitors": ["rival.com"],
        "target_keywords": ["local seo", "technical seo"],
    })
    result = _tool_programmatic_seo_plan(ctx)
    plan_types = {p["page_type"] for p in result["plans_detail"]}
    assert "service" in plan_types
    assert "comparison" in plan_types
    assert "category" in plan_types


def test_explicit_entities_take_precedence_over_cmo_memory() -> None:
    ctx = _FakeCtx({"products_services": ["Ignored Service"]})
    result = _tool_programmatic_seo_plan(ctx, entities={"services": ["Explicit Service"]})
    entities = {p["entity"] for p in result["plans_detail"]}
    assert entities == {"Explicit Service"}


def test_no_memory_and_no_entities_yields_no_plans() -> None:
    ctx = _FakeCtx({})
    result = _tool_programmatic_seo_plan(ctx)
    assert result["plans_detail"] == []
