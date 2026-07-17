"""Supervisor — the central orchestration layer for the specialist agents.

Runs the specialist roster over a site, collects each agent's findings and
proposed actions onto a shared blackboard, and returns a single consolidated
analysis for the governed reasoning loop's ANALYZE phase. This is the
"agents collaborate through a central orchestration layer" requirement from the
steering doc (§5), grounded in real tool-bound executors.
"""
from __future__ import annotations

from typing import Any

from api.agent_tools import AgentContext, build_default_tool_registry
from api.agent_specialists import DEFAULT_ROSTER, Specialist
from api import agent_departments as departments

__all__ = ["Supervisor", "default_supervisor"]


class Supervisor:
    def __init__(self, roster: tuple[Specialist, ...] | None = None) -> None:
        self.roster = roster or DEFAULT_ROSTER
        self.registry = build_default_tool_registry()

    def roster_info(self) -> list[dict]:
        return [
            {"agent": s.name, "role": s.role, "tools": list(s.tools)}
            for s in self.roster
        ]

    def departments(self) -> list[dict]:
        """The department org chart with live workers attached to each team."""
        return departments.roster_departments(self.roster_info())

    def analyze(self, domain: str, tenant: str = "demo-tenant", app: Any = None) -> dict:
        """Run every specialist and consolidate their output.

        Returns ``{health, findings, actions, agents, blackboard, tools}``.
        Each specialist is isolated: a failure in one degrades to an empty
        contribution rather than aborting the whole analysis.
        """
        ctx = AgentContext(domain=domain, tenant=tenant, app=app)

        findings: list[dict] = []
        actions: list[dict] = []
        agents: list[dict] = []
        blackboard: dict[str, Any] = {"site": domain, "signals": []}
        health = 0.0

        for specialist in self.roster:
            try:
                report = specialist.analyze(ctx, self.registry)
            except Exception as exc:  # noqa: BLE001 - one agent must not break the mission
                report = {
                    "agent": specialist.name, "role": specialist.role,
                    "tools_used": list(specialist.tools),
                    "summary": f"unavailable ({type(exc).__name__})",
                    "findings": [], "actions": [], "meta": {},
                }
            findings.extend(report.get("findings", []))
            actions.extend(report.get("actions", []))
            agents.append(report)
            blackboard["signals"].append({"agent": report["agent"], "summary": report["summary"]})
            # The health-bearing agents (technical / website-health) set the score.
            h = report.get("meta", {}).get("health_score")
            if h:
                health = max(health, float(h))

        return {
            "health": round(health, 1),
            "findings": findings,
            "actions": actions,
            "agents": agents,
            "blackboard": blackboard,
            "tools": self.registry.describe(),
        }


_SUPERVISOR: Supervisor | None = None


def default_supervisor() -> Supervisor:
    """Return a shared Supervisor instance."""
    global _SUPERVISOR
    if _SUPERVISOR is None:
        _SUPERVISOR = Supervisor()
    return _SUPERVISOR
