"""Executive reporting for the autonomous CMO.

The report combines the latest CMO assessment with durable per-site memory and
recent governed-loop outcomes. It distinguishes observed changes from forecasts
and never claims that an assigned strategy was completed without a real handler
and verification evidence.
"""
from __future__ import annotations

from datetime import datetime, timezone

from api import agent_loop
from api import executive_brain

__all__ = ["build_report"]

_GOAL_TARGET = 85


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today_prefix() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _goal_trend(memory: dict, outcomes: list[dict]) -> float:
    # Durable marketing-score observations are the preferred trend. Health
    # deltas from the process-local loop remain a fallback for older sites.
    history = memory.get("historical_performance", [])
    if len(history) >= 2:
        return round(
            float(history[-1].get("marketing_score", 0) or 0)
            - float(history[-2].get("marketing_score", 0) or 0),
            2,
        )
    return round(sum(float(row.get("health_delta") or 0) for row in outcomes[:5]), 2)


def _change_rows(memory: dict, direction: str) -> list[dict]:
    rows: list[dict] = []
    for change in memory.get("latest_changes", []):
        if change.get("direction") != direction:
            continue
        rows.append({
            "metric": change.get("metric"),
            "before": change.get("before"),
            "after": change.get("after"),
            "delta": change.get("delta"),
            "material": bool(change.get("material")),
            "when": memory.get("updated_at"),
        })
    return rows


def build_report(*, tenant: str, site: str, assessment: dict | None = None) -> dict:
    """Assemble a business-owner brief from observations, plans, and outcomes."""
    assessment = assessment or executive_brain.get_assessment(tenant, site) or {}
    scores = assessment.get("scores", {})
    goals = assessment.get("goals", {"primary": "traffic"})
    roadmap = assessment.get("roadmap", {})
    memory = assessment.get("memory", {})
    outcomes = agent_loop.list_outcomes(tenant, site)
    today_prefix = _today_prefix()
    todays = [row for row in outcomes if (row.get("recorded_at") or "").startswith(today_prefix)]

    completed_missions = [
        mission for mission in assessment.get("backlog", [])
        if mission.get("status") in {"applied", "completed", "verified"}
    ]
    completed_actions = sum(
        int(row.get("actions_applied", 0) or 0)
        for row in todays
    )
    proposed_today = sum(int(row.get("actions_proposed", 0) or 0) for row in todays)
    improved_changes = _change_rows(memory, "improved")
    declined_changes = _change_rows(memory, "declined")
    failed_strategies = list(memory.get("failed_strategies", []))[-5:]
    successful_strategies = list(memory.get("successful_strategies", []))[-5:]

    next_up = (roadmap.get("today", []) + roadmap.get("next_7_days", []))[:8]
    marketing = float(scores.get("marketing_score", 0) or 0)
    health = float(scores.get("health_score", 0) or 0)
    seo = float(scores.get("seo_score", 0) or 0)
    progress_pct = min(100, round(marketing / _GOAL_TARGET * 100)) if marketing else 0
    trend = _goal_trend(memory, outcomes)
    planned_today = len(roadmap.get("today", []))
    cycles_today = [
        cycle for cycle in memory.get("cycle_history", [])
        if str(cycle.get("recorded_at") or "").startswith(today_prefix)
    ]

    narrative = _narrative(
        site=site,
        goal=str(goals.get("primary", "traffic")),
        marketing=marketing,
        health=health,
        progress=progress_pct,
        planned=planned_today,
        completed=completed_actions + len(completed_missions),
        changes=memory.get("latest_changes", []),
        next_up=next_up,
        storage=str(memory.get("storage", "ephemeral")),
    )

    return {
        "generated_at": _now(),
        "site": site,
        "tenant": tenant,
        "period": "today",
        "goal": goals.get("primary", "traffic"),
        "goal_progress": {
            "percent": progress_pct,
            "standing": marketing,
            "target": _GOAL_TARGET,
            "trend": trend,
            "label": "on track" if progress_pct >= 80 else "improving" if progress_pct >= 55 else "needs work",
        },
        "scores": {
            "website_health": health,
            "seo_score": seo,
            "marketing_score": marketing,
            "components": scores.get("components", {}),
        },
        "today": {
            "planned": planned_today,
            "proposed": proposed_today,
            "completed": completed_actions + len(completed_missions),
            "runs": max(len(todays), len(cycles_today)),
            "changes_detected": len(memory.get("latest_changes", [])),
            "material_changes": sum(1 for row in memory.get("latest_changes", []) if row.get("material")),
        },
        "completed": [
            {
                "site": row["site"],
                "handled": int(row.get("actions_applied", 0) or 0),
                "mode": row.get("mode"),
                "when": row.get("recorded_at"),
            }
            for row in todays
            if int(row.get("actions_applied", 0) or 0) > 0
        ][:5],
        "improved": improved_changes,
        "declined": declined_changes,
        "failed": [
            {
                "site": row.get("site", site),
                "when": row.get("recorded_at"),
                "error": row.get("error"),
            }
            for row in outcomes if row.get("error")
        ][:5],
        "next": next_up,
        "roadmap": {
            "daily": len(roadmap.get("daily", roadmap.get("today", []))),
            "weekly": len(roadmap.get("weekly", roadmap.get("next_7_days", []))),
            "monthly": len(roadmap.get("monthly", roadmap.get("next_30_days", []))),
            "quarterly": len(roadmap.get("quarterly", roadmap.get("next_90_days", []))),
            "annual": len(roadmap.get("annual", roadmap.get("next_365_days", []))),
            "capacity": roadmap.get("capacity", {}),
        },
        "learning": {
            "successful_strategies": successful_strategies,
            "failed_strategies": failed_strategies,
            "strategy_stats": memory.get("strategy_stats", {}),
            "verified_outcomes": sum(
                int(stats.get("successful", 0) or 0) + int(stats.get("failed", 0) or 0)
                for stats in memory.get("strategy_stats", {}).values()
            ),
        },
        "memory": memory,
        "governance": assessment.get("governance", {}),
        "provider": assessment.get("provider", memory.get("provider", {})),
        "narrative": narrative,
    }


def _narrative(
    *,
    site: str,
    goal: str,
    marketing: float,
    health: float,
    progress: int,
    planned: int,
    completed: int,
    changes: list[dict],
    next_up: list[dict],
    storage: str,
) -> str:
    material = [row for row in changes if row.get("material")]
    change_text = (
        f"I detected {len(changes)} condition change(s), including {len(material)} material change(s), and reprioritized the roadmap. "
        if changes
        else "No material condition change was observed; the current priorities remain evidence-aligned. "
    )
    memory_text = (
        "Long-term site memory is durable. "
        if storage == "durable"
        else "Memory is currently ephemeral; enable site memory on a connected website for cross-restart learning. "
    )
    next_text = (
        f"Next: {next_up[0]['title']} ({next_up[0]['business_priority']} priority, assigned to {next_up[0]['assigned_agent']})."
        if next_up
        else "The backlog is clear; monitoring continues."
    )
    return (
        f"CMO brief for {site}: the primary goal is {goal}. Marketing stands at {marketing:g}/100 "
        f"and technical health at {health:g}/100, representing {progress}% of the healthy target. "
        f"Today I scheduled {planned} priority mission(s) and verified {completed} completed action(s). "
        + change_text + memory_text + next_text
    )
