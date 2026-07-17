"""The Executive Brain — autonomous Chief Marketing Officer reasoning core.

Specialists are workers: they sense conditions, propose candidate actions, and
execute assigned work. This module alone decides business priority. It combines
business goals, current specialist evidence, site-condition changes, and
verified strategy history into stable, explainable Missions and an adaptive
capacity-aware daily/weekly/monthly/quarterly roadmap.

The core remains deterministic and auditable. A configured provider-neutral
Intelligence gateway may augment future strategic analysis, but provider access
is never hard-coded here and live execution always remains behind governance.
"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from api import agent_departments as departments
from api.cmo_memory import strategy_adjustment

__all__ = [
    "BusinessGoals",
    "Mission",
    "PRIMARY_GOALS",
    "assess",
    "find_mission",
    "get_assessment",
    "get_goals",
    "plan_roadmap",
    "score_mission",
    "set_goals",
]

PRIMARY_GOALS = ("traffic", "leads", "sales", "local", "ecommerce", "branding")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _key(tenant: str, site: str) -> str:
    return f"{tenant}::{site}".lower()


@dataclass
class BusinessGoals:
    primary: str = "traffic"
    description: str = ""

    @staticmethod
    def normalize(primary: str | None) -> str:
        value = (primary or "").strip().lower()
        return value if value in PRIMARY_GOALS else "traffic"

    def to_dict(self) -> dict:
        return {
            "primary": self.primary,
            "description": self.description,
            "options": list(PRIMARY_GOALS),
        }


_GOALS: dict[str, BusinessGoals] = {}
_ASSESSMENTS: dict[str, dict] = {}


def get_goals(tenant: str, site: str) -> BusinessGoals:
    return _GOALS.get(_key(tenant, site), BusinessGoals())


def set_goals(tenant: str, site: str, primary: str, description: str = "") -> BusinessGoals:
    goals = BusinessGoals(
        primary=BusinessGoals.normalize(primary),
        description=description or "",
    )
    _GOALS[_key(tenant, site)] = goals
    return goals


_SEVERITY_BASE = {"critical": 92, "high": 78, "medium": 58, "low": 38, "info": 25}
_CATEGORY_MOD = {
    "technical_seo": 1.0,
    "crawl": 1.0,
    "health": 0.9,
    "content": 0.95,
    "strategy": 0.9,
    "internal_links": 0.95,
    "backlinks": 0.95,
    "competitor": 0.9,
    "geo": 0.85,
    "local": 0.9,
    "cro": 0.9,
}
_GOAL_FIT = {
    "traffic": {"technical_seo": .9, "crawl": .9, "content": 1., "strategy": .9, "internal_links": .85, "backlinks": .8, "geo": .6, "competitor": .8, "health": .7, "local": .5, "cro": .3},
    "leads": {"content": .9, "cro": 1., "technical_seo": .6, "crawl": .6, "strategy": .7, "internal_links": .6, "local": .7, "geo": .5, "backlinks": .5, "competitor": .6, "health": .6},
    "sales": {"cro": 1., "content": .8, "strategy": .9, "technical_seo": .6, "crawl": .6, "internal_links": .6, "competitor": .8, "backlinks": .5, "geo": .5, "local": .6, "health": .6},
    "local": {"local": 1., "content": .7, "technical_seo": .7, "crawl": .7, "internal_links": .6, "geo": .6, "backlinks": .6, "strategy": .6, "competitor": .5, "cro": .6, "health": .7},
    "ecommerce": {"cro": 1., "content": .8, "technical_seo": .8, "crawl": .8, "strategy": .9, "internal_links": .7, "competitor": .8, "backlinks": .6, "geo": .5, "local": .5, "health": .7},
    "branding": {"geo": 1., "content": .9, "backlinks": .8, "internal_links": .6, "competitor": .7, "technical_seo": .5, "crawl": .5, "strategy": .6, "local": .5, "cro": .4, "health": .6},
}
_EFFORT_HOURS = {"low": 1.5, "medium": 6.0, "high": 24.0}
_EFFORT_FACTOR = {"low": 1.0, "medium": 2.4, "high": 5.0}
_SOURCE_CONFIDENCE = {
    "technical_seo_agent": .88,
    "crawl_fix_generator": .90,
    "content_strategy_agent": .72,
    "keyword_strategy_agent": .68,
    "internal_link_agent": .84,
    "backlink_agent": .82,
    "competitor_intelligence_agent": .75,
    "brand_visibility_agent": .78,
}
_CATEGORY_AGENT = {
    "technical_seo": "Technical SEO Agent",
    "crawl": "Technical SEO Agent",
    "health": "Website Health Agent",
    "content": "Content Strategy Agent",
    "strategy": "Keyword & Content Strategy Agent",
    "internal_links": "Internal Link Architect",
    "backlinks": "Backlink & Link-Building Agent",
    "competitor": "Competitor Intelligence Agent",
    "geo": "Brand Visibility / GEO Agent",
    "local": "Local SEO Agent",
    "cro": "CRO Agent",
}
_CATEGORY_TOOLS = {
    "technical_seo": ["technical_seo_audit", "crawl_site", "apply_fix"],
    "crawl": ["crawl_site", "technical_seo_audit", "apply_fix"],
    "health": ["technical_seo_audit", "crawl_site"],
    "content": ["content_analysis", "keyword_strategy"],
    "strategy": ["keyword_strategy", "content_analysis"],
    "internal_links": ["internal_link_audit"],
    "backlinks": ["backlink_audit", "competitor_gap"],
    "competitor": ["competitor_gap", "keyword_strategy"],
    "geo": ["brand_visibility", "content_analysis"],
    "local": ["keyword_strategy", "content_analysis"],
    "cro": ["content_analysis"],
}
_DEPENDENCIES = {
    "content_pillar": ["Publish supporting cluster articles"],
    "link_building_outreach": ["Publish a link-worthy asset first"],
    "content_comparison": ["Complete keyword and competitor research"],
}
_MARKETING_WEIGHTS = {
    "traffic": {"technical_health": .30, "content_quality": .30, "backlink_safety": .20, "ai_visibility": .20},
    "leads": {"technical_health": .25, "content_quality": .35, "backlink_safety": .15, "ai_visibility": .25},
    "sales": {"technical_health": .30, "content_quality": .30, "backlink_safety": .15, "ai_visibility": .25},
    "local": {"technical_health": .35, "content_quality": .30, "backlink_safety": .15, "ai_visibility": .20},
    "ecommerce": {"technical_health": .35, "content_quality": .30, "backlink_safety": .15, "ai_visibility": .20},
    "branding": {"technical_health": .20, "content_quality": .30, "backlink_safety": .20, "ai_visibility": .30},
}
_AI_CATEGORIES = frozenset({"content", "strategy", "competitor", "geo", "local", "cro"})


def _difficulty(action: dict) -> str:
    action_type = (action.get("type") or "").lower()
    category = action.get("category") or ""
    if category in ("technical_seo", "crawl"):
        return "low"
    if "pillar" in action_type or "link_building" in action_type or "outreach" in action_type:
        return "high"
    return "medium"


def _traffic_gain(impact: int) -> str:
    if impact >= 80:
        return "+15–30% directional organic sessions"
    if impact >= 60:
        return "+8–18% directional organic sessions"
    if impact >= 45:
        return "+4–9% directional organic sessions"
    if impact >= 30:
        return "+2–5% directional organic sessions"
    return "+1–3% directional organic sessions"


def _ranking_gain(impact: int) -> str:
    if impact >= 80:
        return "+5–12 positions on affected queries"
    if impact >= 60:
        return "+3–8 positions on affected queries"
    if impact >= 45:
        return "+2–5 positions on affected queries"
    return "+1–3 positions on affected queries"


def _lead_forecast(value: int, goal: str) -> str:
    multiplier = 1.4 if goal in {"leads", "sales", "ecommerce", "local"} else 1.0
    low = max(1, round(value / 25 * multiplier))
    high = max(low + 1, round(value / 10 * multiplier))
    return f"{low}–{high} incremental qualified leads/month (directional)"


def _revenue_forecast(value: int, memory: dict | None) -> str:
    funnels = (memory or {}).get("conversion_funnels", [])
    conversion_value = 0.0
    for funnel in funnels if isinstance(funnels, list) else []:
        if not isinstance(funnel, dict):
            continue
        candidate = funnel.get("revenue_per_conversion") or funnel.get("average_order_value")
        if isinstance(candidate, (int, float)) and candidate > 0:
            conversion_value = float(candidate)
            break
    if not conversion_value:
        band = "high" if value >= 70 else "medium" if value >= 45 else "low"
        return f"{band.capitalize()} potential; configure conversion value for a monetary forecast"
    low_leads = max(1, round(value / 25))
    high_leads = max(low_leads + 1, round(value / 10))
    return f"${low_leads * conversion_value:,.0f}–${high_leads * conversion_value:,.0f}/month (directional)"


def _budget(difficulty: str, category: str) -> str:
    if category == "backlinks":
        return "$500–$2,500 campaign budget"
    return {"low": "$0–$150", "medium": "$150–$750", "high": "$750–$3,000"}[difficulty]


def _completion_time(difficulty: str) -> str:
    return {"low": "same business day", "medium": "2–5 business days", "high": "2–6 weeks"}[difficulty]


def _rollback(category: str, has_fix: bool) -> str:
    if has_fix:
        return "Restore the Digital Twin before-value through the governed rollback action"
    if category in {"content", "strategy", "geo", "local", "cro"}:
        return "Preserve the WordPress revision and restore the prior page/content version"
    if category == "backlinks":
        return "Stop outreach and retract reversible placements; retain the campaign audit"
    return "Cancel the assigned mission before execution; no live-site mutation is permitted without governance"


def _provider_requirement(category: str, provider: dict | None) -> str:
    if category not in _AI_CATEGORIES:
        return "none — deterministic engine"
    provider = provider or {}
    if provider.get("available"):
        return f"{provider.get('selected', 'configured provider')} via provider-agnostic AI gateway"
    return "provider-agnostic AI gateway — connected provider required for generation"


def _change_urgency(memory: dict | None, category: str) -> tuple[float, list[str]]:
    category_metrics = {
        "technical_seo": ("health_score", "seo_score", "component.technical_health"),
        "crawl": ("health_score", "seo_score", "component.technical_health"),
        "health": ("health_score", "component.technical_health"),
        "content": ("component.content_quality", "marketing_score"),
        "strategy": ("marketing_score", "mission_count"),
        "backlinks": ("component.backlink_safety",),
        "competitor": ("competitor_gaps",),
        "geo": ("component.ai_visibility",),
        "local": ("marketing_score",),
        "cro": ("marketing_score",),
    }
    evidence: list[str] = []
    urgent = False
    for change in (memory or {}).get("latest_changes", []):
        metric = change.get("metric")
        delta = float(change.get("delta") or 0)
        decline = delta < 0 or (category == "competitor" and metric == "competitor_gaps" and delta > 0)
        if metric in category_metrics.get(category, ()) and decline:
            urgent = urgent or bool(change.get("material"))
            evidence.append(f"{metric} changed by {delta:+g}")
    return (1.12 if urgent else 1.04 if evidence else 1.0), evidence


def _mission_id(site: str, action: dict) -> str:
    identity = "|".join([
        site.lower(),
        str(action.get("category", "")),
        str(action.get("type", "")),
        str(action.get("title", "Mission")).strip().lower(),
    ])
    return "msn_" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12]


def _business_priority(score: float) -> str:
    if score >= 70:
        return "critical"
    if score >= 45:
        return "high"
    if score >= 25:
        return "medium"
    return "low"


@dataclass
class Mission:
    id: str
    title: str
    description: str
    category: str
    assigned_agent: str
    assigned_department: str
    source_agent: str
    signal_provenance: str
    forecast_basis: str
    seo_impact: int
    expected_ranking_improvement: str
    traffic_gain: str
    expected_traffic_gain: str
    expected_leads: str
    expected_revenue_impact: str
    business_value: int
    business_priority: str
    difficulty: str
    effort_hours: float
    confidence: float
    required_budget: str
    required_ai_provider: str
    required_tools: list[str]
    required_specialist_agents: list[str]
    estimated_completion_time: str
    rollback_strategy: str
    dependencies: list[str]
    priority_score: float
    reasoning: str
    evidence: list[str]
    learning: dict
    horizon: str = "backlog"
    status: str = "backlog"
    action_id: str | None = None
    fix_id: str | None = None
    recommendation: str = ""
    action_type: str = ""
    autofilled: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def score_mission(
    action: dict,
    goals: BusinessGoals,
    *,
    memory: dict | None = None,
    site: str = "",
    provider: dict | None = None,
) -> Mission:
    """Turn a worker's candidate action into a complete CMO Mission."""
    category = action.get("category", "technical_seo")
    severity = (action.get("severity") or "medium").lower()
    base = _SEVERITY_BASE.get(severity, 45)
    seo_impact = int(round(base * _CATEGORY_MOD.get(category, .9)))
    goal_fit = _GOAL_FIT.get(goals.primary, _GOAL_FIT["traffic"]).get(category, .6)
    business_value = int(round(seo_impact * goal_fit))
    difficulty = _difficulty(action)
    effort_hours = _EFFORT_HOURS[difficulty]

    learning = strategy_adjustment(memory, category)
    urgency, change_evidence = _change_urgency(memory, category)
    provenance = str(action.get("provenance") or "unknown")
    confidence = _SOURCE_CONFIDENCE.get(action.get("source", ""), .7)
    confidence += float(learning.get("confidence_delta", 0) or 0)
    if difficulty == "high":
        confidence -= .05
    if provenance != "observed_live_crawl":
        confidence = min(confidence, .35)
    confidence = round(max(.20, min(.97, confidence)), 2)

    raw_priority = (
        seo_impact * .30 + business_value * .45 + confidence * 100 * .15 + goal_fit * 100 * .10
    ) / _EFFORT_FACTOR[difficulty]
    priority_score = round(
        raw_priority * float(learning.get("multiplier", 1) or 1) * urgency,
        1,
    )
    priority = _business_priority(priority_score)
    assigned = _CATEGORY_AGENT.get(category, "Website Health Agent")
    department = departments.department_for_category(category)
    dependencies = list(_DEPENDENCIES.get((action.get("type") or "").lower(), []))
    dependencies.extend(str(item) for item in action.get("dependencies", []) if item)
    evidence = [str(action.get("detail") or action.get("title") or "Specialist signal")]
    evidence.extend(change_evidence)
    reasoning = (
        f"{severity.capitalize()} {category.replace('_', ' ')} signal; {goal_fit:.0%} fit to the "
        f"{goals.primary} goal; {difficulty} delivery effort; confidence {confidence:.0%}. "
        f"Historical strategy multiplier {learning['multiplier']:.3f} from {learning['samples']} verified outcome(s)."
    )
    traffic = _traffic_gain(seo_impact)
    ranking = _ranking_gain(seo_impact)
    leads = _lead_forecast(business_value, goals.primary)
    revenue = _revenue_forecast(business_value, memory)
    forecast_basis = (
        "directional model from observed live-crawl evidence"
        if provenance == "observed_live_crawl"
        else "scenario only — source data is simulated/deterministic and business baselines are not connected"
    )
    if provenance != "observed_live_crawl":
        ranking = f"Unmeasured scenario: {ranking}"
        traffic = f"Unmeasured scenario: {traffic}"
        leads = f"Unmeasured scenario: {leads}"
        revenue = f"Unmeasured scenario: {revenue}"

    return Mission(
        id=_mission_id(site, action),
        title=action.get("title", "Mission"),
        description=action.get("description", ""),
        category=category,
        assigned_agent=assigned,
        assigned_department=department,
        source_agent=action.get("source", "supervisor"),
        signal_provenance=provenance,
        forecast_basis=forecast_basis,
        seo_impact=seo_impact,
        expected_ranking_improvement=ranking,
        traffic_gain=traffic,
        expected_traffic_gain=traffic,
        expected_leads=leads,
        expected_revenue_impact=revenue,
        business_value=business_value,
        business_priority=priority,
        difficulty=difficulty,
        effort_hours=effort_hours,
        confidence=confidence,
        required_budget=_budget(difficulty, category),
        required_ai_provider=_provider_requirement(category, provider),
        required_tools=list(_CATEGORY_TOOLS.get(category, [])),
        required_specialist_agents=[assigned],
        estimated_completion_time=_completion_time(difficulty),
        rollback_strategy=_rollback(category, bool(action.get("fix_id"))),
        dependencies=dependencies,
        priority_score=priority_score,
        reasoning=reasoning,
        evidence=evidence,
        learning=learning,
        action_id=action.get("id"),
        fix_id=action.get("fix_id"),
        recommendation=action.get("after") or action.get("description", ""),
        action_type=str(action.get("type") or ""),
    )


def _compact(mission: Mission) -> dict:
    # Roadmap recommendations retain the full rubric: horizon views must be as
    # explainable and governable as the backlog, not lossy summary objects.
    return mission.to_dict()


#: Ordered horizons, nearest-first. ``next_365_days`` is the annual horizon and
#: also the final overflow bucket: nothing scheduled by the CMO is ever
#: silently dropped, it always lands somewhere on the twelve-month calendar.
_HORIZON_ORDER = ("today", "next_7_days", "next_30_days", "next_90_days", "next_365_days")
_HORIZON_NAME = {
    "today": "daily",
    "next_7_days": "weekly",
    "next_30_days": "monthly",
    "next_90_days": "quarterly",
    "next_365_days": "annual",
}
#: Categories the Editorial Calendar autofill treats as "content must keep
#: flowing" — new/updated pages and blogs, not one-off technical fixes.
_EDITORIAL_CATEGORIES = frozenset({"content", "strategy"})


def _fillable_horizons() -> tuple[str, ...]:
    # The annual bucket is itself the overflow catch-all; it never needs a
    # promotion pulled *into* it from further away.
    return _HORIZON_ORDER[:-1]


def _autofill_editorial_calendar(
    buckets: dict[str, list[Mission]], used: dict[str, float], capacity: dict[str, float],
) -> None:
    """Guarantee every horizon keeps producing content — no human scheduling.

    If a horizon has no content/strategy mission at all (a pure technical-fix
    week, say), promote the highest-priority real content/strategy mission
    already evidenced further out on the calendar into that horizon. This is
    what makes the Editorial Calendar autonomous: idle content capacity is
    never left unfilled while a real content or page-lifecycle "create" gap is
    on record elsewhere in the backlog.
    """
    order = _HORIZON_ORDER
    for index, bucket in enumerate(_fillable_horizons()):
        if any(mission.category in _EDITORIAL_CATEGORIES for mission in buckets[bucket]):
            continue
        candidate = None
        candidate_bucket = None
        for later in order[index + 1:]:
            pool = [m for m in buckets[later] if m.category in _EDITORIAL_CATEGORIES]
            if not pool:
                continue
            pool.sort(key=lambda m: m.priority_score, reverse=True)
            candidate = pool[0]
            candidate_bucket = later
            break
        if candidate is None or candidate_bucket is None:
            continue
        buckets[candidate_bucket].remove(candidate)
        used[candidate_bucket] -= candidate.effort_hours
        buckets[bucket].append(candidate)
        used[bucket] += candidate.effort_hours
        candidate.horizon = _HORIZON_NAME[bucket]
        candidate.autofilled = True
        candidate.reasoning += (
            f" Editorial Calendar autofill: promoted from {_HORIZON_NAME[candidate_bucket]} to keep "
            f"content moving in the {_HORIZON_NAME[bucket]} horizon."
        )


def plan_roadmap(missions: list[Mission]) -> dict:
    """Place missions by priority and delivery capacity, adapting every pass."""
    buckets: dict[str, list[Mission]] = {name: [] for name in _HORIZON_ORDER}
    used = {name: 0.0 for name in buckets}
    capacity = {
        "today": 8.0, "next_7_days": 32.0, "next_30_days": 120.0,
        "next_90_days": 400.0, "next_365_days": 1600.0,
    }

    for mission in missions:
        if mission.business_priority == "critical" and used["today"] + mission.effort_hours <= capacity["today"]:
            bucket = "today"
        elif mission.difficulty == "low" and used["today"] + mission.effort_hours <= capacity["today"]:
            bucket = "today"
        elif mission.difficulty != "high" and used["next_7_days"] + mission.effort_hours <= capacity["next_7_days"]:
            bucket = "next_7_days"
        elif used["next_30_days"] + mission.effort_hours <= capacity["next_30_days"]:
            bucket = "next_30_days"
        elif used["next_90_days"] + mission.effort_hours <= capacity["next_90_days"]:
            bucket = "next_90_days"
        else:
            bucket = "next_365_days"
        mission.horizon = _HORIZON_NAME[bucket]
        buckets[bucket].append(mission)
        used[bucket] += mission.effort_hours

    _autofill_editorial_calendar(buckets, used, capacity)

    result = {name: [_compact(mission) for mission in rows] for name, rows in buckets.items()}
    # Explicit executive vocabulary alongside backward-compatible API keys.
    result.update({
        "daily": result["today"],
        "weekly": result["next_7_days"],
        "monthly": result["next_30_days"],
        "quarterly": result["next_90_days"],
        "annual": result["next_365_days"],
        "capacity": {
            "daily_hours": capacity["today"],
            "weekly_hours": capacity["next_7_days"],
            "monthly_hours": capacity["next_30_days"],
            "quarterly_hours": capacity["next_90_days"],
            "annual_hours": capacity["next_365_days"],
            "scheduled_hours": {name: round(value, 1) for name, value in used.items()},
        },
    })
    return result


def _compute_scores(analysis: dict, goals: BusinessGoals) -> dict:
    metas = {agent["agent"]: agent.get("meta", {}) for agent in analysis.get("agents", [])}
    health = float(analysis.get("health", 0) or 0)
    content = metas.get("content_strategy", {}).get("content_score")
    geo = metas.get("brand_visibility", {}).get("ai_visibility_score", 0) or 0
    backlinks = metas.get("backlink", {})
    toxic = backlinks.get("toxic", 0) or 0
    total = backlinks.get("total", 0) or 0
    backlink_safety = round(100 * (1 - toxic / total)) if total else 90
    components = {
        "technical_health": round(health),
        "content_quality": round(content) if content else round(health),
        "backlink_safety": backlink_safety,
        "ai_visibility": round(geo),
    }
    weights = _MARKETING_WEIGHTS.get(goals.primary, _MARKETING_WEIGHTS["traffic"])
    marketing = round(sum(components[name] * weights.get(name, 0) for name in components) / (sum(weights.values()) or 1))
    return {
        "health_score": round(health),
        "seo_score": round(health),
        "marketing_score": marketing,
        "components": components,
        "competitor_gaps": metas.get("competitor_intelligence", {}).get("gap_count", 0),
    }


def _top_for(categories: tuple[str, ...], missions: list[Mission], none_message: str) -> str:
    rows = [mission for mission in missions if mission.category in categories]
    return f"{rows[0].title} — {rows[0].business_priority} priority" if rows else none_message


def _executive_questions(missions: list[Mission], scores: dict, memory: dict | None) -> list[dict]:
    top = missions[0] if missions else None
    declines = [change for change in (memory or {}).get("latest_changes", []) if float(change.get("delta") or 0) < 0]
    decline_answer = ", ".join(change.get("metric", "metric") for change in declines[:3]) or "No material traffic proxy declined since the prior observation."
    competitor_change = next((c for c in (memory or {}).get("latest_changes", []) if c.get("metric") == "competitor_gaps" and float(c.get("delta") or 0) > 0), None)
    return [
        {"q": "What should I publish today?", "a": _top_for(("content", "strategy"), missions, "No publication is justified by current evidence today.")},
        {"q": "What should I improve today?", "a": top.title if top else "No blocking issue is currently evidenced."},
        {"q": "What pages should exist but don't?", "a": _top_for(("competitor", "strategy", "content"), missions, "No evidence-backed page gap has been identified.")},
        {"q": "Which keywords are easiest to win?", "a": _top_for(("strategy", "competitor"), missions, "Keyword opportunity data is not yet connected.")},
        {"q": "Which competitors became stronger?", "a": f"Competitor gaps increased by {competitor_change['delta']}." if competitor_change else "No competitor-strength increase is evidenced in the latest comparison."},
        {"q": "Which backlinks should I earn?", "a": _top_for(("backlinks",), missions, "No backlink campaign is currently prioritized.")},
        {"q": "Which pages lost traffic?", "a": decline_answer},
        {"q": "Which pages need rewriting?", "a": _top_for(("content",), missions, "No rewrite is supported by current content signals.")},
        {"q": "Which pages need schema improvements?", "a": _top_for(("technical_seo", "crawl"), missions, "No schema-related technical mission is currently open.")},
        {"q": "Which AI/GEO optimizations should be implemented?", "a": f"AI visibility is {scores['components']['ai_visibility']}/100. " + _top_for(("geo",), missions, "No GEO action is currently evidenced.")},
        {"q": "Which landing pages should be created?", "a": _top_for(("cro", "content", "strategy"), missions, "No landing-page gap is currently evidenced.")},
        {"q": "Which local SEO opportunities exist?", "a": _top_for(("local",), missions, "No local opportunity is currently evidenced.")},
        {"q": "Which conversion bottlenecks exist?", "a": _top_for(("cro",), missions, "Conversion telemetry is not yet producing a bottleneck mission.")},
        {"q": "Which campaigns should begin this week?", "a": _top_for(("backlinks", "content", "strategy", "competitor"), missions, "No new campaign passes the current business-impact threshold.")},
        {"q": "What should be done first for maximum business impact?", "a": f"{top.title} — priority {top.priority_score}, assigned to {top.assigned_agent}." if top else "Backlog is clear."},
    ]


def assess(
    *,
    site: str,
    tenant: str,
    analysis: dict,
    goals: BusinessGoals,
    memory: dict | None = None,
    provider: dict | None = None,
    website_id: str | None = None,
) -> dict:
    """Run one change- and learning-aware CMO assessment for a website."""
    missions = [
        score_mission(action, goals, memory=memory, site=site, provider=provider)
        for action in analysis.get("actions", [])
    ]
    missions.sort(key=lambda mission: mission.priority_score, reverse=True)
    roadmap = plan_roadmap(missions)
    scores = _compute_scores(analysis, goals)
    compact_missions = [
        {"category": mission.category, "priority_score": mission.priority_score}
        for mission in missions
    ]
    org = departments.department_view(compact_missions)
    assessment = {
        "site": site,
        "website_id": website_id,
        "tenant": tenant,
        "generated_at": _now(),
        "goals": goals.to_dict(),
        "scores": scores,
        "mission_count": len(missions),
        "backlog": [mission.to_dict() for mission in missions],
        "roadmap": roadmap,
        "agents": [
            {"agent": agent["agent"], "role": agent.get("role", agent["agent"]), "summary": agent.get("summary", "")}
            for agent in analysis.get("agents", [])
        ],
        "questions": _executive_questions(missions, scores, memory),
        "departments": org["departments"],
        "capability_coverage": org["coverage"],
        "required_integrations": org["required_integrations"],
        "changes": list((memory or {}).get("latest_changes", [])),
        "provider": provider or {
            "route": "provider-agnostic-intelligence-gateway",
            "selected": "deterministic",
            "available": False,
        },
        "reasoning_mode": "deterministic-explainable-with-learned-outcome-calibration",
    }
    _ASSESSMENTS[_key(tenant, site)] = assessment
    return assessment


def get_assessment(tenant: str, site: str) -> dict | None:
    return _ASSESSMENTS.get(_key(tenant, site))


def find_mission(
    mission_id: str,
    *,
    tenant: str | None = None,
    site: str | None = None,
) -> tuple[dict | None, dict | None]:
    """Locate a mission, optionally enforcing tenant and site ownership."""
    for assessment in _ASSESSMENTS.values():
        if tenant is not None and assessment.get("tenant") != tenant:
            continue
        if site is not None and assessment.get("site") != site:
            continue
        for mission in assessment.get("backlog", []):
            if mission.get("id") == mission_id:
                return assessment, mission
    return None, None
