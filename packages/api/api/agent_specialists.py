"""Specialist agents — real executors bound to tools (not prompt-only stubs).

Each specialist runs one or more executable tools from :mod:`api.agent_tools`
against a site and emits (a) findings — observations — and (b) actions —
concrete, reviewable proposals. The Supervisor (see :mod:`api.agent_supervisor`)
runs the roster, posts results to a shared blackboard, and hands the aggregated
analysis to the governed reasoning loop.

Findings/actions use the same shape the loop and UI already consume, so this
layer upgrades the loop's ANALYZE phase from two direct engine calls to a
coordinated multi-agent analysis without changing anything downstream.
"""
from __future__ import annotations

import uuid
from typing import Any

from api.agent_tools import AgentContext, ToolRegistry

__all__ = [
    "Specialist",
    "TechnicalSeoAgent",
    "ContentStrategyAgent",
    "KeywordStrategyAgent",
    "WebsiteHealthAgent",
    "BacklinkAgent",
    "CompetitorIntelligenceAgent",
    "BrandVisibilityAgent",
    "SchemaAgent",
    "ContentRefreshAgent",
    "TopicalAuthorityAgent",
    "SiteArchitectureAgent",
    "AiWriterAgent",
    "ProgrammaticSeoAgent",
    "ImageSeoAgent",
    "PageLifecycleAgent",
    "CampaignPlannerAgent",
    "DEFAULT_ROSTER",
]


def _fid() -> str:
    return f"find_{uuid.uuid4().hex[:10]}"


def _aid() -> str:
    return f"act_{uuid.uuid4().hex[:10]}"


def _suggest_fix_text(fix_type: str | None, desc: str, domain: str) -> str:
    ft = (fix_type or "").lower()
    d = desc.lower()
    if "meta" in ft or "meta description" in d:
        return (f"Add a ~150-char meta description for {domain} that summarises the page value "
                "and leads with the primary keyphrase.")
    if "title" in ft or "title" in d:
        return f"Rewrite the <title> to a 55-60 char, keyword-led title for {domain}."
    if "alt" in ft or "alt text" in d:
        return "Generate descriptive alt text for each image describing its content and context."
    if "schema" in d:
        return "Add JSON-LD structured data (Article/FAQ/Breadcrumb) to improve rich results."
    if "canonical" in d:
        return "Add a self-referencing rel=canonical tag to consolidate ranking signals."
    if "h1" in d or "heading" in d:
        return "Add a single, descriptive H1 that states the page topic with the primary keyphrase."
    return "Apply the recommended technical SEO correction."


class Specialist:
    """Base class: a named role bound to tool(s) that produces a report."""

    name: str = "specialist"
    role: str = "Specialist"
    tools: tuple[str, ...] = ()

    def analyze(self, ctx: AgentContext, registry: ToolRegistry) -> dict:  # pragma: no cover - overridden
        raise NotImplementedError

    def _report(self, *, summary: str, findings: list[dict], actions: list[dict],
                meta: dict | None = None) -> dict:
        metadata = dict(meta or {})
        provenance = metadata.setdefault(
            "provenance",
            "simulated_fixture"
            if self.name in {"backlink", "competitor_intelligence", "brand_visibility"}
            else "deterministic_fixture",
        )
        for row in [*findings, *actions]:
            row.setdefault("provenance", provenance)
        return {
            "agent": self.name,
            "role": self.role,
            "tools_used": list(self.tools),
            "summary": summary,
            "findings": findings,
            "actions": actions,
            "meta": metadata,
        }


class TechnicalSeoAgent(Specialist):
    name = "technical_seo"
    role = "Technical SEO Agent"
    tools = ("technical_seo_audit",)

    def analyze(self, ctx: AgentContext, registry: ToolRegistry) -> dict:
        tool = registry.get("technical_seo_audit")
        result = tool.run(ctx) if tool else {"health_score": 0.0, "checks": []}
        health = result.get("health_score", 0.0)
        findings: list[dict] = []
        actions: list[dict] = []
        for c in result.get("checks", []):
            passed = bool(c.get("passed", True))
            sev = c.get("severity", "info")
            desc = c.get("description", "Technical SEO check")
            findings.append({
                "id": _fid(), "category": "technical_seo", "severity": sev,
                "title": desc, "passed": passed, "detail": desc,
            })
            if not passed:
                actions.append({
                    "id": _aid(), "type": c.get("fix_type") or "seo_improvement",
                    "title": desc, "description": f"Resolve: {desc}",
                    "target": ctx.domain, "before": "current state",
                    "after": _suggest_fix_text(c.get("fix_type"), desc, ctx.domain),
                    "risk": "low" if sev in ("low", "medium", "info") else "medium",
                    "severity": sev, "category": "technical_seo", "detail": desc,
                    "requires_approval": True, "status": "proposed", "fix_id": None,
                    "source": "technical_seo_agent",
                })
        issues = sum(1 for f in findings if not f["passed"])
        return self._report(
            summary=f"Technical health {health}/100 with {issues} issue(s) to resolve.",
            findings=findings, actions=actions, meta={"health_score": health},
        )


class ContentStrategyAgent(Specialist):
    name = "content_strategy"
    role = "Content Strategy Agent"
    tools = ("content_analysis",)

    def analyze(self, ctx: AgentContext, registry: ToolRegistry) -> dict:
        tool = registry.get("content_analysis")
        result = tool.run(ctx) if tool else {"content_score": None}
        score = result.get("content_score")
        findings: list[dict] = []
        actions: list[dict] = []
        if score is not None:
            findings.append({
                "id": _fid(), "category": "content", "severity": "info",
                "title": f"AI content quality score: {round(score)}/100",
                "passed": score >= 70,
                "detail": "Depth, readability and semantic coverage of the page content.",
            })
            if score < 80:
                for title, after in [
                    ("Expand thin content with depth and examples",
                     "Add sections, examples and data so the page fully answers the query intent."),
                    ("Improve readability and structure",
                     "Break up long paragraphs, add descriptive H2/H3s and lists for scannability."),
                    ("Refresh outdated statistics and add EEAT signals",
                     "Update stats/dates, add author bio and cite authoritative sources."),
                ]:
                    actions.append({
                        "id": _aid(), "type": "content_improvement", "title": title,
                        "description": title, "target": ctx.domain,
                        "before": "current content", "after": after,
                        "risk": "low", "severity": "medium", "category": "content",
                        "detail": title, "requires_approval": True, "status": "proposed",
                        "fix_id": None, "source": "content_strategy_agent",
                    })
        summary = (f"Content score {round(score)}/100 — {'strong' if score and score >= 80 else 'improvement opportunities identified'}."
                   if score is not None else "Content analysis unavailable.")
        return self._report(summary=summary, findings=findings, actions=actions,
                            meta={"content_score": score})


class KeywordStrategyAgent(Specialist):
    name = "keyword_strategy"
    role = "Keyword & Content Strategy Agent"
    tools = ("keyword_strategy",)

    def analyze(self, ctx: AgentContext, registry: ToolRegistry) -> dict:
        tool = registry.get("keyword_strategy")
        result = tool.run(ctx) if tool else {"opportunities": []}
        opps = result.get("opportunities", [])
        findings = [{
            "id": _fid(), "category": "strategy", "severity": "info",
            "title": f"{len(opps)} growth opportunity(ies) identified",
            "passed": True, "detail": "Keyword targeting and content-structure opportunities.",
        }]
        actions: list[dict] = []
        for o in opps:
            actions.append({
                "id": _aid(), "type": f"content_{o.get('kind', 'opportunity')}",
                "title": o.get("title", "Opportunity"),
                "description": o.get("recommendation", ""),
                "target": ctx.domain, "before": "not present",
                "after": o.get("recommendation", ""),
                "risk": "low", "severity": "medium", "category": "content",
                "detail": o.get("recommendation", ""), "requires_approval": True,
                "status": "proposed", "fix_id": None, "source": "keyword_strategy_agent",
            })
        return self._report(
            summary=f"Proposed {len(actions)} growth/content opportunity(ies).",
            findings=findings, actions=actions, meta={},
        )


class WebsiteHealthAgent(Specialist):
    name = "website_health"
    role = "Website Health Agent"
    tools = ("technical_seo_audit",)

    def analyze(self, ctx: AgentContext, registry: ToolRegistry) -> dict:
        tool = registry.get("technical_seo_audit")
        result = tool.run(ctx) if tool else {"health_score": 0.0, "checks": []}
        health = result.get("health_score", 0.0)
        band = ("excellent" if health >= 85 else "solid" if health >= 70
                else "at risk" if health >= 50 else "poor")
        findings = [{
            "id": _fid(), "category": "health", "severity": "info",
            "title": f"Overall website health is {band} ({health}/100)",
            "passed": health >= 70,
            "detail": "Synthesised from technical SEO signals across the site.",
        }]
        return self._report(
            summary=f"Website health: {band} ({health}/100).",
            findings=findings, actions=[], meta={"health_score": health, "band": band},
        )


class InternalLinkAgent(Specialist):
    name = "internal_link"
    role = "Internal Link Architect"
    tools = ("internal_link_audit",)

    def analyze(self, ctx: AgentContext, registry: ToolRegistry) -> dict:
        tool = registry.get("internal_link_audit")
        result = tool.run(ctx) if tool else {"pages_analyzed": 0, "proposals_detail": []}
        pages = result.get("pages_analyzed", 0)
        provenance = result.get("provenance", "no_data")
        proposals = result.get("proposals_detail", [])
        orphans = result.get("orphans", [])
        # Only real crawl data yields observed provenance; otherwise be explicit.
        observed = provenance == "observed_live_crawl"
        findings = [{
            "id": _fid(), "category": "internal_links",
            "severity": "high" if orphans else "medium" if proposals else "info",
            "title": (
                f"{len(orphans)} orphan page(s) and {len(proposals)} internal-link opportunity(ies) "
                f"across {pages} crawled page(s)"
                if observed else
                "Internal link graph not available yet — crawl the site to analyze it."
            ),
            "passed": observed and not orphans and not proposals,
            "detail": f"Internal edges: {result.get('internal_edges', 0)}; structure score: {result.get('structure_score', 0)}.",
            "provenance": provenance,
        }]
        actions: list[dict] = []
        for prop in proposals:
            actions.append({
                "id": _aid(), "type": "add_internal_link",
                "title": f"Link '{prop['suggested_anchor']}' → {prop['target_url']}",
                "description": prop["reason"],
                "target": prop["source_url"],
                "before": "no internal link to the target from this source",
                "after": f"Add a contextual internal link to {prop['target_url']} (anchor: '{prop['suggested_anchor']}').",
                "risk": "review", "severity": "medium" if prop["priority"] != "high" else "high",
                "category": "internal_links",
                "detail": "; ".join(prop.get("evidence", [])),
                "requires_approval": True, "status": "proposed", "fix_id": None,
                "source": "internal_link_agent", "proposal": prop,
                # Real crawl-derived proposal — honest provenance for the CMO's
                # confidence model (no fabricated metrics).
                "provenance": prop.get("provenance", provenance),
            })
        return self._report(
            summary=(
                f"{len(proposals)} governed internal-link opportunity(ies); {len(orphans)} orphan(s)."
                if observed else "Internal link analysis needs a crawl first."
            ),
            findings=findings, actions=actions,
            meta={"orphans": len(orphans), "proposals": len(proposals),
                  "internal_edges": result.get("internal_edges", 0), "provenance": provenance},
        )


class SchemaAgent(Specialist):
    name = "schema"
    role = "Schema Engine Agent"
    tools = ("schema_audit",)

    def analyze(self, ctx: AgentContext, registry: ToolRegistry) -> dict:
        tool = registry.get("schema_audit")
        result = tool.run(ctx) if tool else {"pages_analyzed": 0, "proposals_detail": []}
        provenance = result.get("provenance", "no_data")
        observed = provenance == "observed_live_crawl"
        gaps = result.get("gaps_detail", [])
        proposals = result.get("proposals_detail", [])
        findings = [{
            "id": _fid(), "category": "schema",
            "severity": "medium" if gaps else "info",
            "title": (
                f"{len(gaps)} schema gap(s) detected across {result.get('pages_analyzed', 0)} page(s)"
                if observed else "Schema analysis needs a crawl first."
            ),
            "passed": observed and not gaps,
            "detail": "; ".join(g["missing_type"] for g in gaps[:5]),
            "provenance": provenance,
        }]
        actions: list[dict] = []
        for prop in proposals:
            actions.append({
                "id": _aid(), "type": "insert_schema",
                "title": f"Insert {prop['schema_type']} schema on {prop['page_url']}",
                "description": prop["reason"],
                "target": prop["page_url"], "before": "no matching schema block",
                "after": f"{prop['schema_type']} JSON-LD inserted.",
                "risk": "review", "severity": "medium", "category": "schema",
                "detail": prop["reason"], "requires_approval": True, "status": "proposed",
                "fix_id": None, "source": "schema_agent",
                "page_url": prop["page_url"], "schema_type": prop["schema_type"], "data": prop["data"],
                "provenance": provenance,
            })
        return self._report(
            summary=(
                f"{len(proposals)} governed schema proposal(s); {len(gaps)} gap(s) detected."
                if observed else "Schema analysis needs a crawl first."
            ),
            findings=findings, actions=actions,
            meta={"gaps": len(gaps), "proposals": len(proposals), "provenance": provenance},
        )


class ContentRefreshAgent(Specialist):
    name = "content_refresh"
    role = "Content Refresh Agent"
    tools = ("content_refresh_audit",)

    def analyze(self, ctx: AgentContext, registry: ToolRegistry) -> dict:
        tool = registry.get("content_refresh_audit")
        result = tool.run(ctx) if tool else {"pages_analyzed": 0, "proposals_detail": []}
        provenance = result.get("provenance", "no_data")
        observed = provenance == "observed_live_crawl"
        findings_detail = result.get("findings_detail", [])
        proposals = result.get("proposals_detail", [])
        findings = [{
            "id": _fid(), "category": "content",
            "severity": "high" if any(f["finding_type"] == "thin_content" for f in findings_detail) else "medium",
            "title": (
                f"{len(findings_detail)} content-quality finding(s) across {result.get('pages_analyzed', 0)} page(s)"
                if observed else "Content refresh analysis needs a crawl first."
            ),
            "passed": observed and not findings_detail,
            "detail": "; ".join(sorted({f["finding_type"] for f in findings_detail})),
            "provenance": provenance,
        }]
        actions: list[dict] = []
        for prop in proposals:
            actions.append({
                "id": _aid(), "type": f"content_refresh_{prop['operation']}",
                "title": f"{prop['finding_type']} on {prop['page_url']}",
                "description": prop["reason"],
                "target": prop["page_url"], "before": "current content",
                "after": prop["reason"], "risk": "review", "severity": "medium",
                "category": "content", "detail": prop["reason"], "requires_approval": True,
                "status": "proposed", "fix_id": None, "source": "content_refresh_agent",
                "page_url": prop["page_url"], "operation": prop["operation"], "op_detail": prop["detail"],
                "provenance": provenance,
            })
        return self._report(
            summary=(
                f"{len(findings_detail)} content finding(s); {len(proposals)} governed proposal(s)."
                if observed else "Content refresh analysis needs a crawl first."
            ),
            findings=findings, actions=actions,
            meta={"findings": len(findings_detail), "proposals": len(proposals), "provenance": provenance},
        )


class TopicalAuthorityAgent(Specialist):
    name = "topical_authority"
    role = "Topical Authority Agent"
    tools = ("topical_authority",)

    def analyze(self, ctx: AgentContext, registry: ToolRegistry) -> dict:
        tool = registry.get("topical_authority")
        result = tool.run(ctx) if tool else {}
        if "error" in result:
            return self._report(
                summary="Topical authority analysis unavailable.",
                findings=[{"id": _fid(), "category": "strategy", "severity": "info",
                           "title": "Topical authority engine error", "passed": False,
                           "detail": result["error"]}],
                actions=[], meta={},
            )
        authority = result.get("authority_score", 0.0)
        coverage = result.get("coverage_score", 0.0)
        missing_entities = result.get("missing_entities", [])
        missing_concepts = result.get("missing_concepts", [])
        findings = [{
            "id": _fid(), "category": "strategy", "severity": "info",
            "title": f"Topical authority {authority:.0%}, coverage {coverage:.0%}; "
                     f"{len(missing_entities)} missing entity(ies), {len(missing_concepts)} missing concept(s)",
            "passed": coverage >= 0.7,
            "detail": f"{result.get('topic_count', 0)} topic(s), {result.get('entity_count', 0)} entity(ies) tracked.",
        }]
        actions: list[dict] = []
        for entity in missing_entities[:5]:
            actions.append({
                "id": _aid(), "type": "cover_missing_entity",
                "title": f"Cover missing entity: {entity}",
                "description": f"Create or expand content that establishes topical coverage of '{entity}'.",
                "target": ctx.domain, "before": "entity not covered", "after": f"'{entity}' entity covered",
                "risk": "low", "severity": "medium", "category": "strategy",
                "detail": f"Entity gap: {entity}", "requires_approval": True, "status": "proposed",
                "fix_id": None, "source": "topical_authority_agent",
            })
        for concept in missing_concepts[:5]:
            actions.append({
                "id": _aid(), "type": "cover_missing_concept",
                "title": f"Cover missing concept: {concept}",
                "description": f"Create supporting content covering '{concept}' to build topical depth.",
                "target": ctx.domain, "before": "concept not covered", "after": f"'{concept}' concept covered",
                "risk": "low", "severity": "medium", "category": "strategy",
                "detail": f"Concept gap: {concept}", "requires_approval": True, "status": "proposed",
                "fix_id": None, "source": "topical_authority_agent",
            })
        return self._report(
            summary=f"Topical authority {authority:.0%}; {len(actions)} coverage gap(s) to close.",
            findings=findings, actions=actions,
            meta={"authority_score": authority, "coverage_score": coverage},
        )


class SiteArchitectureAgent(Specialist):
    name = "site_architecture"
    role = "Semantic SEO / Site Architecture Agent"
    tools = ("site_architecture",)

    def analyze(self, ctx: AgentContext, registry: ToolRegistry) -> dict:
        tool = registry.get("site_architecture")
        result = tool.run(ctx) if tool else {}
        if "error" in result:
            return self._report(
                summary="Site architecture analysis unavailable.",
                findings=[{"id": _fid(), "category": "strategy", "severity": "info",
                           "title": "Site architecture engine error", "passed": False,
                           "detail": result["error"]}],
                actions=[], meta={},
            )
        structure_score = result.get("structure_score", 0.0)
        clusters = result.get("clusters", [])
        weak_clusters = [c for c in clusters if c.get("strength", 0) < 0.3]
        findings = [{
            "id": _fid(), "category": "strategy", "severity": "info",
            "title": f"Structure score {structure_score:.0%}; {len(clusters)} topic cluster(s), "
                     f"{len(weak_clusters)} weak cluster(s)",
            "passed": structure_score >= 0.5,
            "detail": f"Graph: {result.get('graph_node_count', 0)} node(s), {result.get('graph_edge_count', 0)} edge(s).",
        }]
        actions: list[dict] = []
        for cluster in weak_clusters[:5]:
            actions.append({
                "id": _aid(), "type": "strengthen_topic_cluster",
                "title": f"Strengthen topic cluster: {cluster.get('topic_label', cluster.get('cluster_id'))}",
                "description": "Add supporting articles and internal links to strengthen this weak cluster.",
                "target": ctx.domain, "before": f"cluster strength {cluster.get('strength', 0):.0%}",
                "after": "Cluster strengthened with supporting content and internal links.",
                "risk": "low", "severity": "medium", "category": "strategy",
                "detail": f"cluster_id={cluster.get('cluster_id')}", "requires_approval": True,
                "status": "proposed", "fix_id": None, "source": "site_architecture_agent",
            })
        return self._report(
            summary=f"Structure score {structure_score:.0%}; {len(weak_clusters)} weak topic cluster(s).",
            findings=findings, actions=actions,
            meta={"structure_score": structure_score, "cluster_count": len(clusters)},
        )


class AiWriterAgent(Specialist):
    name = "ai_writer"
    role = "AI Writer V2 Agent"
    tools = ("ai_writer_generate",)

    #: Default Automatic Blog Writer cadence — a new blog is proposed once
    #: this many days have elapsed since the last one recorded in the site's
    #: real CMO memory ``published_blogs`` history. Configurable per site via
    #: ``agent_config.executive_cmo.weekly_blog_cadence_days`` (falls back to
    #: this default when unset).
    _DEFAULT_BLOG_CADENCE_DAYS = 7

    def analyze(self, ctx: AgentContext, registry: ToolRegistry) -> dict:
        memory = ctx.cmo_memory()
        due, next_due_at, last_published_at = self._blog_is_due(memory)
        if not due:
            return self._report(
                summary=f"Weekly blog already published; next one is due {next_due_at}.",
                findings=[{
                    "id": _fid(), "category": "content", "severity": "info",
                    "title": f"Automatic Blog Writer cadence satisfied — next blog due {next_due_at}",
                    "passed": True,
                    "detail": f"last_published_at={last_published_at}",
                }],
                actions=[], meta={"generated": False, "cadence_gated": True, "next_due_at": next_due_at},
            )
        tool = registry.get("ai_writer_generate")
        result = tool.run(ctx, page_url=f"https://{ctx.domain}/", asset_type="blog_post") if tool else {"generated": False}
        generated = result.get("generated", False)
        findings = [{
            "id": _fid(), "category": "content", "severity": "info",
            "title": (
                f"AI Writer V2 draft ready (focus keyphrase: {result.get('focus_keyphrase', '')!r})"
                if generated else "AI Writer V2 draft unavailable — no AI Gateway provider configured."
            ),
            "passed": generated, "detail": "; ".join(result.get("warnings", [])),
        }]
        actions: list[dict] = []
        if generated:
            actions.append({
                "id": _aid(), "type": "publish_ai_draft",
                "title": f"Publish AI-generated draft: {result.get('title', '')}",
                "description": "Route the AI Writer V2 draft through governed publishing.",
                "target": ctx.domain, "before": "current page content",
                "after": "AI-generated, RankMath-aligned content pending approval.",
                "risk": "review", "severity": "medium", "category": "content",
                "detail": f"meta_title={result.get('meta_title', '')}",
                "requires_approval": True, "status": "proposed", "fix_id": None,
                "source": "ai_writer_agent", "page_url": result.get("page_url"), "html": result.get("html"),
                "asset_type": "blog_post", "title_text": result.get("title", ""),
            })
            actions.append({
                "id": _aid(), "type": "publish_ai_draft_seo_meta",
                "title": f"Publish SEO metadata (RankMath/OG/Twitter/canonical): {result.get('title', '')}",
                "description": "Route the AI Writer V2 RankMath/OG/Twitter/canonical metadata through governed publishing.",
                "target": ctx.domain, "before": "current page metadata",
                "after": "AI-generated RankMath/OG/Twitter/canonical metadata pending approval.",
                "risk": "review", "severity": "low", "category": "content",
                "detail": f"focus_keyphrase={result.get('focus_keyphrase', '')}",
                "requires_approval": True, "status": "proposed", "fix_id": None,
                "source": "ai_writer_seo_meta_agent", "page_url": result.get("page_url"),
                "seo_meta": result.get("seo_meta", {}),
            })
        return self._report(
            summary=(f"AI Writer V2 produced a governed draft for {ctx.domain}." if generated
                      else "AI Writer V2 could not generate a draft."),
            findings=findings, actions=actions, meta={"generated": generated},
        )

    def _blog_is_due(self, memory: dict) -> tuple[bool, str, str | None]:
        """Real weekly-cadence gate from the site's own governed publish
        history — never a separate/new scheduler. Reuses the existing
        ``agent_scheduler``/cycle cadence (which already ticks this specialist
        on every governed cycle); this only decides *whether* to propose a new
        blog on the current tick.
        """
        from datetime import datetime, timedelta, timezone

        blogs = memory.get("published_blogs") or []
        cadence_days = self._DEFAULT_BLOG_CADENCE_DAYS
        config = memory.get("executive_cmo_schedule") if isinstance(memory, dict) else None
        if isinstance(config, dict) and config.get("weekly_blog_cadence_days"):
            try:
                cadence_days = max(1, int(config["weekly_blog_cadence_days"]))
            except (TypeError, ValueError):
                pass
        if not blogs:
            return True, "now", None
        last = blogs[-1]
        last_at = last.get("published_at") if isinstance(last, dict) else None
        if not last_at:
            return True, "now", None
        try:
            last_dt = datetime.fromisoformat(str(last_at))
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return True, "now", last_at
        next_due = last_dt + timedelta(days=cadence_days)
        now = datetime.now(timezone.utc)
        return now >= next_due, next_due.isoformat(), last_at


class ProgrammaticSeoAgent(Specialist):
    name = "programmatic_seo"
    role = "Programmatic SEO Agent"
    tools = ("programmatic_seo_generate",)

    def analyze(self, ctx: AgentContext, registry: ToolRegistry) -> dict:
        tool = registry.get("programmatic_seo_generate")
        result = tool.run(ctx) if tool else {"plans": 0, "plans_detail": []}
        plans = result.get("plans_detail", [])
        findings = [{
            "id": _fid(), "category": "strategy", "severity": "info",
            "title": f"{len(plans)} programmatic landing-page plan(s) from real site entities",
            "passed": True, "detail": "; ".join(result.get("notes", [])),
        }]
        actions: list[dict] = []
        for plan in plans:
            actions.append({
                "id": _aid(), "type": f"create_{plan['page_type']}_page",
                "title": f"Create {plan['page_type']} page: {plan['title']}",
                "description": plan["reason"],
                "target": ctx.domain, "before": "page does not exist",
                "after": f"Draft page created at slug '{plan['slug']}' (never live until approved).",
                "risk": "review", "severity": "low", "category": "strategy",
                "detail": plan["reason"], "requires_approval": True, "status": "proposed",
                "fix_id": None, "source": "programmatic_seo_agent", "plan": plan,
            })
        return self._report(
            summary=f"{len(plans)} governed programmatic page plan(s) ready for approval.",
            findings=findings, actions=actions, meta={"plans": len(plans)},
        )


class ImageSeoAgent(Specialist):
    name = "image_seo"
    role = "Image SEO Agent"
    tools = ("image_seo_audit",)

    def analyze(self, ctx: AgentContext, registry: ToolRegistry) -> dict:
        tool = registry.get("image_seo_audit")
        result = tool.run(ctx) if tool else {"images_analyzed": 0, "proposals_detail": []}
        provenance = result.get("provenance", "no_data")
        observed = provenance == "observed_live_page"
        findings_detail = result.get("findings_detail", [])
        proposals = result.get("proposals_detail", [])
        findings = [{
            "id": _fid(), "category": "technical_seo",
            "severity": "high" if any(f["finding_type"] == "missing_alt" for f in findings_detail) else "low",
            "title": (
                f"{len(findings_detail)} image-markup finding(s) across {result.get('images_analyzed', 0)} image(s)"
                if observed else "Image SEO analysis needs a live page read first."
            ),
            "passed": observed and not findings_detail,
            "detail": "; ".join(sorted({f["finding_type"] for f in findings_detail})),
            "provenance": provenance,
        }]
        actions: list[dict] = []
        for prop in proposals:
            actions.append({
                "id": _aid(), "type": f"image_{prop['finding_type']}",
                "title": f"Fix {prop['finding_type']} on {prop['src']}",
                "description": prop["reason"],
                "target": prop["page_url"], "before": "current image markup",
                "after": prop["reason"], "risk": "review", "severity": "low",
                "category": "technical_seo", "detail": prop["reason"], "requires_approval": True,
                "status": "proposed", "fix_id": None, "source": "image_seo_agent",
                "page_url": prop["page_url"], "proposal": prop, "provenance": provenance,
            })
        return self._report(
            summary=(
                f"{len(findings_detail)} image finding(s); {len(proposals)} governed proposal(s)."
                if observed else "Image SEO analysis needs a live page read first."
            ),
            findings=findings, actions=actions,
            meta={"findings": len(findings_detail), "proposals": len(proposals), "provenance": provenance},
        )


class PageLifecycleAgent(Specialist):
    name = "page_lifecycle"
    role = "Page Lifecycle Agent"
    tools = ("page_lifecycle_audit",)

    def analyze(self, ctx: AgentContext, registry: ToolRegistry) -> dict:
        tool = registry.get("page_lifecycle_audit")
        result = tool.run(ctx) if tool else {"pages_analyzed": 0, "decisions_detail": []}
        provenance = result.get("provenance", "no_data")
        observed = provenance == "observed_live_crawl"
        decisions = result.get("decisions_detail", [])
        findings = [{
            "id": _fid(), "category": "strategy", "severity": "medium" if decisions else "info",
            "title": (
                f"{len(decisions)} page-lifecycle decision(s) across {result.get('pages_analyzed', 0)} page(s)"
                if observed else "Page lifecycle analysis needs a crawl first."
            ),
            "passed": observed and not decisions,
            "detail": "; ".join(sorted({d["action"] for d in decisions})),
            "provenance": provenance,
        }]
        actions: list[dict] = []
        for decision in decisions:
            actions.append({
                "id": _aid(), "type": f"lifecycle_{decision['action']}",
                "title": f"{decision['action'].replace('_', ' ').title()}: "
                         f"{decision.get('page_url') or decision.get('proposed_url', '')}",
                "description": decision["reason"],
                "target": decision.get("page_url") or decision.get("proposed_url") or ctx.domain,
                "before": "current site structure", "after": decision["reason"],
                "risk": "review", "severity": decision.get("priority", "medium"),
                "category": "strategy", "detail": decision["reason"], "requires_approval": True,
                "status": "proposed", "fix_id": None, "source": "page_lifecycle_agent",
                "decision": decision, "provenance": provenance,
            })
        return self._report(
            summary=(f"{len(decisions)} governed page-lifecycle decision(s) ready for approval."
                      if observed else "Page lifecycle analysis needs a crawl first."),
            findings=findings, actions=actions,
            meta={"decisions": len(decisions), "provenance": provenance},
        )


class CampaignPlannerAgent(Specialist):
    name = "campaign_planner"
    role = "Campaign Planner Agent"
    tools = ("campaign_planner",)

    def analyze(self, ctx: AgentContext, registry: ToolRegistry) -> dict:
        tool = registry.get("campaign_planner")
        result = tool.run(ctx) if tool else {"campaigns": 0, "campaigns_detail": []}
        campaigns = result.get("campaigns_detail", [])
        findings = [{
            "id": _fid(), "category": "strategy", "severity": "medium" if campaigns else "info",
            "title": f"{len(campaigns)} governed campaign(s) sequenced from real site evidence",
            "passed": not campaigns,
            "detail": "; ".join(sorted({c["campaign_type"] for c in campaigns})),
        }]
        actions: list[dict] = []
        for campaign in campaigns:
            actions.append({
                "id": _aid(), "type": f"campaign_{campaign['campaign_type']}",
                "title": campaign["title"],
                "description": campaign["reason"],
                "target": ctx.domain, "before": "no active campaign",
                "after": f"Campaign sequenced across {campaign.get('estimated_action_count', 0)} action(s).",
                "risk": "review", "severity": campaign.get("priority", "medium"),
                "category": "strategy", "detail": campaign["reason"], "requires_approval": True,
                "status": "proposed", "fix_id": None, "source": "campaign_planner_agent",
                "campaign": campaign,
            })
        return self._report(
            summary=f"{len(campaigns)} governed campaign(s) ready for review.",
            findings=findings, actions=actions, meta={"campaigns": len(campaigns)},
        )


class BacklinkAgent(Specialist):
    name = "backlink"
    role = "Backlink & Link-Building Agent"
    tools = ("backlink_audit",)

    def analyze(self, ctx: AgentContext, registry: ToolRegistry) -> dict:
        tool = registry.get("backlink_audit")
        result = tool.run(ctx) if tool else {"total": 0, "toxic": 0, "potentially_toxic": 0, "top_toxic": []}
        toxic = result.get("toxic", 0)
        total = result.get("total", 0)
        findings = [{
            "id": _fid(), "category": "backlinks",
            "severity": "high" if toxic else "info",
            "title": f"{toxic} toxic backlink(s) detected across {total} sampled referring domains",
            "passed": toxic == 0,
            "detail": "Toxicity scored by the backlink-intelligence engine.",
        }]
        actions: list[dict] = []
        if toxic:
            actions.append({
                "id": _aid(), "type": "disavow_toxic_backlinks",
                "title": f"Disavow {toxic} toxic backlink(s)",
                "description": "Build and submit a Google disavow file for the toxic referring domains.",
                "target": ctx.domain, "before": "toxic links counted in profile",
                "after": "Disavow file submitted; toxic links neutralised.",
                "risk": "review", "severity": "high", "category": "backlinks",
                "detail": "; ".join(f"{t['source']} ({t['score']})" for t in result.get("top_toxic", [])[:3]),
                "requires_approval": True, "status": "proposed", "fix_id": None,
                "source": "backlink_agent",
            })
        actions.append({
            "id": _aid(), "type": "link_building_outreach",
            "title": "Pursue high-authority link-building opportunities",
            "description": "Run outreach to earn links from relevant high-DR domains.",
            "target": ctx.domain, "before": "gaps vs competitors",
            "after": "Prioritised outreach list built and pitched.",
            "risk": "low", "severity": "medium", "category": "strategy",
            "detail": "Authority building via earned links.",
            "requires_approval": True, "status": "proposed", "fix_id": None,
            "source": "backlink_agent",
        })
        return self._report(
            summary=f"{toxic} toxic link(s) to review; link-building opportunities identified.",
            findings=findings, actions=actions,
            meta={"toxic": toxic, "total": total},
        )


class CompetitorIntelligenceAgent(Specialist):
    name = "competitor_intelligence"
    role = "Competitor Intelligence Agent"
    tools = ("competitor_gap",)

    def analyze(self, ctx: AgentContext, registry: ToolRegistry) -> dict:
        tool = registry.get("competitor_gap")
        result = tool.run(ctx) if tool else {"competitors": [], "keyword_gaps": []}
        gaps = result.get("keyword_gaps", [])
        competitors = result.get("competitors", [])
        findings = [{
            "id": _fid(), "category": "competitor", "severity": "info",
            "title": f"{len(gaps)} keyword gap(s) vs {len(competitors)} tracked competitor(s)",
            "passed": True,
            "detail": f"Competitors: {', '.join(competitors)}." if competitors else "No competitors set.",
        }]
        actions = [{
            "id": _aid(), "type": "content_comparison",
            "title": g.get("keyword", "Competitor gap"),
            "description": g.get("recommendation", "Create comparison content."),
            "target": ctx.domain, "before": "not ranking / no page",
            "after": g.get("recommendation", "Create comparison content."),
            "risk": "low", "severity": "medium", "category": "content",
            "detail": g.get("recommendation", ""), "requires_approval": True,
            "status": "proposed", "fix_id": None, "source": "competitor_intelligence_agent",
        } for g in gaps]
        return self._report(
            summary=f"Found {len(gaps)} keyword gap(s) to capture from competitors.",
            findings=findings, actions=actions,
            meta={"gap_count": len(gaps)},
        )


class BrandVisibilityAgent(Specialist):
    name = "brand_visibility"
    role = "Brand Visibility / GEO Agent"
    tools = ("brand_visibility",)

    def analyze(self, ctx: AgentContext, registry: ToolRegistry) -> dict:
        tool = registry.get("brand_visibility")
        result = tool.run(ctx) if tool else {"ai_visibility_score": 0, "citations": 0, "total_queries": 0}
        score = result.get("ai_visibility_score", 0)
        citations = result.get("citations", 0)
        total = result.get("total_queries", 0)
        findings = [{
            "id": _fid(), "category": "geo", "severity": "medium" if score < 50 else "info",
            "title": f"AI visibility score {score}/100 — cited in {citations}/{total} AI answers",
            "passed": score >= 50,
            "detail": "Generative Engine Optimisation (GEO): presence in ChatGPT/Perplexity/Gemini/AI Overviews.",
        }]
        actions: list[dict] = []
        if score < 65:
            for title, after in [
                ("Add FAQ/HowTo structured data for AI-answer eligibility",
                 "Mark up key pages with FAQ/HowTo JSON-LD so AI engines can cite them."),
                ("Publish authoritative, citable content",
                 "Create data-led, quotable content that AI answer engines prefer to cite."),
                ("Strengthen brand/entity signals",
                 "Add About/author bios, consistent NAP, and entity markup to build citable authority."),
            ]:
                actions.append({
                    "id": _aid(), "type": "geo_optimization", "title": title,
                    "description": title, "target": ctx.domain,
                    "before": "low AI citation rate", "after": after,
                    "risk": "low", "severity": "medium", "category": "strategy",
                    "detail": title, "requires_approval": True, "status": "proposed",
                    "fix_id": None, "source": "brand_visibility_agent",
                })
        return self._report(
            summary=f"AI/GEO visibility {score}/100; {len(actions)} optimisation(s) proposed.",
            findings=findings, actions=actions,
            meta={"ai_visibility_score": score, "citations": citations},
        )


DEFAULT_ROSTER: tuple[Specialist, ...] = (
    WebsiteHealthAgent(),
    TechnicalSeoAgent(),
    ContentStrategyAgent(),
    KeywordStrategyAgent(),
    InternalLinkAgent(),
    SchemaAgent(),
    ContentRefreshAgent(),
    TopicalAuthorityAgent(),
    SiteArchitectureAgent(),
    AiWriterAgent(),
    ProgrammaticSeoAgent(),
    ImageSeoAgent(),
    PageLifecycleAgent(),
    CampaignPlannerAgent(),
    BacklinkAgent(),
    CompetitorIntelligenceAgent(),
    BrandVisibilityAgent(),
)
