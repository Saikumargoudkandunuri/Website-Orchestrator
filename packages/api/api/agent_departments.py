"""Departments — the org layer between the Executive Brain (CMO) and workers.

The steering vision organizes the platform like a marketing org: the CEO sets
business goals, the Executive Brain (CMO) sets priorities, departments own a
capability domain, and specialist workers execute governed missions bound to
real tools.

This module makes that org chart real *and honest*. It groups the existing
specialist workers into departments and enumerates the full Milestone-5
capability surface with a truthful status:

* ``active``   — a real, governed executable tool exists today.
* ``analysis`` — a deterministic engine produces analysis, but there is no live
  write (recommendation only).
* ``planned``  — the capability is gated on an external integration that is not
  connected yet (GBP, social, ads, CRM, email, heatmaps, third-party crawlers).
  It is a tracked backlog item, never presented as functional.

Nothing here fabricates a capability. A ``planned`` entry names the integration
it needs so the Executive Brain can reason about coverage without pretending the
department can act. This keeps the org chart aligned with the anti-patterns in
the steering doc: no disconnected gadgets, no simulated capability shown as real.
"""
from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    "Capability",
    "Department",
    "DEPARTMENTS",
    "STATUS_ACTIVE",
    "STATUS_ANALYSIS",
    "STATUS_PLANNED",
    "capability_registry",
    "department_view",
    "department_for_category",
    "roster_departments",
]

STATUS_ACTIVE = "active"
STATUS_ANALYSIS = "analysis"
STATUS_PLANNED = "planned"
_STATUS_RANK = {STATUS_ACTIVE: 3, STATUS_ANALYSIS: 2, STATUS_PLANNED: 1}


@dataclass(frozen=True)
class Capability:
    """One marketing capability the CMO can reason about.

    ``status`` is the single source of truth for what the platform can honestly
    do today. ``requires_integration`` names the external dependency a planned
    capability is blocked on, so coverage gaps are explicit, not hidden.
    """

    key: str
    name: str
    department: str
    status: str
    loop_role: str
    requires_integration: str | None = None
    tools: tuple[str, ...] = ()
    mission_categories: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "name": self.name,
            "department": self.department,
            "status": self.status,
            "loop_role": self.loop_role,
            "requires_integration": self.requires_integration,
            "tools": list(self.tools),
            "mission_categories": list(self.mission_categories),
            "executable": self.status == STATUS_ACTIVE,
        }


@dataclass(frozen=True)
class Department:
    """A capability domain owning a set of specialist workers."""

    key: str
    name: str
    mandate: str
    worker_agents: tuple[str, ...] = field(default_factory=tuple)
    mission_categories: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "name": self.name,
            "mandate": self.mandate,
            "worker_agents": list(self.worker_agents),
            "mission_categories": list(self.mission_categories),
        }


# --------------------------------------------------------------------------- #
# The department org chart. Worker agents reference existing specialist names in
# api.agent_specialists; a department with no workers yet is a planned team.
# --------------------------------------------------------------------------- #
DEPARTMENTS: tuple[Department, ...] = (
    Department(
        key="technical",
        name="Technical Department",
        mandate="Crawl health, indexing, structured data, Core Web Vitals, technical fixes.",
        worker_agents=("technical_seo", "website_health", "image_seo"),
        mission_categories=("technical_seo", "crawl", "health"),
    ),
    Department(
        key="content",
        name="Content Department",
        mandate="Content quality, refreshes, topical depth, EEAT, editorial calendar.",
        worker_agents=("content_strategy", "content_refresh", "ai_writer"),
        mission_categories=("content",),
    ),
    Department(
        key="seo_research",
        name="SEO & Research Department",
        mandate="Keyword and topic strategy, topical authority, programmatic opportunities.",
        worker_agents=("keyword_strategy", "topical_authority", "site_architecture", "programmatic_seo",
                       "page_lifecycle", "campaign_planner"),
        mission_categories=("strategy",),
    ),
    Department(
        key="offpage",
        name="Off-Page & Authority Department",
        mandate="Internal linking, backlinks, digital PR, outreach, citations, link-worthy assets.",
        worker_agents=("internal_link", "backlink"),
        mission_categories=("internal_links", "backlinks"),
    ),
    Department(
        key="competitor",
        name="Competitor Intelligence Department",
        mandate="Competitor tracking, share-of-voice, keyword/content gap capture.",
        worker_agents=("competitor_intelligence",),
        mission_categories=("competitor",),
    ),
    Department(
        key="ai_visibility",
        name="AI Visibility / GEO Department",
        mandate="Generative Engine Optimization, entity/knowledge-graph signals, AI citations.",
        worker_agents=("brand_visibility",),
        mission_categories=("geo",),
    ),
    Department(
        key="local",
        name="Local SEO Department",
        mandate="Google Business Profile, citations, local rankings, reviews.",
        worker_agents=(),
        mission_categories=("local",),
    ),
    Department(
        key="conversion",
        name="Conversion & UX Department",
        mandate="CRO, UX, funnel analytics, heatmaps, landing pages.",
        worker_agents=(),
        mission_categories=("cro",),
    ),
    Department(
        key="marketing_ops",
        name="Marketing Automation Department",
        mandate="Social, email, campaigns, ads, press releases.",
        worker_agents=(),
        mission_categories=(),
    ),
    Department(
        key="analytics",
        name="Analytics & Attribution Department",
        mandate="Lead tracking, revenue attribution, reporting, brand monitoring.",
        worker_agents=(),
        mission_categories=(),
    ),
)

_DEPARTMENT_BY_KEY = {d.key: d for d in DEPARTMENTS}
_DEPARTMENT_BY_CATEGORY: dict[str, str] = {}
for _dept in DEPARTMENTS:
    for _cat in _dept.mission_categories:
        _DEPARTMENT_BY_CATEGORY[_cat] = _dept.key


# --------------------------------------------------------------------------- #
# Capability registry — the full Milestone-5 surface, honestly statused.
# --------------------------------------------------------------------------- #
def _cap(key, name, dept, status, loop_role, *, integration=None, tools=(), cats=()):
    return Capability(
        key=key, name=name, department=dept, status=status, loop_role=loop_role,
        requires_integration=integration, tools=tuple(tools), mission_categories=tuple(cats),
    )


_CAPABILITIES: tuple[Capability, ...] = (
    # --- Technical (real) ---
    _cap("technical_seo", "Technical SEO Audit", "technical", STATUS_ACTIVE,
         "sense+analyze+execute", tools=("technical_seo_audit", "crawl_site", "apply_fix"),
         cats=("technical_seo", "crawl", "health")),
    _cap("core_web_vitals", "Core Web Vitals", "technical", STATUS_ANALYSIS,
         "sense+analyze", cats=("technical_seo",)),
    _cap("structured_data", "Structured Data / Schema", "technical", STATUS_ACTIVE,
         "sense+analyze+execute", tools=("schema_audit", "schema_execute"), cats=("technical_seo",)),
    _cap("image_seo", "Image SEO Engine", "technical", STATUS_ACTIVE,
         "sense+analyze+execute", tools=("image_seo_audit", "image_seo_execute"), cats=("technical_seo",)),
    # --- Content ---
    _cap("content_quality", "Content Quality & Refresh", "content", STATUS_ACTIVE,
         "sense+analyze+execute", tools=("content_analysis", "content_refresh_audit", "content_refresh_execute"),
         cats=("content",)),
    _cap("ai_writer_v2", "AI Writer V2 (governed publish)", "content", STATUS_ACTIVE,
         "execute", tools=("ai_writer_generate", "ai_writer_publish", "ai_writer_publish_seo_meta")),
    _cap("editorial_calendar", "Editorial Calendar (daily/weekly/monthly/quarterly/annual autofill)",
         "content", STATUS_ACTIVE, "plan", tools=(), cats=("content", "strategy")),
    _cap("image_generation", "Image Generation", "content", STATUS_PLANNED,
         "execute", integration="image_generation_provider"),
    _cap("video_generation", "Video Generation", "content", STATUS_PLANNED,
         "execute", integration="video_generation_provider"),
    # --- SEO & Research ---
    _cap("keyword_strategy", "Keyword & Topic Strategy", "seo_research", STATUS_ANALYSIS,
         "analyze", tools=("keyword_strategy",), cats=("strategy",)),
    _cap("semantic_seo", "Semantic SEO", "seo_research", STATUS_ACTIVE,
         "sense+analyze", tools=("site_architecture",), cats=("strategy",)),
    _cap("entity_engine", "Entity Engine", "seo_research", STATUS_ACTIVE,
         "sense+analyze", tools=("topical_authority",)),
    _cap("knowledge_graph", "Knowledge Graph", "seo_research", STATUS_ACTIVE,
         "sense+analyze", tools=("topical_authority",)),
    _cap("programmatic_seo", "Programmatic SEO", "seo_research", STATUS_ACTIVE,
         "plan+execute", tools=("programmatic_seo_generate", "programmatic_seo_publish")),
    _cap("ai_search_optimization", "AI Search Optimization", "seo_research", STATUS_ANALYSIS,
         "analyze", cats=("geo", "strategy")),
    _cap("page_lifecycle", "Page Lifecycle Engine (create/edit/delete/merge/pillar)", "seo_research", STATUS_ACTIVE,
         "sense+analyze+plan+execute", tools=("page_lifecycle_audit", "page_lifecycle_execute")),
    _cap("campaign_planner", "Campaign Planner (blog/topic clusters, internal linking, authority, GEO, launches, seasonal)",
         "seo_research", STATUS_ACTIVE, "sense+analyze+plan", tools=("campaign_planner",)),
    # --- Off-page & authority ---
    _cap("backlink_audit", "Backlink Audit", "offpage", STATUS_ANALYSIS,
         "analyze", tools=("backlink_audit",), cats=("backlinks",)),
    _cap("digital_pr", "Digital PR", "offpage", STATUS_PLANNED,
         "execute", integration="outreach_email+media_database"),
    _cap("outreach_engine", "Outreach Engine", "offpage", STATUS_PLANNED,
         "execute", integration="outreach_email"),
    _cap("citation_management", "Citation Management", "offpage", STATUS_PLANNED,
         "execute", integration="citation_directories_api"),
    _cap("press_release", "Press Release Engine", "offpage", STATUS_PLANNED,
         "execute", integration="pr_distribution_api"),
    _cap("guest_post_marketplace", "Guest Post Marketplace", "offpage", STATUS_PLANNED,
         "execute", integration="marketplace_backend"),
    # Real analysis on real crawl data with governed structural execution: the
    # crawler now captures anchor text and the Digital Twin resolves
    # url->wp_page_id, so insertions publish through Governance + rollback.
    _cap("internal_link_engine", "Internal Link Engine", "offpage", STATUS_ACTIVE,
         "sense+analyze+execute", tools=("internal_link_audit", "internal_link_execute"),
         cats=("internal_links",)),
    # --- Competitor ---
    _cap("competitor_intel", "Competitor Intelligence", "competitor", STATUS_ANALYSIS,
         "analyze", tools=("competitor_gap",), cats=("competitor",)),
    _cap("brand_monitoring", "Brand Monitoring", "competitor", STATUS_PLANNED,
         "sense", integration="brand_monitoring_api"),
    # --- AI visibility / GEO ---
    _cap("ai_visibility", "AI Visibility / GEO", "ai_visibility", STATUS_ANALYSIS,
         "analyze", tools=("brand_visibility",), cats=("geo",)),
    # --- Local ---
    _cap("local_seo", "Local SEO", "local", STATUS_PLANNED,
         "sense+execute", integration="google_business_profile_api", cats=("local",)),
    _cap("gbp", "Google Business Profile", "local", STATUS_PLANNED,
         "sense+execute", integration="google_business_profile_api"),
    _cap("reputation", "Reputation Management", "local", STATUS_PLANNED,
         "sense+execute", integration="reviews_api"),
    # --- Conversion & UX ---
    _cap("cro_engine", "CRO Engine", "conversion", STATUS_PLANNED,
         "analyze+execute", integration="analytics_events+wordpress_publish", cats=("cro",)),
    _cap("ux_engine", "UX Engine", "conversion", STATUS_PLANNED,
         "analyze", integration="analytics_events"),
    _cap("heatmaps", "Heatmaps", "conversion", STATUS_PLANNED,
         "sense", integration="heatmap_capture_script"),
    _cap("funnel_analytics", "Funnel Analytics", "conversion", STATUS_PLANNED,
         "sense+analyze", integration="analytics_events"),
    # --- Marketing automation ---
    _cap("social_automation", "Social Media Automation", "marketing_ops", STATUS_PLANNED,
         "execute", integration="social_platform_apis"),
    _cap("email_marketing", "Email Marketing", "marketing_ops", STATUS_PLANNED,
         "execute", integration="email_provider_api"),
    _cap("campaign_manager", "Campaign Manager", "marketing_ops", STATUS_PLANNED,
         "plan+execute", integration="channel_integrations"),
    _cap("ads_manager", "Ads Manager", "marketing_ops", STATUS_PLANNED,
         "execute", integration="ads_platform_apis"),
    # --- Analytics & attribution ---
    _cap("lead_tracking", "Lead Tracking", "analytics", STATUS_PLANNED,
         "sense", integration="crm_or_forms_api"),
    _cap("revenue_attribution", "Revenue Attribution", "analytics", STATUS_PLANNED,
         "analyze", integration="analytics_events+crm"),
    # --- Portfolio / agency surfaces ---
    _cap("multi_site_portfolio", "Multi-site Portfolio", "analytics", STATUS_ACTIVE,
         "plan", tools=()),
    _cap("agency_dashboard", "Agency Dashboard", "analytics", STATUS_PLANNED,
         "report", integration="multi_tenant_ui"),
    _cap("white_label", "White Label", "analytics", STATUS_PLANNED,
         "report", integration="branding_config"),
    _cap("client_portal", "Client Portal", "analytics", STATUS_PLANNED,
         "report", integration="client_auth"),
    _cap("team_collaboration", "Team Collaboration", "analytics", STATUS_PLANNED,
         "report", integration="rbac_and_workflow"),
    _cap("autonomous_growth", "Autonomous Business Growth Engine", "analytics", STATUS_ACTIVE,
         "learn", tools=()),
)


def capability_registry() -> list[dict]:
    """Return the full Milestone-5 capability surface with honest statuses."""
    return [c.to_dict() for c in _CAPABILITIES]


def department_for_category(category: str) -> str:
    """Map a mission category to its owning department key."""
    return _DEPARTMENT_BY_CATEGORY.get((category or "").lower(), "technical")


def roster_departments(roster_info: list[dict]) -> list[dict]:
    """Attach live worker roster entries to each department."""
    by_agent = {r["agent"]: r for r in roster_info}
    out: list[dict] = []
    for dept in DEPARTMENTS:
        workers = [by_agent[a] for a in dept.worker_agents if a in by_agent]
        entry = dept.to_dict()
        entry["workers"] = workers
        entry["staffed"] = bool(workers)
        out.append(entry)
    return out


def department_view(missions: list[dict] | None = None) -> dict:
    """Roll missions up to departments and summarize honest capability coverage.

    ``missions`` are compact mission dicts (each with a ``category``). The view
    reports, per department, how many missions the CMO currently assigns to it
    and which of its capabilities are active/analysis/planned.
    """
    missions = missions or []
    caps_by_dept: dict[str, list[dict]] = {}
    for cap in _CAPABILITIES:
        caps_by_dept.setdefault(cap.department, []).append(cap.to_dict())

    mission_counts: dict[str, int] = {}
    for mission in missions:
        dept = department_for_category(str(mission.get("category", "")))
        mission_counts[dept] = mission_counts.get(dept, 0) + 1

    departments: list[dict] = []
    for dept in DEPARTMENTS:
        caps = caps_by_dept.get(dept.key, [])
        status_counts = {STATUS_ACTIVE: 0, STATUS_ANALYSIS: 0, STATUS_PLANNED: 0}
        for cap in caps:
            status_counts[cap["status"]] = status_counts.get(cap["status"], 0) + 1
        best = max((c["status"] for c in caps), key=lambda s: _STATUS_RANK.get(s, 0), default=STATUS_PLANNED)
        departments.append({
            **dept.to_dict(),
            "assigned_missions": mission_counts.get(dept.key, 0),
            "capabilities": caps,
            "capability_status_counts": status_counts,
            "operational_status": best,
        })

    all_caps = capability_registry()
    coverage = {
        "total": len(all_caps),
        STATUS_ACTIVE: sum(1 for c in all_caps if c["status"] == STATUS_ACTIVE),
        STATUS_ANALYSIS: sum(1 for c in all_caps if c["status"] == STATUS_ANALYSIS),
        STATUS_PLANNED: sum(1 for c in all_caps if c["status"] == STATUS_PLANNED),
    }
    return {
        "departments": departments,
        "coverage": coverage,
        "required_integrations": sorted({
            c["requires_integration"] for c in all_caps if c["requires_integration"]
        }),
    }
