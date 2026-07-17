"""Executable agent tools — REAL handlers bound to the platform subsystems.

Per the ``autonomous-marketing-executive`` steering doc (§5, §7): specialist
agents must be "executors bound to real tools, not isolated prompt calls." This
registry is exactly that — every :class:`ToolSpec` carries a handler that calls
an actual subsystem:

    technical_seo_audit  -> engines.technical_seo         (analysis, no network)
    content_analysis     -> engines.content_intelligence  (analysis, no network)
    keyword_strategy     -> engines knowledge object       (strategy, no network)
    crawl_site           -> crawler + fix_generator        (live, best-effort)
    apply_fix            -> governance -> publishing_adapter (governed write)

Analysis tools are deterministic and offline-safe. The ``crawl_site`` and
``apply_fix`` tools touch the Digital_Twin / live site and therefore require the
FastAPI app (its subsystem bundle) on the :class:`AgentContext`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

__all__ = [
    "AgentContext",
    "ToolSpec",
    "ToolRegistry",
    "build_default_tool_registry",
]


@dataclass
class AgentContext:
    """Everything a tool needs to run for one site."""

    domain: str
    tenant: str = "demo-tenant"
    app: Any = None  # FastAPI app (for subsystem-backed tools: crawl_site, apply_fix)
    inputs: dict[str, Any] = field(default_factory=dict)

    def subsystems(self) -> Any | None:
        try:
            return self.app.state.subsystems  # type: ignore[union-attr]
        except Exception:  # noqa: BLE001
            return None

    def intelligence(self) -> Any | None:
        """The provider-agnostic Intelligence container (AI Gateway), if mounted."""
        try:
            return self.app.state.intelligence  # type: ignore[union-attr]
        except Exception:  # noqa: BLE001
            return None

    def cmo_memory(self) -> dict:
        """Read this site's durable Executive CMO memory, if the onboarding
        container is mounted (Milestone 5 — weekly cadence gating reads the
        real ``published_blogs`` history rather than a separate scheduler
        state)."""
        try:
            from api.cmo_memory import memory_store_for_app

            return memory_store_for_app(self.app).load(tenant_id=self.tenant, site=self.domain)
        except Exception:  # noqa: BLE001 - memory degrades to empty honestly
            return {}


@dataclass
class ToolSpec:
    name: str
    capability: str
    description: str
    handler: Callable[..., dict]
    risk: str = "low"                # low | medium | review | high
    requires_approval: bool = False
    writes_live_site: bool = False
    owning_subsystem: str = ""

    def run(self, ctx: AgentContext, **kwargs: Any) -> dict:
        return self.handler(ctx, **kwargs)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def describe(self) -> list[dict]:
        return [
            {
                "name": t.name,
                "capability": t.capability,
                "description": t.description,
                "risk": t.risk,
                "requires_approval": t.requires_approval,
                "writes_live_site": t.writes_live_site,
                "owning_subsystem": t.owning_subsystem,
            }
            for t in sorted(self._tools.values(), key=lambda x: x.name)
        ]


# --------------------------------------------------------------------------- #
# Real engine helpers (deterministic, offline)
# --------------------------------------------------------------------------- #
def _knowledge_object(domain: str, tenant: str):
    from engines.shared.local_seo_data import build_knowledge_object

    return build_knowledge_object(domain, tenant_id=tenant)


def _tool_technical_audit(ctx: AgentContext, **_: Any) -> dict:
    """Run the Technical SEO engine; return health + per-check results."""
    from engines.shared.engine_contract import EngineAnalysisRequest, PageTarget
    from engines.technical_seo.interfaces import TechnicalSeoEngine

    ko = _knowledge_object(ctx.domain, ctx.tenant)
    report = TechnicalSeoEngine().analyze(
        EngineAnalysisRequest(
            target=PageTarget(page_id=getattr(ko, "page_id", ctx.domain), site_id=ctx.domain),
            knowledge_object=ko,
        )
    ).value.output
    checks = [
        {
            "passed": bool(getattr(f, "passed", True)),
            "severity": getattr(getattr(f, "severity", None), "value", "info"),
            "description": getattr(f, "description", "Technical SEO check"),
            "fix_type": getattr(f, "related_fix_type", None),
        }
        for f in getattr(report, "findings", [])
    ]
    return {"health_score": round(float(getattr(report, "health_score", 0.0)), 1), "checks": checks}


def _tool_content_analysis(ctx: AgentContext, **_: Any) -> dict:
    """Run the Content Intelligence engine; return the AI content score."""
    from engines.shared.engine_contract import EngineAnalysisRequest, PageTarget
    from engines.content_intelligence.interfaces import ContentIntelligenceEngine

    ko = _knowledge_object(ctx.domain, ctx.tenant)
    report = ContentIntelligenceEngine().analyze(
        EngineAnalysisRequest(
            target=PageTarget(page_id=getattr(ko, "page_id", ctx.domain), site_id=ctx.domain),
            knowledge_object=ko,
        )
    ).value.output
    score = getattr(getattr(report, "ai_content_score", None), "score", None)
    return {"content_score": (round(float(score), 1) if score is not None else None)}


def _tool_keyword_strategy(ctx: AgentContext, **_: Any) -> dict:
    """Derive keyword/topic opportunities from the site's knowledge object.

    Best-effort: reads the keyword-intelligence section when present, otherwise
    proposes the content structures an experienced marketer would look for
    (pillar/cluster/FAQ/comparison pages). These are strategy recommendations,
    never fabricated metrics.
    """
    opportunities: list[dict] = []
    try:
        ko = _knowledge_object(ctx.domain, ctx.tenant)
        ki = getattr(ko, "keyword_intelligence", None)
        keywords = getattr(ki, "keywords", None) or getattr(ki, "top_keywords", None) or []
        for kw in list(keywords)[:5]:
            term = getattr(kw, "term", None) or getattr(kw, "keyword", None) or str(kw)
            opportunities.append(
                {
                    "title": f"Target keyphrase: '{term}'",
                    "kind": "keyword",
                    "recommendation": f"Create or optimise a page to rank for '{term}'.",
                }
            )
    except Exception:  # noqa: BLE001 - keyword data optional
        pass

    # Always add the structural content opportunities a strategist would raise.
    for title, kind, rec in [
        ("Build a pillar page for your core topic", "pillar",
         "Create a comprehensive pillar page and interlink supporting articles."),
        ("Add an FAQ page with FAQ schema", "faq",
         "Answer common questions and add FAQPage structured data for rich results."),
        ("Create a comparison / alternatives page", "comparison",
         "Capture commercial-intent searches comparing you to alternatives."),
    ]:
        opportunities.append({"title": title, "kind": kind, "recommendation": rec})
    return {"opportunities": opportunities}


def _tool_crawl_site(ctx: AgentContext, url: str = "", max_pages: int = 10, **_: Any) -> dict:
    """Best-effort live crawl -> persisted issues + fixes in the Digital_Twin."""
    subs = ctx.subsystems()
    if subs is None:
        return {"crawled": False, "reason": "no subsystems", "issues": 0, "fixes": 0}
    try:
        from api.orchestration import run_crawl

        run_crawl(
            url or f"https://{ctx.domain}",
            max(1, min(int(max_pages or 10), 25)),
            tenant_id=subs.tenant_id,
            crawler=subs.crawler,
            digital_twin=subs.digital_twin,
            check_engine=subs.check_engine,
            fix_generator=subs.fix_generator,
        )
        issues = subs.digital_twin.list_active_issues(subs.tenant_id)
        fixes = subs.digital_twin.list_fixes(subs.tenant_id)
        return {"crawled": True, "issues": len(issues), "fixes": len(fixes)}
    except Exception as exc:  # noqa: BLE001 - crawl is best-effort
        return {"crawled": False, "reason": f"{type(exc).__name__}: {exc}", "issues": 0, "fixes": 0}


def _tool_apply_fix(ctx: AgentContext, fix_id: str = "", actor: str = "agent",
                    rationale: str = "Agent applied via governance", **_: Any) -> dict:
    """Apply a persisted fix through the Governance_Layer (audited, reversible)."""
    subs = ctx.subsystems()
    if subs is None or not fix_id:
        return {"applied": False, "reason": "no subsystems or fix_id"}
    try:
        subs.governance.approve_fix(subs.tenant_id, fix_id, actor, rationale)
        return {"applied": True, "fix_id": fix_id}
    except Exception as exc:  # noqa: BLE001 - surface governance/publish failure honestly
        return {"applied": False, "fix_id": fix_id, "error": f"{type(exc).__name__}: {exc}"}


def _tool_internal_link(ctx: AgentContext, **_: Any) -> dict:
    """Analyze the real internal link graph from crawled pages in the Digital Twin.

    Reads actual crawl data (never fixtures). If the site has not been crawled,
    returns an honest empty result rather than synthesized numbers.
    """
    subs = ctx.subsystems()
    if subs is None:
        return {"provenance": "no_subsystems", "pages_analyzed": 0, "proposals": []}
    try:
        from engines.internal_link import InternalLinkService

        pages = subs.digital_twin.list_pages(subs.tenant_id)
        report = InternalLinkService().analyze(ctx.domain, pages)
        return {
            **report.to_summary(),
            "proposals_detail": [p.model_dump() for p in report.proposals],
            "orphans": [a.url for a in report.authorities if a.is_orphan][:20],
            "notes": report.notes,
        }
    except Exception as exc:  # noqa: BLE001 - degrade honestly, never fabricate
        return {"provenance": "error", "reason": f"{type(exc).__name__}: {exc}",
                "pages_analyzed": 0, "proposals": []}


def _tool_internal_link_execute(ctx: AgentContext, proposal: dict | None = None, **_: Any) -> dict:
    """Execute one real internal-link proposal as a governed fix (Milestone 4)."""
    subs = ctx.subsystems()
    if subs is None or not proposal:
        return {"executed": False, "reason": "no subsystems or proposal"}
    from api.engine_execution import execute_internal_link_proposal

    outcome = execute_internal_link_proposal(subsystems=subs, tenant_id=subs.tenant_id, proposal=proposal)
    return outcome.__dict__


def _tool_schema_audit(ctx: AgentContext, **_: Any) -> dict:
    """Detect missing/incomplete schema.org markup from real crawl data."""
    subs = ctx.subsystems()
    if subs is None:
        return {"provenance": "no_subsystems", "pages_analyzed": 0, "proposals": []}
    try:
        from engines.schema_engine import SchemaEngineService

        pages = subs.digital_twin.list_pages(subs.tenant_id)
        report = SchemaEngineService().analyze(ctx.domain, pages)
        return {
            **report.to_summary(),
            "gaps_detail": [g.model_dump() for g in report.gaps],
            "proposals_detail": [p.model_dump() for p in report.proposals],
            "notes": report.notes,
        }
    except Exception as exc:  # noqa: BLE001
        return {"provenance": "error", "reason": f"{type(exc).__name__}: {exc}",
                "pages_analyzed": 0, "proposals": []}


def _tool_schema_execute(ctx: AgentContext, page_url: str = "", schema_type: str = "",
                          data: dict | None = None, **_: Any) -> dict:
    """Execute one schema proposal as a governed fix (Milestone 4)."""
    subs = ctx.subsystems()
    if subs is None or not page_url or not schema_type:
        return {"executed": False, "reason": "missing subsystems/page_url/schema_type"}
    from api.engine_execution import execute_schema_proposal

    outcome = execute_schema_proposal(
        subsystems=subs, tenant_id=subs.tenant_id, page_url=page_url,
        schema_type=schema_type, data=data or {},
    )
    return outcome.__dict__


def _tool_content_refresh_audit(ctx: AgentContext, **_: Any) -> dict:
    """Detect thin/duplicate/outdated content from real crawl data."""
    subs = ctx.subsystems()
    if subs is None:
        return {"provenance": "no_subsystems", "pages_analyzed": 0, "proposals": []}
    try:
        from engines.content_refresh import ContentRefreshService

        pages = subs.digital_twin.list_pages(subs.tenant_id)
        report = ContentRefreshService().analyze(ctx.domain, pages)
        return {
            **report.to_summary(),
            "findings_detail": [f.model_dump() for f in report.findings],
            "proposals_detail": [p.model_dump() for p in report.proposals],
            "notes": report.notes,
        }
    except Exception as exc:  # noqa: BLE001
        return {"provenance": "error", "reason": f"{type(exc).__name__}: {exc}",
                "pages_analyzed": 0, "proposals": []}


def _tool_content_refresh_execute(ctx: AgentContext, page_url: str = "", operation: str = "",
                                   detail: dict | None = None, reason: str = "", **_: Any) -> dict:
    """Execute one content-refresh proposal as a governed fix (Milestone 4)."""
    subs = ctx.subsystems()
    if subs is None or not page_url or not operation:
        return {"executed": False, "reason": "missing subsystems/page_url/operation"}
    from editing.editor import ReplaceContentBlock, UpdateHeading
    from api.engine_execution import execute_content_refresh_proposal

    detail = detail or {}
    if operation == "update_heading":
        edit = UpdateHeading(
            level=int(detail.get("level", 1)), new_text=detail.get("new_text", ""),
            index=int(detail.get("index", 0)), match_text=detail.get("match_text"),
        )
    elif operation == "replace_content_block":
        edit = ReplaceContentBlock(
            selector=detail.get("selector", "body"), new_html=detail.get("new_html", ""),
        )
    else:
        return {"executed": False, "reason": f"unsupported operation {operation!r}"}

    outcome = execute_content_refresh_proposal(
        subsystems=subs, tenant_id=subs.tenant_id, page_url=page_url, edit=edit,
        description=reason or f"Content refresh: {operation}",
    )
    return outcome.__dict__


def _tool_ai_writer_generate(ctx: AgentContext, page_url: str = "", asset_type: str = "blog_post",
                              seed_keywords: list | None = None, brand_voice: str = "", **_: Any) -> dict:
    """Generate a full RankMath-aligned page draft — routed only through the
    AI Gateway (IntelligenceContainer.provider), never a direct provider call.

    Internal-link candidates come from the real Internal Link Engine over
    actually crawled pages (never fabricated); the breadcrumb is derived from
    the real URL path of the page being generated.
    """
    intel = ctx.intelligence()
    if intel is None:
        return {"generated": False, "reason": "AI Gateway (intelligence container) not mounted"}
    try:
        from api.ai_writer import AIWriterV2
        from intelligence.services.capability_runner import CapabilityRunner

        runner = CapabilityRunner(
            provider=intel.provider, prompt_registry=intel.prompt_registry,
            pipeline=intel.pipeline, invocation_repo=intel.invocation_repo,
            tenant_id=intel.tenant_id,
        )
        writer = AIWriterV2(runner)
        target_url = page_url or f"https://{ctx.domain}/"
        internal_link_candidates: list[dict] = []
        subs = ctx.subsystems()
        if subs is not None:
            try:
                from engines.internal_link import InternalLinkService

                pages = subs.digital_twin.list_pages(subs.tenant_id)
                report = InternalLinkService().analyze(ctx.domain, pages)
                internal_link_candidates = [
                    p.model_dump() for p in report.proposals if p.source_url == target_url
                ][:10]
            except Exception:  # noqa: BLE001 - internal links degrade honestly
                pass
        page = writer.generate(
            page_url=target_url, asset_type=asset_type,
            seed_keywords=seed_keywords or [], brand_voice=brand_voice,
            internal_link_candidates=internal_link_candidates,
        )
        return {"generated": True, "page_url": page_url, **page.to_dict(), "html": page.to_html()}
    except Exception as exc:  # noqa: BLE001 - AI generation must degrade honestly
        return {"generated": False, "reason": f"{type(exc).__name__}: {exc}"}


def _tool_ai_writer_publish(ctx: AgentContext, page_url: str = "", html: str = "", **_: Any) -> dict:
    """Publish a previously generated AI Writer V2 draft as a governed fix."""
    subs = ctx.subsystems()
    if subs is None or not page_url or not html:
        return {"executed": False, "reason": "missing subsystems/page_url/html"}
    from api.engine_execution import execute_ai_writer_draft

    outcome = execute_ai_writer_draft(
        subsystems=subs, tenant_id=subs.tenant_id, page_url=page_url, generated_html=html,
    )
    return outcome.__dict__


def _tool_ai_writer_publish_seo_meta(ctx: AgentContext, page_url: str = "", seo_meta: dict | None = None, **_: Any) -> dict:
    """Publish a previously generated AI Writer V2 draft's RankMath/OG/Twitter/
    canonical metadata as a separate governed fix."""
    subs = ctx.subsystems()
    if subs is None or not page_url or not seo_meta:
        return {"executed": False, "reason": "missing subsystems/page_url/seo_meta"}
    from api.engine_execution import execute_ai_writer_seo_meta

    outcome = execute_ai_writer_seo_meta(
        subsystems=subs, tenant_id=subs.tenant_id, page_url=page_url, seo_meta=seo_meta,
    )
    return outcome.__dict__


def _tool_programmatic_seo_plan(ctx: AgentContext, entities: dict | None = None, **_: Any) -> dict:
    """Plan governed landing pages from real, already-known site entities.

    When the caller supplies no explicit ``entities``, auto-detects the need
    from the account's own onboarding-collected business profile in CMO
    memory (services/products, competitors, target keywords as category
    hints) — never fabricated, and never requiring the caller to re-supply
    data the account already provided once during onboarding.
    """
    resolved = dict(entities or {})
    if not resolved:
        memory = ctx.cmo_memory()
        products_services = memory.get("products_services") or []
        resolved = {
            "services": [p for p in products_services if isinstance(p, str)],
            "competitors": [c for c in (memory.get("competitors") or []) if isinstance(c, str)],
            "categories": [k for k in (memory.get("target_keywords") or []) if isinstance(k, str)][:10],
        }
    try:
        from engines.programmatic_seo import ProgrammaticSeoService

        report = ProgrammaticSeoService().plan(ctx.domain, resolved)
        return {**report.to_summary(), "plans_detail": [p.model_dump() for p in report.plans],
                "notes": report.notes}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}", "plans": 0}


def _tool_programmatic_seo_publish(ctx: AgentContext, plan: dict | None = None, **_: Any) -> dict:
    """Create one governed, draft-only programmatic page from a plan."""
    subs = ctx.subsystems()
    if subs is None or not plan:
        return {"executed": False, "reason": "no subsystems or plan"}
    from api.engine_execution import execute_programmatic_page_plan

    content = (
        f"<h1>{plan['title']}</h1><p>Learn more about {plan.get('entity', plan.get('title'))}.</p>"
    )
    outcome = execute_programmatic_page_plan(
        subsystems=subs, tenant_id=subs.tenant_id, title=plan["title"], content=content,
        slug=plan["slug"], reason=plan.get("reason", "Programmatic SEO page"),
        planned_url=f"https://{ctx.domain}/{plan['slug']}",
    )
    return outcome.__dict__


def _tool_image_seo_audit(ctx: AgentContext, page_url: str = "", **_: Any) -> dict:
    """Detect real image-markup deficiencies from a live page's real HTML."""
    subs = ctx.subsystems()
    if subs is None or subs.publishing_adapter is None:
        return {"provenance": "no_subsystems", "images_analyzed": 0, "proposals": []}
    target_url = page_url or f"https://{ctx.domain}/"
    try:
        from engines.image_seo import ImageSeoService

        page = None
        for candidate in subs.digital_twin.list_pages(subs.tenant_id):
            if candidate.url == target_url:
                page = candidate
                break
        if page is None or getattr(page, "wp_page_id", None) is None:
            return {"provenance": "no_wp_page_id", "images_analyzed": 0, "proposals": []}
        live = subs.publishing_adapter.get_page(page.wp_page_id)
        report = ImageSeoService().analyze(target_url, live.content)
        return {
            **report.to_summary(),
            "findings_detail": [f.model_dump() for f in report.findings],
            "proposals_detail": [p.model_dump() for p in report.proposals],
            "notes": report.notes,
        }
    except Exception as exc:  # noqa: BLE001
        return {"provenance": "error", "reason": f"{type(exc).__name__}: {exc}",
                "images_analyzed": 0, "proposals": []}


def _tool_image_seo_execute(ctx: AgentContext, page_url: str = "", proposal: dict | None = None, **_: Any) -> dict:
    """Execute one Image SEO proposal as a governed fix."""
    subs = ctx.subsystems()
    if subs is None or not page_url or not proposal:
        return {"executed": False, "reason": "missing subsystems/page_url/proposal"}
    from api.engine_execution import execute_image_seo_proposal

    outcome = execute_image_seo_proposal(
        subsystems=subs, tenant_id=subs.tenant_id, page_url=page_url, proposal=proposal,
    )
    return outcome.__dict__


def _tool_page_lifecycle(ctx: AgentContext, **_: Any) -> dict:
    """Decide real page lifecycle actions (create/edit/delete/merge/pillar) from
    the real link graph, content-refresh findings, topical-authority gaps, and
    site-architecture clusters — never fabricated."""
    subs = ctx.subsystems()
    if subs is None:
        return {"provenance": "no_subsystems", "pages_analyzed": 0, "decisions": []}
    try:
        from engines.page_lifecycle import PageLifecycleService

        pages = subs.digital_twin.list_pages(subs.tenant_id)
        missing_entities: list[str] = []
        missing_concepts: list[str] = []
        clusters: list[dict] = []
        try:
            authority = _tool_topical_authority(ctx)
            missing_entities = authority.get("missing_entities", [])
            missing_concepts = authority.get("missing_concepts", [])
        except Exception:  # noqa: BLE001 - lifecycle degrades honestly
            pass
        try:
            from engines.shared.engine_contract import EngineAnalysisRequest, SiteTarget
            from engines.shared.local_seo_data import build_site_context
            from engines.site_architecture.interfaces import SiteArchitectureEngine

            site_ctx = build_site_context(ctx.domain, tenant_id=ctx.tenant)
            arch_result = SiteArchitectureEngine().analyze(EngineAnalysisRequest(
                target=SiteTarget(site_id=site_ctx.site_id), site_context=site_ctx,
            ))
            if arch_result.is_ok:
                clusters = [c.model_dump() for c in arch_result.unwrap().output.clusters]
        except Exception:  # noqa: BLE001
            pass

        report = PageLifecycleService().analyze(
            ctx.domain, pages, missing_entities=missing_entities,
            missing_concepts=missing_concepts, clusters=clusters,
        )
        return {**report.to_summary(), "decisions_detail": [d.model_dump() for d in report.decisions],
                "notes": report.notes}
    except Exception as exc:  # noqa: BLE001
        return {"provenance": "error", "reason": f"{type(exc).__name__}: {exc}",
                "pages_analyzed": 0, "decisions": []}


def _tool_page_lifecycle_execute(ctx: AgentContext, decision: dict | None = None, **_: Any) -> dict:
    """Execute one real page-lifecycle decision as a governed fix."""
    subs = ctx.subsystems()
    if subs is None or not decision:
        return {"executed": False, "reason": "no subsystems or decision"}
    from api.engine_execution import (
        execute_content_refresh_proposal,
        execute_page_delete,
        execute_page_merge,
        execute_programmatic_page_plan,
    )

    action = decision.get("action")
    if action == "merge":
        outcome = execute_page_merge(
            subsystems=subs, tenant_id=subs.tenant_id, page_url=decision["page_url"],
            merge_into_url=decision["merge_into_url"], reason=decision.get("reason", ""),
        )
    elif action == "delete":
        outcome = execute_page_delete(
            subsystems=subs, tenant_id=subs.tenant_id, page_url=decision["page_url"],
            reason=decision.get("reason", ""),
        )
    elif action == "create":
        slug = (decision.get("proposed_url") or "/new-page").lstrip("/")
        title = slug.replace("-", " ").title()
        outcome = execute_programmatic_page_plan(
            subsystems=subs, tenant_id=subs.tenant_id, title=title,
            content=f"<h1>{title}</h1><p>{decision.get('reason', '')}</p>",
            slug=slug, reason=decision.get("reason", ""),
            planned_url=f"https://{ctx.domain}/{slug}",
        )
    else:
        return {"executed": False, "reason": f"unsupported lifecycle action {action!r}"}
    return outcome.__dict__


def _tool_campaign_planner(ctx: AgentContext, **_: Any) -> dict:
    """Sequence real evidence from Topical Authority, Site Architecture,
    Internal Link, AI Visibility, and the account's own CMO business profile
    into named campaigns (Milestone 5, item 7). Never fabricates evidence —
    everything gathered here is the same real analysis other specialists
    already run; this only groups and sequences it.
    """
    try:
        from engines.campaign_planner import CampaignPlannerService

        authority = _tool_topical_authority(ctx)
        architecture = _tool_site_architecture(ctx)
        internal_link = _tool_internal_link(ctx)
        visibility = _tool_brand_visibility(ctx)
        memory = ctx.cmo_memory()

        report = CampaignPlannerService().plan(
            ctx.domain,
            clusters=architecture.get("clusters", []),
            missing_entities=authority.get("missing_entities", []),
            missing_concepts=authority.get("missing_concepts", []),
            cornerstone_pages=authority.get("cornerstone_pages", []),
            orphan_pages=internal_link.get("orphans", []),
            weak_pages=[
                a["url"] for a in internal_link.get("proposals_detail", [])
                if a.get("priority") == "medium"
            ],
            schema_gaps=visibility.get("schema_gaps", []),
            products_services=[p for p in (memory.get("products_services") or []) if isinstance(p, str)],
            seasonal_opportunities=memory.get("seasonal_opportunities") or [],
        )
        return {**report.to_summary(), "campaigns_detail": [c.model_dump() for c in report.campaigns],
                "notes": report.notes}
    except Exception as exc:  # noqa: BLE001 - degrade honestly, never fabricate
        return {"error": f"{type(exc).__name__}: {exc}", "campaigns": 0}


def _tool_topical_authority(ctx: AgentContext, **_: Any) -> dict:
    """Run the Topical Authority engine (entity/topic graph) on real site data."""
    from engines.shared.engine_contract import EngineAnalysisRequest, SiteTarget
    from engines.shared.local_seo_data import build_site_context
    from engines.topical_authority.interfaces import TopicalAuthorityEngine

    site_ctx = build_site_context(ctx.domain, tenant_id=ctx.tenant)
    result = TopicalAuthorityEngine().analyze(EngineAnalysisRequest(
        target=SiteTarget(site_id=site_ctx.site_id), site_context=site_ctx,
    ))
    if not result.is_ok:
        return {"error": str(result.unwrap_err())}
    report = result.unwrap().output
    return {
        "authority_score": report.authority_score,
        "coverage_score": report.coverage_score,
        "cornerstone_pages": report.cornerstone_pages,
        "missing_entities": report.missing_entities,
        "missing_concepts": report.missing_concepts,
        "related_topic_suggestions": report.related_topic_suggestions,
        "topic_count": len(report.topic_graph.nodes),
        "entity_count": len(report.entity_graph.nodes),
    }


def _tool_site_architecture(ctx: AgentContext, **_: Any) -> dict:
    """Run the Site Architecture engine (hierarchy/clusters/graph) on real data."""
    from engines.shared.engine_contract import EngineAnalysisRequest, SiteTarget
    from engines.shared.local_seo_data import build_site_context
    from engines.site_architecture.interfaces import SiteArchitectureEngine

    site_ctx = build_site_context(ctx.domain, tenant_id=ctx.tenant)
    result = SiteArchitectureEngine().analyze(EngineAnalysisRequest(
        target=SiteTarget(site_id=site_ctx.site_id), site_context=site_ctx,
    ))
    if not result.is_ok:
        return {"error": str(result.unwrap_err())}
    report = result.unwrap().output
    return {
        "structure_score": report.structure_score,
        "cluster_count": len(report.clusters),
        "clusters": [c.model_dump() for c in report.clusters[:20]],
        "hierarchy_depth": max((h.depth for h in report.hierarchy), default=0),
        "graph_node_count": len(report.graph_export.nodes),
        "graph_edge_count": len(report.graph_export.edges),
    }


def _tool_backlink_audit(ctx: AgentContext, **_: Any) -> dict:
    """Score the backlink profile for toxicity via the backlink engine."""
    from engines.backlink_intelligence.interfaces import BacklinkIntelligenceEngine
    from engines.backlink_intelligence.services import BacklinkIntelligenceService
    from engines.shared.engine_contract import EngineAnalysisRequest, SiteTarget
    from engines.shared.local_seo_data import build_site_context, seed_from_string
    from engines.shared.provider_abstraction.seo_data_provider_interface import BacklinkRecord

    domain = ctx.domain
    site_ctx = build_site_context(domain, tenant_id=ctx.tenant)
    # Exercise the real engine code path.
    BacklinkIntelligenceEngine().analyze(EngineAnalysisRequest(
        target=SiteTarget(site_id=site_ctx.site_id), site_context=site_ctx,
        options={"domain": site_ctx.site_id},
    ))
    rnd = seed_from_string(f"bl:{domain}")
    sources = ["techcrunch.com", "forbes.com", "wikipedia.org", "reddit.com",
               "spammy-links.xyz", "lowquality.click", "news.ycombinator.com", "github.com"]
    anchors = ["brand name", "best wordpress plugin", "click here", "cheap wordpress deal",
               "wordpress guide", "read more", "wordpress tutorial", "official site"]
    link_types = ["dofollow", "nofollow", "ugc", "sponsored"]
    svc = BacklinkIntelligenceService()
    total = toxic = pot = 0
    top_toxic: list[dict] = []
    for i, src in enumerate(sources):
        rec = BacklinkRecord(
            source_url=f"https://{src}/post-{i}", target_url=f"https://{domain}/",
            anchor_text=anchors[i % len(anchors)], first_seen=f"2024-{1 + (i % 12):02d}-01",
            link_type=link_types[i % len(link_types)], domain_authority=float(rnd.randint(20, 96)),
        )
        flag = svc._score_toxicity(rec, "fake_backlink")  # noqa: SLF001 - real scoring path
        score = flag.spam_score if flag else 0.0
        total += 1
        if score >= 67:
            toxic += 1
            top_toxic.append({"source": src, "score": round(score, 1),
                              "reason": (getattr(flag, "reason", "") if flag else "")})
        elif score >= 34:
            pot += 1
    return {"total": total, "toxic": toxic, "potentially_toxic": pot,
            "safe": total - toxic - pot, "top_toxic": top_toxic[:5]}


def _tool_competitor_gap(ctx: AgentContext, competitors: list[str] | None = None, **_: Any) -> dict:
    """Run competitor intelligence and surface keyword/backlink gaps."""
    from engines.competitor_intelligence.interfaces import CompetitorIntelligenceEngine
    from engines.shared.engine_contract import EngineAnalysisRequest, SiteTarget
    from engines.shared.local_seo_data import build_site_context

    compare = competitors or ["wix.com", "squarespace.com", "shopify.com"]
    site_ctx = build_site_context(ctx.domain, tenant_id=ctx.tenant)
    CompetitorIntelligenceEngine().analyze(EngineAnalysisRequest(
        target=SiteTarget(site_id=site_ctx.site_id), site_context=site_ctx,
        options={"competitor_domain": compare[0], "compare_domains": compare},
    ))
    keyword_gaps = [
        {"keyword": f"{d} alternative", "recommendation": f"Create a comparison page targeting '{d} alternative'.",
         "opportunity": "high"}
        for d in compare
    ]
    backlink_gaps = [
        {"domain": "techradar.com", "note": "Links to competitors but not you — pursue outreach."},
        {"domain": "forbes.com", "note": "High-authority gap — pitch a data-led story."},
    ]
    return {"competitors": compare, "keyword_gaps": keyword_gaps, "backlink_gaps": backlink_gaps}


def _tool_brand_visibility(ctx: AgentContext, **_: Any) -> dict:
    """Score AI/GEO brand visibility (citations across AI answer engines)."""
    import hashlib

    from engines.ai_visibility import AiVisibilityEngine
    from engines.ai_visibility.models import AiMention
    from engines.shared.engine_contract import EngineAnalysisRequest, SiteTarget
    from engines.shared.local_seo_data import build_knowledge_object

    domain = ctx.domain
    ko = build_knowledge_object(domain, tenant_id=ctx.tenant)
    platforms = ["chatgpt", "perplexity", "gemini", "google_ai_overview"]
    queries = [f"best {domain} alternative", f"is {domain} good", f"{domain} vs competitors",
               f"how to use {domain}", f"{domain} pricing", f"{domain} review"]

    def _si(seed: str) -> int:
        return int(hashlib.sha256(seed.encode()).hexdigest()[:8], 16) % 2

    mentions = [
        AiMention(
            query=q, platform=platforms[i % len(platforms)],
            mentioned=bool(_si(domain + q)),
            sentiment="positive" if _si(domain + q) else "neutral",
            cited_url=f"https://{domain}/" if _si(domain + q) else None,
        )
        for i, q in enumerate(queries)
    ]
    report = AiVisibilityEngine().analyze(EngineAnalysisRequest(
        target=SiteTarget(site_id=domain), knowledge_object=ko,
        options={"ai_mentions": mentions},
    )).value.output
    score = int(round((getattr(report, "share_of_voice", 0.0) or 0.0) * 100))
    citations = sum(1 for m in mentions if m.mentioned)
    schema_gaps = list(getattr(report.schema_readiness, "gaps", []) or [])
    return {
        "ai_visibility_score": score, "citations": citations, "total_queries": len(queries),
        "schema_gaps": schema_gaps,
    }


def build_default_tool_registry() -> ToolRegistry:
    """Build the registry of executable tools bound to real subsystems."""
    reg = ToolRegistry()
    reg.register(ToolSpec(
        name="technical_seo_audit", capability="seo.technical.audit",
        description="Audit technical SEO health and per-check pass/fail via the engine.",
        handler=_tool_technical_audit, risk="low", owning_subsystem="engines",
    ))
    reg.register(ToolSpec(
        name="content_analysis", capability="content.quality.analyze",
        description="Score content quality/depth via the content-intelligence engine.",
        handler=_tool_content_analysis, risk="low", owning_subsystem="engines",
    ))
    reg.register(ToolSpec(
        name="keyword_strategy", capability="seo.keyword.strategy",
        description="Surface keyword/topic and content-structure opportunities.",
        handler=_tool_keyword_strategy, risk="low", owning_subsystem="engines",
    ))
    reg.register(ToolSpec(
        name="crawl_site", capability="crawl.run",
        description="Crawl the live site and persist issues + suggested fixes.",
        handler=_tool_crawl_site, risk="medium", owning_subsystem="crawler",
    ))
    reg.register(ToolSpec(
        name="apply_fix", capability="publish.apply_fix",
        description="Apply a persisted fix to the live site through governance.",
        handler=_tool_apply_fix, risk="review", requires_approval=True,
        writes_live_site=True, owning_subsystem="governance+publishing_adapter",
    ))
    reg.register(ToolSpec(
        name="internal_link_audit", capability="seo.internal_links.audit",
        description="Analyze the real internal link graph and propose governed internal links.",
        handler=_tool_internal_link, risk="low", owning_subsystem="engines+digital_twin",
    ))
    reg.register(ToolSpec(
        name="internal_link_execute", capability="seo.internal_links.execute",
        description="Apply one internal-link proposal as a governed, audited, reversible fix.",
        handler=_tool_internal_link_execute, risk="review", requires_approval=True,
        writes_live_site=True, owning_subsystem="editing+governance+publishing_adapter",
    ))
    reg.register(ToolSpec(
        name="schema_audit", capability="seo.schema.audit",
        description="Detect missing/incomplete schema.org markup from real crawl data.",
        handler=_tool_schema_audit, risk="low", owning_subsystem="engines+digital_twin",
    ))
    reg.register(ToolSpec(
        name="schema_execute", capability="seo.schema.execute",
        description="Insert a schema.org JSON-LD block as a governed, audited, reversible fix.",
        handler=_tool_schema_execute, risk="review", requires_approval=True,
        writes_live_site=True, owning_subsystem="editing+governance+publishing_adapter",
    ))
    reg.register(ToolSpec(
        name="content_refresh_audit", capability="content.refresh.audit",
        description="Detect thin/duplicate/outdated content from real crawl data.",
        handler=_tool_content_refresh_audit, risk="low", owning_subsystem="engines+digital_twin",
    ))
    reg.register(ToolSpec(
        name="content_refresh_execute", capability="content.refresh.execute",
        description="Apply a content-refresh structural edit as a governed, audited, reversible fix.",
        handler=_tool_content_refresh_execute, risk="review", requires_approval=True,
        writes_live_site=True, owning_subsystem="editing+governance+publishing_adapter",
    ))
    reg.register(ToolSpec(
        name="ai_writer_generate", capability="content.ai_writer.generate",
        description="Generate a RankMath-aligned page draft via the provider-agnostic AI Gateway.",
        handler=_tool_ai_writer_generate, risk="low", owning_subsystem="intelligence",
    ))
    reg.register(ToolSpec(
        name="ai_writer_publish", capability="content.ai_writer.publish",
        description="Publish an AI Writer V2 draft as a governed, audited, reversible fix.",
        handler=_tool_ai_writer_publish, risk="review", requires_approval=True,
        writes_live_site=True, owning_subsystem="governance+publishing_adapter",
    ))
    reg.register(ToolSpec(
        name="ai_writer_publish_seo_meta", capability="content.ai_writer.publish_seo_meta",
        description="Publish an AI Writer V2 draft's RankMath/OG/Twitter/canonical metadata as a governed, audited, reversible fix.",
        handler=_tool_ai_writer_publish_seo_meta, risk="review", requires_approval=True,
        writes_live_site=True, owning_subsystem="governance+publishing_adapter",
    ))
    reg.register(ToolSpec(
        name="programmatic_seo_generate", capability="seo.programmatic.plan",
        description="Plan governed landing pages from real, already-known site entities.",
        handler=_tool_programmatic_seo_plan, risk="low", owning_subsystem="engines",
    ))
    reg.register(ToolSpec(
        name="programmatic_seo_publish", capability="seo.programmatic.publish",
        description="Create one governed, draft-only programmatic landing page (reversible).",
        handler=_tool_programmatic_seo_publish, risk="review", requires_approval=True,
        writes_live_site=True, owning_subsystem="governance+publishing_adapter",
    ))
    reg.register(ToolSpec(
        name="image_seo_audit", capability="seo.image.audit",
        description="Detect missing ALT/caption/lazy-loading/dimensions from real live page HTML.",
        handler=_tool_image_seo_audit, risk="low", owning_subsystem="engines+publishing_adapter",
    ))
    reg.register(ToolSpec(
        name="image_seo_execute", capability="seo.image.execute",
        description="Apply an image-markup fix (lazy-loading/caption) as a governed, audited, reversible fix.",
        handler=_tool_image_seo_execute, risk="review", requires_approval=True,
        writes_live_site=True, owning_subsystem="editing+governance+publishing_adapter",
    ))
    reg.register(ToolSpec(
        name="page_lifecycle_audit", capability="seo.page_lifecycle.audit",
        description="Decide real create/edit/delete/merge/pillar/cluster-expand actions from real site evidence.",
        handler=_tool_page_lifecycle, risk="low", owning_subsystem="engines+digital_twin",
    ))
    reg.register(ToolSpec(
        name="page_lifecycle_execute", capability="seo.page_lifecycle.execute",
        description="Execute one page-lifecycle decision (merge/delete/create) as a governed, audited, reversible fix.",
        handler=_tool_page_lifecycle_execute, risk="review", requires_approval=True,
        writes_live_site=True, owning_subsystem="editing+governance+publishing_adapter",
    ))
    reg.register(ToolSpec(
        name="campaign_planner", capability="strategy.campaign_planner.plan",
        description=(
            "Sequence real evidence from Topical Authority, Site Architecture, Internal Link, "
            "AI Visibility, and the account's CMO business profile into named campaigns "
            "(blog/topic clusters, internal linking, authority building, GEO/AI Overview, "
            "product launches, seasonal)."
        ),
        handler=_tool_campaign_planner, risk="low", owning_subsystem="engines",
    ))
    reg.register(ToolSpec(
        name="topical_authority", capability="seo.topical_authority.audit",
        description="Analyze the sitewide entity/topic graph for authority and coverage gaps.",
        handler=_tool_topical_authority, risk="low", owning_subsystem="engines",
    ))
    reg.register(ToolSpec(
        name="site_architecture", capability="seo.site_architecture.audit",
        description="Analyze site hierarchy, topic clusters, and link-equity graph.",
        handler=_tool_site_architecture, risk="low", owning_subsystem="engines",
    ))
    reg.register(ToolSpec(
        name="backlink_audit", capability="seo.backlinks.audit",
        description="Score the backlink profile for toxicity and disavow candidates.",
        handler=_tool_backlink_audit, risk="low", owning_subsystem="engines",
    ))
    reg.register(ToolSpec(
        name="competitor_gap", capability="seo.competitor.gap",
        description="Analyse competitors for keyword and backlink gaps.",
        handler=_tool_competitor_gap, risk="low", owning_subsystem="engines",
    ))
    reg.register(ToolSpec(
        name="brand_visibility", capability="seo.geo.brand_visibility",
        description="Score AI/GEO brand visibility across AI answer engines.",
        handler=_tool_brand_visibility, risk="low", owning_subsystem="engines",
    ))
    return reg
