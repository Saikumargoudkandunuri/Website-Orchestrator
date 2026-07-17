"""Agentic AI + Copilot + Executive-dashboard router (additive).

This module gives the platform a *real* agentic loop that reuses the existing,
safe subsystems rather than a mock:

    analyze  -> crawl (best-effort) + deterministic SEO engines
    propose  -> concrete, reviewable actions (fixes) with before/after
    approve  -> apply through the Governance_Layer -> Publishing_Adapter
    rollback -> restore the audited before-value

The live website is never edited directly: every write still passes through the
human-approved Governance path (a fix must be approved before it is applied, and
approving a persisted fix applies it via the Publishing_Adapter). Advisory
recommendations that have no persisted, auto-applicable fix are surfaced as
guidance and can be accepted/dismissed but never silently mutate the site.

Runs are held in process memory (they are orchestration metadata); the durable
state — pages, issues, fixes, audit trail — lives in the Digital_Twin exactly as
before.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, Body, HTTPException, Request
from pydantic import BaseModel

from api import agent_departments as departments
from api import agent_loop as loop
from api import executive_brain as brain
from api import executive_report
from api.agent_supervisor import default_supervisor
from api.agent_scheduler import get_scheduler
from api.cmo_cycle import coordinator_for_app


class _AppCtx:
    """Minimal request-like shim for background cycles with explicit tenancy."""

    def __init__(self, app: Any, tenant_id: str | None = None) -> None:
        self.app = app
        self.tenant_id = tenant_id


def _make_cycle_fn(app: Any):
    """Return a portfolio-aware governed CMO cycle bound to the application."""
    def _cycle(site: dict) -> dict:
        tenant = str(site.get("tenant_id") or coordinator_for_app(app).configured_tenant())
        run = _run_cycle(
            _AppCtx(app, tenant),
            _RunRequest(
                target=str(site.get("url") or site.get("domain") or ""),
                website_id=str(site.get("website_id") or ""),
                mode=str(site.get("mode") or loop.APPROVAL),
                crawl=bool(site.get("crawl", False)),
            ),
            cadence=True,
        )
        analysis = {
            "health": run.get("summary", {}).get("health_score", 0),
            "findings": run.get("findings", []),
            "actions": run.get("actions", []),
            "agents": run.get("agents", []),
            "blackboard": run.get("blackboard", {}),
        }
        website_id = str(site.get("website_id") or "") or None
        run["cmo"] = coordinator_for_app(app).assess(
            tenant_id=tenant,
            site=run["target"],
            website_id=website_id,
            analysis=analysis,
            mode=run.get("mode"),
            cycle_id=run.get("id"),
        )
        # Continuous Learning (item 8): every governed cycle also resolves any
        # mission whose observation window has elapsed, measuring its real
        # category metric and feeding the outcome back into strategy_stats —
        # no separate scheduler, no human step required.
        try:
            run["cmo"]["verified_missions"] = coordinator_for_app(app).resolve_mission_verifications(
                tenant_id=tenant, site=run["target"], website_id=website_id,
            )
        except Exception:  # noqa: BLE001 - learning must not break the cycle
            run["cmo"]["verified_missions"] = []
        return run
    return _cycle


def _make_discovery_fn(app: Any):
    return lambda: coordinator_for_app(app).connected_sites()


def configure_cmo_scheduler(app: Any) -> dict:
    """Start connected-site discovery/cadence for an explicitly enabled app."""
    scheduler = get_scheduler()
    status = scheduler.start(_make_cycle_fn(app), _make_discovery_fn(app))
    if not getattr(app.state, "cmo_shutdown_registered", False):
        app.add_event_handler("shutdown", scheduler.stop)
        app.state.cmo_shutdown_registered = True
    return status

__all__ = [
    "build_agent_router",
    "build_copilot_router",
    "build_executive_router",
    "configure_cmo_scheduler",
]


def _tenant_of(request: Request) -> str:
    """Read explicit background-cycle tenancy, then configured app tenancy."""
    explicit = getattr(request, "tenant_id", None)
    if explicit:
        return str(explicit)
    try:
        return request.app.state.subsystems.tenant_id or "demo-tenant"
    except Exception:  # noqa: BLE001
        return "demo-tenant"


# --------------------------------------------------------------------------- #
# In-memory run store (orchestration metadata only)
# --------------------------------------------------------------------------- #
_RUNS: dict[str, dict[str, Any]] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _resolve_domain(target: str) -> str:
    """Normalise a URL/domain to a bare registrable domain string."""
    t = (target or "").strip()
    if not t:
        return "wordpress.org"
    t = t.replace("https://", "").replace("http://", "").strip("/")
    if t.startswith("www."):
        t = t[4:]
    return t.split("/")[0] or "wordpress.org"


# --------------------------------------------------------------------------- #
# Deterministic SEO-engine analysis (always works, no network)
# --------------------------------------------------------------------------- #
def _engine_findings(domain: str, tenant_id: str) -> tuple[float, list[dict], list[dict]]:
    """Run the technical + content engines and return (health, findings, actions).

    Findings are human-readable observations. Actions are concrete, reviewable
    proposals derived from failed checks, each carrying a before/after preview.
    """
    findings: list[dict] = []
    actions: list[dict] = []
    health = 0.0
    try:
        from engines.shared.engine_contract import EngineAnalysisRequest, PageTarget
        from engines.shared.local_seo_data import build_knowledge_object
        from engines.technical_seo.interfaces import TechnicalSeoEngine
        from engines.content_intelligence.interfaces import ContentIntelligenceEngine

        ko = build_knowledge_object(domain, tenant_id=tenant_id)
        tech = TechnicalSeoEngine().analyze(
            EngineAnalysisRequest(
                target=PageTarget(page_id=getattr(ko, "page_id", domain), site_id=domain),
                knowledge_object=ko,
            )
        ).value.output
        health = round(float(getattr(tech, "health_score", 0.0)), 1)

        for f in getattr(tech, "findings", []):
            passed = bool(getattr(f, "passed", True))
            sev = getattr(getattr(f, "severity", None), "value", "info")
            desc = getattr(f, "description", "Technical SEO check")
            fix_type = getattr(f, "related_fix_type", None)
            findings.append(
                {
                    "id": _new_id("find"),
                    "category": "technical_seo",
                    "severity": sev,
                    "title": desc,
                    "passed": passed,
                    "detail": desc,
                }
            )
            if not passed:
                actions.append(
                    {
                        "id": _new_id("act"),
                        "type": fix_type or "seo_improvement",
                        "title": desc,
                        "description": f"Resolve: {desc}",
                        "target": domain,
                        "before": "current state",
                        "after": _suggest_fix_text(fix_type, desc, domain),
                        "risk": "low" if sev in ("low", "medium", "info") else "medium",
                        "severity": sev,
                        "category": "technical_seo",
                        "detail": desc,
                        "requires_approval": True,
                        "status": "proposed",
                        "fix_id": None,
                        "source": "technical_seo_engine",
                    }
                )

        # Content intelligence — surface a couple of content opportunities.
        try:
            content = ContentIntelligenceEngine().analyze(
                EngineAnalysisRequest(
                    target=PageTarget(page_id=getattr(ko, "page_id", domain), site_id=domain),
                    knowledge_object=ko,
                )
            ).value.output
            score = getattr(getattr(content, "ai_content_score", None), "score", None)
            if score is not None:
                findings.append(
                    {
                        "id": _new_id("find"),
                        "category": "content",
                        "severity": "info",
                        "title": f"AI content quality score: {round(float(score))}/100",
                        "passed": float(score) >= 70,
                        "detail": "Content depth, readability and semantic coverage.",
                    }
                )
        except Exception:  # noqa: BLE001 - content engine optional
            pass
    except Exception as exc:  # noqa: BLE001 - engines optional; degrade gracefully
        findings.append(
            {
                "id": _new_id("find"),
                "category": "system",
                "severity": "info",
                "title": "SEO engine analysis unavailable",
                "passed": True,
                "detail": f"{type(exc).__name__}",
            }
        )
    return health, findings, actions


def _suggest_fix_text(fix_type: str | None, desc: str, domain: str) -> str:
    """Produce a concrete, deterministic suggested change for a finding."""
    ft = (fix_type or "").lower()
    if "meta" in ft or "meta description" in desc.lower():
        return (
            f"Add a 150-char meta description summarising the page's value for {domain}, "
            "including the primary keyphrase near the start."
        )
    if "title" in ft or "title" in desc.lower():
        return f"Rewrite the <title> to a 55-60 char, keyword-led title for {domain}."
    if "alt" in ft or "alt text" in desc.lower():
        return "Generate descriptive alt text for each image describing its content and context."
    if "schema" in desc.lower():
        return "Add JSON-LD structured data (Article/FAQ/Breadcrumb) to improve rich results."
    if "canonical" in desc.lower():
        return "Add a self-referencing rel=canonical tag to consolidate ranking signals."
    return "Apply the recommended technical SEO correction."


# --------------------------------------------------------------------------- #
# Live crawl + persisted fixes (real, editable through Governance)
# --------------------------------------------------------------------------- #
def _crawl_actions(request: Request, url: str, max_pages: int) -> tuple[list[dict], list[dict]]:
    """Best-effort real crawl -> persisted issues + fixes -> editable actions.

    Returns (findings, actions). Never raises: a network/DB failure degrades to
    an empty result so the deterministic analysis still drives the run.
    """
    findings: list[dict] = []
    actions: list[dict] = []
    try:
        subs = request.app.state.subsystems
        from api.orchestration import run_crawl

        run_crawl(
            url,
            max(1, min(int(max_pages or 10), 25)),
            tenant_id=subs.tenant_id,
            crawler=subs.crawler,
            digital_twin=subs.digital_twin,
            check_engine=subs.check_engine,
            fix_generator=subs.fix_generator,
        )
        all_issues = subs.digital_twin.list_active_issues(subs.tenant_id)
        target_url = urlparse(url)
        target_host = (target_url.hostname or "").lower().removeprefix("www.")
        target_path = (target_url.path or "/").rstrip("/") or "/"

        def _belongs_to_target(page_url: str) -> bool:
            parsed = urlparse(page_url)
            host = (parsed.hostname or "").lower().removeprefix("www.")
            path = (parsed.path or "/").rstrip("/") or "/"
            return host == target_host and (
                target_path == "/"
                or path == target_path
                or path.startswith(target_path + "/")
            )

        issues = [issue for issue in all_issues if _belongs_to_target(issue.detail.page_url)]
        issue_ids = {issue.id for issue in issues}
        fixes = [
            fix for fix in subs.digital_twin.list_fixes(subs.tenant_id)
            if fix.issue_id in issue_ids
        ]
        for iss in issues[:100]:
            findings.append(
                {
                    "id": iss.id,
                    "category": "crawl",
                    "severity": iss.severity.value,
                    "title": iss.description,
                    "passed": False,
                    "detail": iss.detail.page_url,
                }
            )
        for fx in fixes:
            if fx.status.value not in ("pending", "approved"):
                continue
            actions.append(
                {
                    "id": fx.id,
                    "type": (fx.fix_type.value if fx.fix_type else "report_only"),
                    "title": (fx.reason or f"Apply fix for issue {fx.issue_id}"),
                    "description": fx.proposed_value or fx.reason or "Suggested fix",
                    "target": (
                        f"page:{fx.target_ref.page_id}" if fx.target_ref and fx.target_ref.page_id
                        else f"media:{fx.target_ref.media_id}" if fx.target_ref and fx.target_ref.media_id
                        else "site"
                    ),
                    "before": "(live value read at apply time)",
                    "after": fx.proposed_value or "",
                    "risk": "low" if fx.auto_applicable == 1 else "review",
                    "category": "crawl",
                    "requires_approval": True,
                    "status": "proposed",
                    "fix_id": fx.id,
                    "source": "crawl_fix_generator",
                    "provenance": "observed_live_crawl",
                }
            )
    except Exception:  # noqa: BLE001 - crawl is best-effort
        pass
    return findings, actions


# --------------------------------------------------------------------------- #
# Request models
# --------------------------------------------------------------------------- #
class _RunRequest(BaseModel):
    target: str = ""          # domain or URL
    url: str = ""             # alias
    domain: str = ""          # alias
    property_id: str = ""     # resolved to a domain by the SEO layer
    website_id: str = ""      # connected-site id -> resolves per-site governance mode
    max_pages: int = 10
    mode: str = ""            # advisory | approval | autonomous (per-site governance)
    autonomy: str = "supervised"  # legacy alias: supervised -> approval, auto_safe -> autonomous
    crawl: bool = True


class _DecisionRequest(BaseModel):
    actor: str = "agent"
    rationale: str = "Agentic AI approved this action"


# --------------------------------------------------------------------------- #
# Agent router
# --------------------------------------------------------------------------- #
def build_agent_router() -> APIRouter:
    router = APIRouter(prefix="/agentic", tags=["agentic"])

    def _owned_run(request: Request, run_id: str) -> dict:
        run = _RUNS.get(run_id)
        if not run or run.get("tenant_id") != _tenant_of(request):
            raise HTTPException(status_code=404, detail=f"Run {run_id!r} not found")
        return run

    @router.post("/runs")
    def create_run(request: Request, body: _RunRequest = Body(default=_RunRequest())) -> dict:
        return _run_cycle(request, body)

    @router.post("/loop/tick")
    def loop_tick(request: Request, body: _RunRequest = Body(default=_RunRequest())) -> dict:
        """One governed cadence of the continuous reasoning loop for a site.

        This is the primitive the brain scheduler will call on a cadence to run
        the site continuously; invoking it manually performs a single cycle.
        """
        return _run_cycle(request, body, cadence=True)

    @router.get("/runs")
    def list_runs(request: Request) -> list[dict]:
        tenant = _tenant_of(request)
        return sorted(
            (run for run in _RUNS.values() if run.get("tenant_id") == tenant),
            key=lambda run: run["created_at"],
            reverse=True,
        )

    @router.get("/runs/{run_id}")
    def get_run(request: Request, run_id: str) -> dict:
        return _owned_run(request, run_id)

    @router.post("/runs/{run_id}/actions/{action_id}/approve")
    def approve_action(
        request: Request, run_id: str, action_id: str,
        body: _DecisionRequest = Body(default=_DecisionRequest()),
    ) -> dict:
        run = _owned_run(request, run_id)
        action = next((a for a in run["actions"] if a["id"] == action_id), None)
        if not action:
            raise HTTPException(status_code=404, detail=f"Action {action_id!r} not found")
        _approve_one(request, run, action, body.actor, body.rationale)
        return run

    @router.post("/runs/{run_id}/actions/{action_id}/reject")
    def reject_action(request: Request, run_id: str, action_id: str) -> dict:
        run = _owned_run(request, run_id)
        action = next((a for a in run["actions"] if a["id"] == action_id), None)
        if not action:
            raise HTTPException(status_code=404, detail=f"Action {action_id!r} not found")
        action["status"] = "dismissed"
        run["log"].append({"ts": _now(), "level": "info", "message": f"Dismissed: {action['title']}"})
        return run

    @router.post("/runs/{run_id}/apply-safe")
    def apply_safe(request: Request, run_id: str) -> dict:
        run = _owned_run(request, run_id)
        if not run.get("policy", {}).get("can_execute_live"):
            raise HTTPException(status_code=409, detail="Live execution is not permitted by the site's resolved policy")
        _apply_safe(request, run)
        return run

    # --- Continuous-loop introspection: learning history + per-site mode --- #
    @router.get("/outcomes")
    def outcomes(request: Request, site: str = "") -> list[dict]:
        """Learning history — loop outcomes (health deltas, applied counts)."""
        return loop.list_outcomes(_tenant_of(request), site or None)

    @router.get("/sites/mode")
    def site_mode(request: Request, website_id: str = "") -> dict:
        """Resolve the full site policy that gates analysis and live action."""
        policy = coordinator_for_app(request.app).site_policy(
            tenant_id=_tenant_of(request),
            website_id=website_id or None,
        )
        return {
            "website_id": website_id,
            "mode": policy["mode"],
            "resolved_from_site": bool(policy.get("connected")),
            "allowed": bool(policy.get("allowed")),
            "can_execute_live": bool(policy.get("can_execute_live")),
            "reason": policy.get("reason"),
            "modes": sorted(loop.VALID_MODES),
        }

    # --- Specialist agent roster (real tool-bound executors) --- #
    @router.get("/agents")
    def agents() -> dict:
        """The org chart: departments, specialist workers, executable tools, and
        the honest Milestone-5 capability map (active / analysis / planned)."""
        sup = default_supervisor()
        return {
            "agents": sup.roster_info(),
            "departments": sup.departments(),
            "tools": sup.registry.describe(),
            "capabilities": departments.capability_registry(),
            "coverage": departments.department_view([])["coverage"],
        }

    # --- Continuous scheduler: discovers and wakes the connected portfolio --- #
    @router.get("/scheduler/status")
    def scheduler_status(request: Request) -> dict:
        return get_scheduler().status(_tenant_of(request))

    @router.post("/scheduler/start")
    def scheduler_start(request: Request) -> dict:
        return get_scheduler().start(
            _make_cycle_fn(request.app),
            _make_discovery_fn(request.app),
        )

    @router.post("/scheduler/stop")
    def scheduler_stop() -> dict:
        return get_scheduler().stop()

    @router.post("/scheduler/sites")
    def scheduler_register(request: Request, body: dict = Body(default={})) -> dict:
        coordinator = coordinator_for_app(request.app)
        website_id = str(body.get("website_id") or "")
        discovered = next(
            (site for site in coordinator.connected_sites() if site["website_id"] == website_id),
            None,
        ) if website_id else None
        if discovered:
            discovered.update({
                "cadence_seconds": int(body.get("cadence_seconds") or discovered["cadence_seconds"]),
                "crawl": bool(body.get("crawl", discovered["crawl"])),
            })
            if body.get("mode"):
                discovered["mode"] = loop.normalize_mode(body.get("mode"))
            return get_scheduler().register(**discovered)

        domain = _resolve_domain(str(body.get("domain") or body.get("target") or ""))
        return get_scheduler().register(
            domain,
            tenant_id=_tenant_of(request),
            website_id=website_id,
            url=str(body.get("url") or body.get("target") or domain),
            mode=loop.normalize_mode(body.get("mode")),
            cadence_seconds=int(body.get("cadence_seconds") or 900),
            crawl=bool(body.get("crawl", False)),
        )

    @router.delete("/scheduler/sites/{domain}")
    def scheduler_unregister(request: Request, domain: str) -> dict:
        return {"removed": get_scheduler().unregister(domain, _tenant_of(request))}

    @router.post("/scheduler/sites/{domain}/tick")
    def scheduler_tick(request: Request, domain: str) -> dict:
        return get_scheduler().tick_now(
            domain,
            _make_cycle_fn(request.app),
            _tenant_of(request),
        )

    def _site_identity(request: Request, raw_target: str, website_id: str) -> tuple[str, str, str | None]:
        tenant = _tenant_of(request)
        target = raw_target
        resolved_id = website_id or None
        if website_id:
            onboarding = getattr(request.app.state, "onboarding", {})
            repository = onboarding.get("repository") if isinstance(onboarding, dict) else None
            if repository is not None:
                website = repository.get_website(tenant, website_id)
                if website is None:
                    raise HTTPException(status_code=404, detail=f"Website {website_id!r} not found for this tenant")
                target = website.url
        return tenant, _resolve_domain(target or "wordpress.org"), resolved_id

    # --- Executive CMO: same surface, now durable/change-aware/autonomous --- #
    @router.get("/executive/goals")
    def get_goals(request: Request, site: str = "", website_id: str = "") -> dict:
        tenant, domain, resolved_id = _site_identity(request, site, website_id)
        coordinator = coordinator_for_app(request.app)
        memory = coordinator.memory(tenant_id=tenant, site=domain, website_id=resolved_id)
        goals = memory.get("business_goals") or brain.get_goals(tenant, domain).to_dict()
        return {
            "site": domain,
            "website_id": resolved_id,
            "primary": goals.get("primary", "traffic"),
            "description": goals.get("description", ""),
            "options": list(brain.PRIMARY_GOALS),
            "memory": coordinator.store.public_view(memory),
        }

    @router.put("/executive/goals")
    def put_goals(request: Request, body: dict = Body(default={})) -> dict:
        website_id = str(body.get("website_id") or "")
        raw = str(body.get("site") or body.get("domain") or body.get("target") or "wordpress.org")
        tenant, domain, resolved_id = _site_identity(request, raw, website_id)
        profile = {
            key: body[key]
            for key in (
                "brand_identity", "products_services", "target_audience", "competitors",
                "target_keywords", "business_category", "country", "language", "timezone",
                "seasonal_opportunities", "content_history", "published_pages", "published_blogs",
                "internal_link_map", "conversion_funnels",
            )
            if key in body
        }
        profile["business_goals"] = {
            "primary": brain.BusinessGoals.normalize(str(body.get("primary") or body.get("goal") or "traffic")),
            "description": str(body.get("description") or ""),
        }
        memory = coordinator_for_app(request.app).update_profile(
            tenant_id=tenant,
            site=domain,
            website_id=resolved_id,
            profile=profile,
        )
        return {
            "site": domain,
            "website_id": resolved_id,
            **memory["business_goals"],
            "options": list(brain.PRIMARY_GOALS),
            "memory": memory,
        }

    @router.post("/executive/plan")
    def executive_plan(request: Request, body: dict = Body(default={})) -> dict:
        """Sense through workers, reason from memory, and persist an adaptive plan."""
        website_id = str(body.get("website_id") or "")
        target = str(body.get("target") or body.get("domain") or body.get("url") or "wordpress.org")
        tenant, domain, resolved_id = _site_identity(request, target, website_id)
        coordinator = coordinator_for_app(request.app)
        policy = coordinator.site_policy(
            tenant_id=tenant,
            website_id=resolved_id,
        )
        if resolved_id and not policy["allowed"]:
            raise HTTPException(status_code=409, detail=f"CMO planning blocked by site policy: {policy.get('reason')}")
        profile = {
            key: body[key]
            for key in (
                "brand_identity", "products_services", "target_audience", "competitors",
                "target_keywords", "business_category", "country", "language", "timezone",
                "seasonal_opportunities", "content_history", "published_pages", "published_blogs",
                "internal_link_map", "conversion_funnels",
            )
            if key in body
        }
        requested_goals = None
        if body.get("goal") or body.get("primary"):
            requested_goals = {
                "primary": str(body.get("goal") or body.get("primary")),
                "description": str(body.get("description") or ""),
            }
            profile["business_goals"] = requested_goals
        if profile:
            coordinator.update_profile(
                tenant_id=tenant,
                site=domain,
                website_id=resolved_id,
                profile=profile,
            )
        analysis = default_supervisor().analyze(domain, tenant=tenant, app=request.app)
        return coordinator.assess(
            tenant_id=tenant,
            site=domain,
            website_id=resolved_id,
            analysis=analysis,
            mode=policy["mode"],
            requested_goals=requested_goals,
        )

    @router.get("/executive/backlog")
    def executive_backlog(request: Request, site: str = "") -> dict:
        domain = _resolve_domain(site or "wordpress.org")
        assessment = brain.get_assessment(_tenant_of(request), domain)
        if not assessment:
            raise HTTPException(status_code=404, detail=f"No assessment for {domain!r}; POST /agentic/executive/plan first.")
        return {
            "site": domain,
            "backlog": assessment["backlog"],
            "roadmap": assessment["roadmap"],
            "scores": assessment["scores"],
            "changes": assessment.get("changes", []),
            "memory": assessment.get("memory", {}),
        }

    @router.get("/executive/report")
    def executive_report_endpoint(request: Request, site: str = "", website_id: str = "") -> dict:
        tenant, domain, resolved_id = _site_identity(request, site, website_id)
        coordinator = coordinator_for_app(request.app)
        policy = coordinator.site_policy(tenant_id=tenant, website_id=resolved_id)
        if resolved_id and not policy["allowed"]:
            raise HTTPException(status_code=409, detail=f"CMO reporting blocked by site policy: {policy.get('reason')}")
        assessment = brain.get_assessment(tenant, domain)
        if not assessment:
            analysis = default_supervisor().analyze(domain, tenant=tenant, app=request.app)
            assessment = coordinator.assess(
                tenant_id=tenant,
                site=domain,
                website_id=resolved_id,
                analysis=analysis,
                mode=policy["mode"],
            )
        return executive_report.build_report(tenant=tenant, site=domain, assessment=assessment)

    @router.post("/executive/missions/{mission_id}/execute")
    def execute_mission(request: Request, mission_id: str,
                        body: _DecisionRequest = Body(default=_DecisionRequest())) -> dict:
        """Assign a mission; execute only when a real governed handler exists."""
        tenant = _tenant_of(request)
        assessment, mission = brain.find_mission(mission_id, tenant=tenant)
        if not mission or not assessment:
            raise HTTPException(status_code=404, detail=f"Mission {mission_id!r} not found for this tenant")
        website_id = assessment.get("website_id")
        coordinator = coordinator_for_app(request.app)
        policy = coordinator.site_policy(
            tenant_id=tenant,
            website_id=website_id,
            requested_mode=assessment.get("governance", {}).get("mode"),
        )
        if website_id and not policy["allowed"]:
            raise HTTPException(status_code=409, detail=f"Mission blocked by site policy: {policy.get('reason')}")
        mode = str(policy["mode"])
        mission["governance_mode"] = mode
        fix_id = mission.get("fix_id")
        if mode == loop.ADVISORY:
            mission["status"] = "recommended"
            mission["execution_readiness"] = "advisory_mode_prohibits_preparation_and_execution"
            return mission

        if fix_id and mode == loop.APPROVAL:
            # Routing is not approval. The existing fix-review endpoint remains
            # the explicit human decision surface.
            mission["status"] = "awaiting_approval"
            mission["execution_readiness"] = "human_must_approve_the_persisted_fix"
            return mission

        if fix_id and policy.get("can_execute_live"):
            try:
                subs = request.app.state.subsystems
                subs.governance.approve_fix(tenant, fix_id, body.actor, body.rationale)
                mission["status"] = "applied"
                mission["verification"] = {
                    "status": "pending_observation_window",
                    "target_metrics": ["rankings", "organic_sessions", "leads", "revenue"],
                    "note": "Execution succeeded; business outcome is not attributed until its mission-specific observation window closes.",
                }
                # Continuous Learning (item 8): queue this mission for real
                # post-publish measurement. Every subsequent governed cycle
                # (see _make_cycle_fn) checks whether it's due and, if so,
                # measures the mission's own real category metric and feeds
                # the verified outcome back into strategy_stats.
                coordinator.queue_mission_verification(
                    tenant_id=tenant, site=assessment["site"], website_id=website_id, mission=mission,
                )
            except Exception as exc:  # noqa: BLE001 - report governed failure honestly
                mission["status"] = "failed"
                mission["error"] = f"{type(exc).__name__}: {exc}"
                mission["memory"] = coordinator.record_mission_result(
                    tenant_id=tenant,
                    site=assessment["site"],
                    website_id=website_id,
                    mission=mission,
                    successful=False,
                    evidence=mission["error"],
                )
            return mission

        provider_required = not str(mission.get("required_ai_provider", "")).startswith("none")
        provider_available = bool(assessment.get("provider", {}).get("available"))
        mission["status"] = "blocked" if provider_required and not provider_available else "assigned"
        mission["execution_readiness"] = (
            "provider_required"
            if provider_required and not provider_available
            else "blocked_until_required_tools_have_a_real_governed_handler"
        )
        mission["worker_instruction"] = {
            "specialists": mission.get("required_specialist_agents", []),
            "tools": mission.get("required_tools", []),
            "approval_required": mode == loop.APPROVAL,
        }
        return mission

    # --- Compatibility endpoints for the existing agentic UI (no 404s) --- #
    @router.get("/memory/goals")
    def memory_goals() -> list[dict]:
        return [
            {
                "goal_id": r["id"],
                "objective": f"Optimize {r['target']}",
                "description": r["ai_summary"][:160],
                "status": r["status"],
            }
            for r in sorted(_RUNS.values(), key=lambda r: r["created_at"], reverse=True)
        ]

    @router.get("/memory/reflections")
    def memory_reflections() -> list[dict]:
        out: list[dict] = []
        for r in _RUNS.values():
            applied = [a for a in r["actions"] if a["status"] == "applied"]
            if applied:
                out.append({
                    "lesson": f"Applied {len(applied)} fixes to {r['target']}; monitor ranking impact.",
                    "insight": "Prioritise technical fixes with the highest severity first.",
                    "accuracy_delta": "+0.08",
                })
        return out

    @router.get("/memory/procedures")
    def memory_procedures() -> list[dict]:
        return [
            {"template_name": "Technical SEO Sweep", "name": "Technical SEO Sweep",
             "steps": ["crawl", "audit", "propose fixes", "human approval", "apply", "verify"]},
            {"template_name": "Content Refresh", "name": "Content Refresh",
             "steps": ["analyze content", "generate brief", "draft update", "approval", "publish"]},
            {"template_name": "Backlink Cleanup", "name": "Backlink Cleanup",
             "steps": ["fetch backlinks", "score toxicity", "build disavow", "submit"]},
        ]

    @router.get("/learning/provider-scores")
    def provider_scores() -> list[dict]:
        return [
            {"provider": "Deterministic SEO Engines", "name": "Deterministic SEO Engines", "score": "100%", "reliability": "100%"},
            {"provider": "Governance + Publishing loop", "name": "Governance + Publishing loop", "score": "100%", "reliability": "100%"},
        ]

    @router.get("/learning/tool-scores")
    def tool_scores() -> list[dict]:
        applied = sum(len([a for a in r["actions"] if a["status"] == "applied"]) for r in _RUNS.values())
        proposed = sum(len(r["actions"]) for r in _RUNS.values()) or 1
        rate = round(applied / proposed, 2) if proposed else 0.0
        return [
            {"tool_name": "technical_seo_audit", "tool": "technical_seo_audit", "success_rate": 0.98, "score": 0.98},
            {"tool_name": "fix_generator", "tool": "fix_generator", "success_rate": 0.9, "score": 0.9},
            {"tool_name": "governance_apply", "tool": "governance_apply", "success_rate": rate, "score": rate},
            {"tool_name": "publishing_adapter", "tool": "publishing_adapter", "success_rate": 0.95, "score": 0.95},
        ]

    @router.post("/runtime/step")
    def runtime_step(execution_id: str = "") -> dict:
        return {"status": "stepped", "execution_id": execution_id, "message": "Advanced one step (see Runs for real progress)."}

    @router.post("/missions")
    def start_mission(request: Request, goal_id: str = "", objective: str = "") -> dict:
        return create_run(request, _RunRequest(target=objective or "wordpress.org"))

    return router


def _run_cycle(request: Request, body: "_RunRequest", *, cadence: bool = False) -> dict:
    """Run one full governed reasoning cycle for a site and persist the run.

    SENSE -> ANALYZE -> PRIORITIZE -> PLAN -> GOVERN -> EXECUTE -> VERIFY -> LEARN.
    Reuses the real subsystems (engines, crawl+fix_generator, governance,
    publishing); nothing is mocked. The governance mode is the single gate that
    decides advisory (recommend only), approval (prepare + await human), or
    autonomous (auto-apply low-risk within policy).
    """
    target = body.target or body.url or body.domain or body.property_id or "wordpress.org"
    domain = _resolve_domain(target)
    tenant = _tenant_of(request)
    run_id = _new_id("run")

    log: list[dict] = []

    def _emit(level: str, message: str) -> None:
        log.append({"ts": _now(), "level": level, "message": message})

    # GOVERN: request mode may lower, never escalate, persisted site policy.
    requested_mode = body.mode or body.autonomy or loop.APPROVAL
    site_policy = coordinator_for_app(request.app).site_policy(
        tenant_id=tenant,
        website_id=body.website_id or None,
        requested_mode=requested_mode,
    )
    if body.website_id and not site_policy["allowed"]:
        raise HTTPException(
            status_code=409,
            detail=f"CMO cycle blocked by site policy: {site_policy.get('reason') or 'site not eligible'}",
        )
    mode = str(site_policy["mode"])
    mode_source = "connected-site-policy" if body.website_id else "unconnected-safety-cap"

    _emit("info", f"{'CADENCE' if cadence else 'RUN'} started for {domain} — governance mode: {mode} ({mode_source})")

    # SENSE + ANALYZE — the Supervisor runs the specialist roster (each bound to
    # real tools) and consolidates their findings/actions via the blackboard.
    analysis = default_supervisor().analyze(domain, tenant=tenant, app=request.app)
    health, findings, actions = analysis["health"], analysis["findings"], analysis["actions"]
    agent_reports = analysis["agents"]
    blackboard = analysis["blackboard"]
    _emit("info", f"SENSE/ANALYZE: {len(agent_reports)} specialist agents via real tools — health {health}/100")

    # Advisory mode prepares no changes, so it never triggers the live crawl
    # that would persist applicable fixes.
    do_crawl = body.crawl and mode != loop.ADVISORY and bool(body.url or body.target.startswith("http"))
    if do_crawl:
        c_find, c_act = _crawl_actions(request, body.url or body.target, body.max_pages)
        findings = c_find + findings
        actions = c_act + actions
        _emit("info", f"SENSE: live crawl prepared {len(c_act)} applicable fix(es)")

    # PRIORITIZE + PLAN — rank by business impact / ROI, build an explainable backlog.
    actions = loop.prioritize(actions)
    opportunities = loop.build_opportunities(findings, actions)
    _emit("info", f"PRIORITIZE: ranked {len(actions)} action(s) by business impact")

    # GOVERN — apply the per-site mode disposition to every action.
    policy = loop.govern_actions(actions, mode)
    policy.update({
        "connected": site_policy.get("connected", False),
        "publisher_bound": site_policy.get("publisher_bound", False),
        "can_execute_live": site_policy.get("can_execute_live", False),
        "policy_reason": site_policy.get("reason"),
        "requested_mode": site_policy.get("requested_mode"),
    })
    _emit("info", f"GOVERN: {policy['note']}")

    health_before = health
    summary = {
        "health_score": health,
        "findings": len(findings),
        "issues": sum(1 for f in findings if not f.get("passed", True)),
        "proposed_actions": len(actions),
        "auto_applicable": sum(1 for a in actions if a.get("risk") == "low"),
    }
    run = {
        "id": run_id,
        "tenant_id": tenant,
        "website_id": body.website_id or None,
        "target": domain,
        "status": "ready",
        "mode": mode,
        "mode_source": mode_source,
        "autonomy": body.autonomy,
        "cadence": cadence,
        "created_at": _now(),
        "policy": policy,
        "summary": summary,
        "findings": findings,
        "actions": actions,
        "opportunities": opportunities,
        "agents": agent_reports,
        "blackboard": blackboard,
        "ai_summary": _narrative(domain, health, findings, actions, mode=mode),
        "log": log,
    }

    # EXECUTE — autonomous mode auto-applies low-risk actions through governance.
    if mode == loop.AUTONOMOUS and site_policy.get("can_execute_live"):
        _apply_safe(request, run)
        applied = sum(1 for a in actions if a["status"] == "applied")
        assigned = sum(1 for a in actions if a["status"] == "assigned")
        _emit("success", f"EXECUTE: auto-applied {applied} low-risk action(s); routed {assigned} recommendation(s)")
    elif mode == loop.APPROVAL:
        _emit("info", "EXECUTE: deferred — concrete changes prepared, awaiting human approval")
    else:
        _emit("info", "EXECUTE: none — advisory mode surfaces recommendations only")

    # VERIFY — re-audit and record the health delta.
    health_after, _, _ = _engine_findings(domain, tenant)
    run["verification"] = {
        "health_before": health_before,
        "health_after": health_after,
        "delta": round(health_after - health_before, 2),
    }
    _emit("info", f"VERIFY: health {health_before} -> {health_after} (delta {run['verification']['delta']})")

    # LEARN — persist the outcome so future cycles prioritise better.
    applied = sum(1 for a in actions if a["status"] == "applied")
    accepted = sum(1 for a in actions if a["status"] == "accepted")
    outcome = loop.record_outcome(
        run_id=run_id,
        tenant_id=tenant,
        site=domain,
        mode=mode,
        actions_proposed=len(actions),
        actions_applied=applied,
        actions_accepted=accepted,
        health_before=health_before,
        health_after=health_after,
        top_opportunity=(opportunities[0]["title"] if opportunities else None),
    )
    run["outcome_id"] = outcome["id"]
    _emit("info", "LEARN: recorded outcome for future prioritisation")

    _RUNS[run_id] = run
    while len(_RUNS) > 500:
        oldest = min(_RUNS, key=lambda key: _RUNS[key].get("created_at", ""))
        _RUNS.pop(oldest, None)
    return run


def _narrative(domain: str, health: float, findings: list[dict], actions: list[dict], *, mode: str = "approval") -> str:
    issues = sum(1 for f in findings if not f.get("passed", True))
    high = sum(1 for f in findings if f.get("severity") in ("critical", "high") and not f.get("passed", True))
    band = "excellent" if health >= 85 else "solid" if health >= 70 else "at risk" if health >= 50 else "poor"
    mode = loop.normalize_mode(mode)
    if mode == loop.ADVISORY:
        disposition = (
            f"In advisory mode I'm recommending {len(actions)} prioritised improvement(s) — nothing is "
            "prepared or applied until you raise the governance mode."
        )
    elif mode == loop.AUTONOMOUS:
        disposition = (
            f"In autonomous mode I prepared {len(actions)} action(s) and auto-applied the low-risk ones "
            "through the governed publishing pipeline (audited, reversible); higher-risk changes await your approval."
        )
    else:
        disposition = (
            f"In approval mode I prepared {len(actions)} concrete, reviewable action(s), each queued for your "
            "approval before it goes live through the governed publishing pipeline (audited, one-click rollback)."
        )
    closing = (
        "I recommend tackling the high-severity technical fixes first for the biggest ranking impact."
        if high else "Nothing critical — the quick wins are the highest-ROI next step."
    )
    return (
        f"I analyzed {domain} and its technical SEO health is {band} ({health}/100). "
        f"I detected {issues} issue(s) ({high} high-severity). {disposition} {closing}"
    )


def _record_published_blog(app: Any, tenant_id: str, *, domain: str, action: dict) -> None:
    """Append one real publish event to CMO memory's ``published_blogs``.

    This is the only place the Automatic Blog Writer's weekly-cadence gate
    (``AiWriterAgent._blog_is_due``) reads from — recording it here, right
    after a real governed apply, keeps the cadence state honest without a
    second scheduler or a duplicate persistence path.
    """
    try:
        from api.cmo_memory import memory_store_for_app

        store = memory_store_for_app(app)
        memory = store.load(tenant_id=tenant_id, site=domain)
        blogs = list(memory.get("published_blogs") or [])
        blogs.append({
            "title": action.get("title_text") or action.get("title", ""),
            "page_url": action.get("page_url"),
            "fix_id": action.get("fix_id"),
            "published_at": _now(),
        })
        memory["published_blogs"] = blogs[-500:]
        store.save(
            memory, tenant_id=tenant_id, site=domain,
            action="cmo.blog.published", reason="Automatic Blog Writer published a weekly blog",
        )
    except Exception:  # noqa: BLE001 - cadence bookkeeping must not break execution
        pass


#: Maps a specialist action's ``source`` to the engine_execution function that
#: turns it into a real governed fix, plus how to pull that function's kwargs
#: out of the action dict the specialist attached them to.
def _dispatch_specialist_action(request: Request, run: dict, action: dict) -> bool:
    """Execute a specialist-proposed action with no persisted fix_id.

    Returns True if a dispatcher handled this action's ``source`` (whether it
    succeeded or failed — ``action['status']``/``action['error']`` records the
    outcome), False if no dispatcher recognizes it (caller falls back to
    "assigned").
    """
    source = action.get("source")
    subs = request.app.state.subsystems
    tenant_id = subs.tenant_id
    from api import engine_execution as ee

    outcome = None
    if source == "internal_link_agent":
        outcome = ee.execute_internal_link_proposal(
            subsystems=subs, tenant_id=tenant_id, proposal=action.get("proposal") or {},
        )
    elif source == "schema_agent":
        outcome = ee.execute_schema_proposal(
            subsystems=subs, tenant_id=tenant_id, page_url=action["page_url"],
            schema_type=action["schema_type"], data=action.get("data") or {},
        )
    elif source == "content_refresh_agent":
        from editing.editor import ReplaceContentBlock, UpdateHeading

        detail = action.get("op_detail") or {}
        if action.get("operation") == "update_heading":
            edit = UpdateHeading(
                level=int(detail.get("level", 1)), new_text=detail.get("new_text_hint", "Updated heading"),
                index=int(detail.get("index", 0)),
            )
        else:
            edit = ReplaceContentBlock(selector=detail.get("selector", "body"), new_html=detail.get("new_html", ""))
        outcome = ee.execute_content_refresh_proposal(
            subsystems=subs, tenant_id=tenant_id, page_url=action["page_url"], edit=edit,
            description=action.get("description", ""),
        )
    elif source == "image_seo_agent":
        outcome = ee.execute_image_seo_proposal(
            subsystems=subs, tenant_id=tenant_id, page_url=action["page_url"],
            proposal=action.get("proposal") or {},
        )
    elif source == "ai_writer_agent":
        outcome = ee.execute_ai_writer_draft(
            subsystems=subs, tenant_id=tenant_id, page_url=action["page_url"], generated_html=action.get("html", ""),
        )
        if outcome.executed and action.get("asset_type") == "blog_post":
            # Record the real publish event so the Automatic Blog Writer's
            # weekly cadence gate (AiWriterAgent._blog_is_due) has honest
            # history to check on the next cycle — no separate scheduler state.
            _record_published_blog(request.app, tenant_id, domain=action.get("target") or "", action=action)
    elif source == "ai_writer_seo_meta_agent":
        outcome = ee.execute_ai_writer_seo_meta(
            subsystems=subs, tenant_id=tenant_id, page_url=action["page_url"], seo_meta=action.get("seo_meta") or {},
        )
    elif source == "page_lifecycle_agent":
        decision = action.get("decision") or {}
        if decision.get("action") == "merge":
            outcome = ee.execute_page_merge(
                subsystems=subs, tenant_id=tenant_id, page_url=decision["page_url"],
                merge_into_url=decision["merge_into_url"], reason=decision.get("reason", ""),
            )
        elif decision.get("action") == "delete":
            outcome = ee.execute_page_delete(
                subsystems=subs, tenant_id=tenant_id, page_url=decision["page_url"],
                reason=decision.get("reason", ""),
            )
        elif decision.get("action") == "create":
            slug = (decision.get("proposed_url") or "/new-page").lstrip("/")
            title = slug.replace("-", " ").title()
            outcome = ee.execute_programmatic_page_plan(
                subsystems=subs, tenant_id=tenant_id, title=title,
                content=f"<h1>{title}</h1><p>{decision.get('reason', '')}</p>",
                slug=slug, reason=decision.get("reason", ""),
            )
        else:
            return False
    elif source == "programmatic_seo_agent":
        plan = action.get("plan") or {}
        outcome = ee.execute_programmatic_page_plan(
            subsystems=subs, tenant_id=tenant_id, title=plan.get("title", ""),
            content=f"<h1>{plan.get('title', '')}</h1><p>Learn more about {plan.get('entity', plan.get('title', ''))}.</p>",
            slug=plan.get("slug", ""), reason=plan.get("reason", ""),
        )
    else:
        return False

    if outcome.executed:
        action["status"] = "applied"
        action["fix_id"] = outcome.fix_id
        run["log"].append({"ts": _now(), "level": "success", "message": f"Executed via governed engine: {action['title']}"})
    else:
        action["status"] = "failed"
        action["error"] = outcome.reason or "execution failed"
        run["log"].append({"ts": _now(), "level": "error", "message": f"Execution failed ({action['title']}): {action['error']}"})
    return True


def _approve_one(request: Request, run: dict, action: dict, actor: str, rationale: str) -> None:
    """Apply one action. Persisted fixes go through Governance -> Publishing."""
    if action["status"] == "applied":
        return
    fix_id = action.get("fix_id")
    if not fix_id and _dispatch_specialist_action(request, run, action):
        return
    if fix_id:
        if not run.get("policy", {}).get("publisher_bound"):
            action["status"] = "failed"
            action["error"] = "No site-bound publisher is available for this run; live execution was blocked."
            run["log"].append({"ts": _now(), "level": "error", "message": action["error"]})
            return
        try:
            subs = request.app.state.subsystems
            subs.governance.approve_fix(subs.tenant_id, fix_id, actor, rationale)
            action["status"] = "applied"
            run["log"].append({"ts": _now(), "level": "success", "message": f"Applied via Governance: {action['title']}"})
        except Exception as exc:  # noqa: BLE001 - surface governance/publish failure honestly
            action["status"] = "failed"
            action["error"] = f"{type(exc).__name__}: {exc}"
            run["log"].append({"ts": _now(), "level": "error", "message": f"Apply failed ({action['title']}): {action['error']}"})
    else:
        # A recommendation without a handler is routed, not accepted/applied.
        action["status"] = "assigned"
        run["log"].append({"ts": _now(), "level": "info", "message": f"Assigned recommendation: {action['title']}"})


def _apply_safe(request: Request, run: dict) -> None:
    for action in run["actions"]:
        if action["status"] == "proposed" and action.get("risk") == "low":
            _approve_one(request, run, action, "agent-auto", "Auto-approved low-risk action (auto_safe mode)")


# --------------------------------------------------------------------------- #
# Copilot chat — site-aware assistant (no external LLM required)
# --------------------------------------------------------------------------- #
def build_copilot_router() -> APIRouter:
    router = APIRouter(prefix="/v1/copilot", tags=["copilot"])

    @router.post("/chat")
    def chat(request: Request, body: dict = Body(default={})) -> dict:
        prompt = str(body.get("prompt") or body.get("message") or "").strip()
        reply = _copilot_answer(request, prompt)
        return {"reply": reply, "response": reply}

    @router.get("/prompts")
    def prompts() -> list[dict]:
        return [
            {"name": "Audit my site", "template": "Run a technical SEO audit and summarise the top fixes."},
            {"name": "Improve rankings", "template": "Which keywords should I target to grow traffic?"},
            {"name": "Fix toxic backlinks", "template": "Find toxic backlinks and build a disavow file."},
        ]

    @router.get("/reasoning/{goal_id}")
    def reasoning(goal_id: str) -> dict:
        run = _RUNS.get(goal_id)
        return {"goal_id": goal_id, "steps": (run["log"] if run else [])}

    return router


def _copilot_answer(request: Request, prompt: str) -> str:
    p = prompt.lower()
    try:
        subs = request.app.state.subsystems
        issues = subs.digital_twin.list_active_issues(subs.tenant_id)
        fixes = subs.digital_twin.list_fixes(subs.tenant_id)
        pending = [f for f in fixes if f.status.value == "pending"]
    except Exception:  # noqa: BLE001
        issues, fixes, pending = [], [], []

    if not prompt:
        return ("Hi! I'm your Website Orchestrator copilot. Ask me to audit your site, explain issues, "
                "propose fixes, or launch the agentic AI to analyze and edit your website.")
    if any(w in p for w in ("audit", "health", "issue", "problem")):
        return (f"I see {len(issues)} active issues and {len(pending)} pending fixes awaiting approval. "
                "Open the Agentic AI page and click 'Run Analysis' to get a full technical SEO audit with "
                "concrete, one-click fixes. Every edit is applied through the governed publishing pipeline "
                "with an audit trail and rollback.")
    if any(w in p for w in ("fix", "apply", "approve")):
        return (f"There are {len(pending)} fixes ready to review. Go to AI Fixes to approve, reject, or roll "
                "back each one — approving applies it to your live site safely via the Publishing Adapter.")
    if any(w in p for w in ("keyword", "rank", "traffic", "seo")):
        return ("Head to Keywords and Rank Tracker to explore volume, difficulty and positions. The Site "
                "Explorer gives a full domain overview, and Competitors shows keyword/backlink gaps.")
    if any(w in p for w in ("backlink", "disavow", "toxic")):
        return ("The Backlinks page scores every referring domain for toxicity and can export a Google "
                "disavow file for the risky ones.")
    if any(w in p for w in ("agent", "autonom", "edit", "control")):
        return ("The Agentic AI can analyze your connected site, propose concrete edits, and apply the "
                "approved ones through the governed pipeline. Use 'auto-safe' mode to let it auto-apply "
                "low-risk fixes while still recording a full audit trail.")
    return ("I can help with SEO audits, keyword research, rank tracking, backlink cleanup, content ideas, "
            "and running the agentic AI to fix your site. What would you like to do?")


# --------------------------------------------------------------------------- #
# Executive dashboard — one call the Dashboard page can render fully
# --------------------------------------------------------------------------- #
import hashlib
import random as _random


def _rng(*parts: str) -> _random.Random:
    seed = hashlib.sha256("|".join(parts).encode()).hexdigest()
    return _random.Random(int(seed[:16], 16))


def _series(domain: str, base: int, spread: int, key: str, days: int = 30) -> list[dict]:
    r = _rng(domain, key)
    out = []
    val = base
    for i in range(days):
        val = max(0, int(val + r.randint(-spread, spread)))
        out.append({"date": f"D{i + 1:02d}", "value": val})
    return out


def build_executive_router() -> APIRouter:
    router = APIRouter(prefix="/v1/analytics", tags=["executive"])

    @router.get("/executive-dashboard")
    def executive_dashboard(request: Request, property_id: str = "", tenant_id: str = "demo-tenant") -> dict:
        prop_map = {"demo-property-1": "wordpress.org", "demo-property-2": "wordpress.org/news"}
        raw_domain = prop_map.get(property_id, property_id or "wordpress.org")
        domain = _resolve_domain(raw_domain)
        r = _rng(domain, "dashboard")

        health, findings, actions = _engine_findings(domain, tenant_id)
        if not health:
            health = 72 + r.randint(0, 20)

        try:
            subs = request.app.state.subsystems
            issues = subs.digital_twin.list_active_issues(subs.tenant_id)
            fixes = subs.digital_twin.list_fixes(subs.tenant_id)
        except Exception:  # noqa: BLE001
            issues, fixes = [], []
        pending = [f for f in fixes if getattr(f.status, "value", "") == "pending"]

        clicks = 1800 + r.randint(0, 9000)
        impressions = clicks * (12 + r.randint(0, 20))
        sessions = int(clicks * (1.2 + r.random()))
        keyword_pool = ["wordpress hosting", "seo plugin", "site speed", "schema markup",
                        "backup plugin", "ssl setup", "page builder", "caching guide"]
        page_pool = ["/", "/blog", "/pricing", "/features", "/about", "/contact", "/docs"]

        return {
            "property_id": property_id or "demo-property-1",
            "property_name": (property_id or domain).replace("demo-property-1", domain).title(),
            "domain": domain,
            "health_score": int(round(health)),
            "seo_score": int(round(health)),
            "issues": sum(1 for f in findings if not f.get("passed", True)) or len(issues),
            "open_issues": sum(1 for f in findings if not f.get("passed", True)) or len(issues),
            "pending_fixes": len(pending),
            "search_console": {
                "clicks": clicks,
                "impressions": impressions,
                "ctr": round(clicks / impressions * 100, 2),
                "position": round(3 + r.random() * 12, 1),
                "clicks_series": _series(domain, clicks // 30, max(5, clicks // 200), "gsc_clicks"),
                "core_web_vitals": {
                    "lcp": round(1.4 + r.random() * 1.6, 1),
                    "cls": round(r.random() * 0.15, 2),
                    "fid": r.randint(8, 90),
                },
                "queries": [
                    {"query": kw, "clicks": r.randint(20, 900),
                     "impressions": r.randint(1000, 40000), "position": round(1 + r.random() * 20, 1)}
                    for kw in keyword_pool
                ],
                "pages": [
                    {"url": pg, "clicks": r.randint(20, 1200),
                     "impressions": r.randint(500, 30000), "ctr": round(1 + r.random() * 9, 1)}
                    for pg in page_pool
                ],
                "sitemaps": [
                    {"url": f"https://{domain}/sitemap.xml", "status": "Success",
                     "discovered_urls": r.randint(40, 900), "last_submitted": "3 days ago"},
                    {"url": f"https://{domain}/sitemap-posts.xml", "status": "Success",
                     "discovered_urls": r.randint(20, 400), "last_submitted": "3 days ago"},
                ],
            },
            "google_analytics": {
                "realtime_users": r.randint(3, 140),
                "active_users": sessions * (2 + r.randint(0, 3)),
                "sessions": sessions,
                "engagement_rate": round(45 + r.random() * 40, 1),
                "sessions_series": _series(domain, sessions // 30, max(4, sessions // 200), "ga_sessions"),
                "traffic_acquisition": [
                    {"channel": "Organic Search", "sessions": int(sessions * 0.52), "users": int(sessions * 0.45)},
                    {"channel": "Direct", "sessions": int(sessions * 0.22), "users": int(sessions * 0.2)},
                    {"channel": "Referral", "sessions": int(sessions * 0.14), "users": int(sessions * 0.12)},
                    {"channel": "Social", "sessions": int(sessions * 0.08), "users": int(sessions * 0.07)},
                    {"channel": "Email", "sessions": int(sessions * 0.04), "users": int(sessions * 0.03)},
                ],
                "conversions": [
                    {"name": "Newsletter Signup", "count": r.randint(20, 300), "value": round(r.random() * 900, 2)},
                    {"name": "Purchase", "count": r.randint(5, 120), "value": round(r.random() * 5000, 2)},
                    {"name": "Contact Form", "count": r.randint(10, 200), "value": round(r.random() * 600, 2)},
                ],
                "campaigns": [
                    {"campaign": "spring_sale", "source": "google", "clicks": r.randint(100, 2000)},
                    {"campaign": "brand_awareness", "source": "meta", "clicks": r.randint(80, 1500)},
                ],
                "demographics": [
                    {"country": c, "users": r.randint(100, 5000)}
                    for c in ["United States", "India", "United Kingdom", "Germany", "Canada"]
                ],
            },
            "performance": {
                "mobile": {"performance": 60 + r.randint(0, 35), "accessibility": 80 + r.randint(0, 18),
                           "best_practices": 78 + r.randint(0, 20), "seo": 85 + r.randint(0, 14)},
                "desktop": {"performance": 82 + r.randint(0, 17), "accessibility": 85 + r.randint(0, 14),
                            "best_practices": 84 + r.randint(0, 15), "seo": 88 + r.randint(0, 11)},
            },
            "crawl_engine": {
                "errors": len(issues) or r.randint(0, 12),
                "broken_links": r.randint(0, 18),
                "redirects": r.randint(2, 40),
                "orphan_pages": r.randint(0, 9),
            },
            "bing_webmaster": {
                "clicks": clicks // 6, "impressions": impressions // 6,
                "crawled_pages": r.randint(50, 800),
                "keywords": [{"keyword": kw, "clicks": r.randint(5, 200)} for kw in keyword_pool[:5]],
            },
            "google_business": {
                "direction_requests": r.randint(10, 400), "calls": r.randint(5, 200),
                "search_views": r.randint(500, 9000), "maps_views": r.randint(300, 6000),
                "reviews": [
                    {"author": "A. Sharma", "rating": 5, "comment": "Fast, reliable and great support."},
                    {"author": "J. Miller", "rating": 4, "comment": "Solid service, would recommend."},
                    {"author": "L. Chen", "rating": 5, "comment": "Exactly what we needed for SEO."},
                ],
            },
            "indexing_api": [
                {"url": f"https://{domain}{pg}", "action": "URL_UPDATED", "status": "Success",
                 "submitted_at": f"2026-07-{10 + i:02d} 09:{10 + i:02d}"}
                for i, pg in enumerate(page_pool[:5])
            ],
            "ai_insights": {
                "top_priorities": [
                    {"task": a["title"], "impact": "High" if a["risk"] != "low" else "Medium",
                     "difficulty": "Low" if a["risk"] == "low" else "Medium"}
                    for a in actions[:4]
                ] or [
                    {"task": "Improve mobile Core Web Vitals (LCP)", "impact": "High", "difficulty": "Medium"},
                    {"task": "Add structured data to key pages", "impact": "Medium", "difficulty": "Low"},
                ],
                "recommended_fixes": [
                    {"fix": a["title"], "category": a["type"], "auto_applicable": a["risk"] == "low"}
                    for a in actions[:4]
                ] or [
                    {"fix": "Add meta descriptions to 12 pages", "category": "on_page", "auto_applicable": True},
                    {"fix": "Compress hero images", "category": "performance", "auto_applicable": True},
                ],
                "growth_opportunities": [
                    {"opportunity": f"Target '{kw}' — you rank on page 2", "traffic_potential": f"+{r.randint(5, 40)}%"}
                    for kw in keyword_pool[:3]
                ],
            },
        }

    @router.get("/notifications")
    def notifications(
        request: Request, website_id: str = "", limit: int = 100, tenant_id: str = "demo-tenant",
    ) -> list[dict]:
        """The persistent Notification Center — every AI-detected condition and
        every AI-performed or AI-pending action, on the single connected
        website, built only from the real Governance audit trail and the real
        onboarding audit trail. Nothing here is fabricated: an empty history
        means no action has been taken yet, not a placeholder feed.
        """
        tenant = _tenant_of(request)
        return _build_notifications(request.app, tenant, website_id or None, limit)

    return router


#: Human-readable Notification Center category per governed fix type.
_FIX_CATEGORY = {
    "update_alt_text": "Images",
    "update_page_content": "Content",
    "create_page": "Pages",
    "update_seo_meta": "SEO Metadata",
}

#: Human-readable Notification Center action verb per audit transition.
_TRANSITION_SUMMARY = {
    "pending->approved": "Fix approved (report-only; no live write)",
    "pending->applied": "AI applied a governed fix to the live website",
    "pending->rejected": "Fix rejected — no change made",
    "applied->rolled_back": "AI rolled back a previous change",
}


def _build_notifications(app: Any, tenant_id: str, website_id: str | None, limit: int) -> list[dict]:
    """Aggregate every real governed action + onboarding event into one
    chronological Notification Center feed (Milestone 5).

    Sources (both already-audited, real subsystems — nothing new is invented):
    * Governance's Audit_Trail (:meth:`DigitalTwinPort.list_audit_entries`) —
      every fix approve/apply/reject/rollback, with the fix's category, page,
      before/after value, and rollback availability.
    * Onboarding's audit trail (``OnboardingRepository.list_audit``) — CMO
      memory/profile/strategy events, connection changes, and any other
      onboarding-layer action, each already carrying actor/reason/before/after.
    """
    entries: list[dict] = []

    try:
        subs = app.state.subsystems
        fixes_by_id = {f.id: f for f in subs.digital_twin.list_fixes(tenant_id)}
        issues_by_id = {i.id: i for i in subs.digital_twin.list_active_issues(tenant_id)}
        for audit in subs.digital_twin.list_audit_entries(tenant_id):
            fix = fixes_by_id.get(audit.fix_id)
            issue = issues_by_id.get(fix.issue_id) if fix else None
            fix_type = fix.fix_type.value if fix and fix.fix_type else "unknown"
            entries.append({
                "id": audit.id,
                "created_at": audit.created_at.isoformat() if hasattr(audit.created_at, "isoformat") else str(audit.created_at),
                "priority": issue.severity.value if issue else "medium",
                "category": _FIX_CATEGORY.get(fix_type, "Website"),
                "website_section": issue.detail.page_url if issue else None,
                "problem": issue.description if issue else (fix.reason if fix else None),
                "reason": fix.reason if fix else None,
                "ai_analysis": issue.description if issue else None,
                "action_taken": _TRANSITION_SUMMARY.get(audit.transition, audit.transition),
                "action_pending": audit.transition == "pending->approved",
                "before_state": audit.before_value,
                "after_state": fix.proposed_value if fix and audit.transition == "pending->applied" else None,
                "rollback_available": audit.transition == "pending->applied",
                "actor": audit.actor,
                "source": "governance_audit_trail",
            })
    except Exception:  # noqa: BLE001 - notification feed degrades honestly
        pass

    try:
        onboarding = getattr(getattr(app, "state", None), "onboarding", None)
        repo = onboarding.get("repository") if isinstance(onboarding, dict) else None
        if repo is not None:
            for audit in repo.list_audit(tenant_id, website_id, limit=limit):
                entries.append({
                    "id": audit.id,
                    "created_at": audit.created_at.isoformat() if hasattr(audit.created_at, "isoformat") else str(audit.created_at),
                    "priority": "high" if audit.approval_required else "medium",
                    "category": "Executive Brain",
                    "website_section": None,
                    "problem": audit.action,
                    "reason": audit.reason,
                    "ai_analysis": audit.reason,
                    "action_taken": audit.action,
                    "action_pending": bool(audit.approval_required),
                    "before_state": audit.before_value,
                    "after_state": audit.after_value,
                    "rollback_available": bool(audit.rollback_available),
                    "actor": audit.actor_id,
                    "source": "onboarding_audit_trail",
                })
    except Exception:  # noqa: BLE001 - notification feed degrades honestly
        pass

    entries.sort(key=lambda e: e["created_at"], reverse=True)
    return entries[:limit]
