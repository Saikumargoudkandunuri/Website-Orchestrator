"""Milestone 5 — Campaign Planner Agent wiring: Executive Brain -> Department
-> Specialist -> Tool chain (analysis/planning stage; no live write of its own,
so it never bypasses Governance — it only sequences work other governed
engines already produce).
"""
from __future__ import annotations

from api.agent_specialists import CampaignPlannerAgent, DEFAULT_ROSTER
from api.agent_tools import AgentContext, build_default_tool_registry
from api import agent_departments as departments


def test_campaign_planner_agent_is_in_default_roster() -> None:
    names = {s.name for s in DEFAULT_ROSTER}
    assert "campaign_planner" in names


def test_campaign_planner_tool_is_registered() -> None:
    registry = build_default_tool_registry()
    assert registry.get("campaign_planner") is not None


def test_campaign_planner_capability_is_active_and_owned_by_seo_research() -> None:
    caps = {c["key"]: c for c in departments.capability_registry()}
    cap = caps["campaign_planner"]
    assert cap["status"] == "active"
    assert cap["department"] == "seo_research"
    assert cap["executable"] is True


def test_campaign_planner_agent_runs_end_to_end_through_real_tools() -> None:
    """No subsystems/app -> CMO memory and Digital Twin reads degrade to
    empty, but the underlying Topical Authority / Site Architecture engines
    still run their real (deterministic, seeded) sitewide analysis for any
    domain — consistent with every other specialist in this roster. This
    proves the full Executive Brain -> Department -> Specialist -> Tool chain
    executes without error and returns well-formed, governed proposals.
    """
    agent = CampaignPlannerAgent()
    registry = build_default_tool_registry()
    ctx = AgentContext(domain="no-such-real-site.invalid", tenant="tenant-x", app=None)
    report = agent.analyze(ctx, registry)
    assert report["agent"] == "campaign_planner"
    for action in report["actions"]:
        assert action["source"] == "campaign_planner_agent"
        assert action["requires_approval"] is True
        assert action["status"] == "proposed"
        assert action["campaign"]["campaign_type"]
