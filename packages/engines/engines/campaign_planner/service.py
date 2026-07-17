"""Campaign Planner service — pure sequencing over real engine output.

Never re-implements detection: every campaign is derived from evidence the
Topical Authority, Site Architecture, Internal Link, and AI Visibility engines
already computed from real crawl/entity data, plus the account's own
onboarding-collected business profile (products/services, seasonal
opportunities) from CMO memory. No industry news/trends are fabricated here —
Market Intelligence campaigns (competitor-driven) require a connected
competitor/backlink data provider and are out of scope for this deterministic
planner until one is wired in.
"""
from __future__ import annotations

from engines.campaign_planner.models import CampaignPlan, CampaignPlannerReport

__all__ = ["CampaignPlannerService"]


class CampaignPlannerService:
    engine_name = "campaign_planner"
    engine_version = "1.0.0"

    def plan(
        self,
        site_id: str,
        *,
        clusters: list[dict] | None = None,
        missing_entities: list[str] | None = None,
        missing_concepts: list[str] | None = None,
        cornerstone_pages: list[str] | None = None,
        orphan_pages: list[str] | None = None,
        weak_pages: list[str] | None = None,
        schema_gaps: list[str] | None = None,
        products_services: list[str] | None = None,
        seasonal_opportunities: list[dict] | None = None,
    ) -> CampaignPlannerReport:
        report = CampaignPlannerReport(site_id=site_id)

        # --- blog_cluster / topic_cluster: real Site Architecture clusters
        # with too few supporting pages to carry topical weight.
        for cluster in clusters or []:
            members = cluster.get("member_page_ids") or []
            label = cluster.get("topic_label") or cluster.get("cluster_id", "cluster")
            if 1 <= len(members) < 3:
                report.campaigns.append(CampaignPlan(
                    campaign_type="blog_cluster",
                    title=f"Build out blog cluster: {label}",
                    reason=f"Topic cluster '{label}' has only {len(members)} page(s); "
                           "needs supporting articles to reach cluster depth.",
                    evidence=[f"cluster_id={cluster.get('cluster_id')}", f"members={len(members)}"],
                    target_pages=list(members),
                    estimated_action_count=max(1, 3 - len(members)),
                    priority="medium",
                ))
            elif len(members) >= 3 and cluster.get("strength", 1.0) < 0.5:
                report.campaigns.append(CampaignPlan(
                    campaign_type="topic_cluster",
                    title=f"Strengthen internal linking within cluster: {label}",
                    reason=f"Cluster '{label}' has {len(members)} pages but weak "
                           f"intra-cluster link density ({cluster.get('strength', 0):.0%}).",
                    evidence=[f"cluster_id={cluster.get('cluster_id')}", f"strength={cluster.get('strength', 0)}"],
                    target_pages=list(members),
                    estimated_action_count=len(members),
                    priority="medium",
                ))

        # --- topic_cluster (entity/concept gaps): real topical-authority gaps
        # with no dedicated page — pairs naturally with Page Lifecycle's
        # `create` decisions but is surfaced here as a sequencing campaign.
        gap_entities = list(missing_entities or []) + list(missing_concepts or [])
        if gap_entities:
            report.campaigns.append(CampaignPlan(
                campaign_type="topic_cluster",
                title=f"Close {len(gap_entities)} topical-authority gap(s)",
                reason="Real entity/concept gaps have no dedicated supporting content.",
                evidence=[f"gap={g}" for g in gap_entities[:10]],
                target_pages=list(cornerstone_pages or []),
                estimated_action_count=len(gap_entities),
                priority="medium",
            ))

        # --- internal_linking: real orphans/weak pages from the Internal Link Engine.
        isolated = list(orphan_pages or []) + list(weak_pages or [])
        if isolated:
            report.campaigns.append(CampaignPlan(
                campaign_type="internal_linking",
                title=f"Internal linking campaign for {len(isolated)} isolated/weak page(s)",
                reason="Real inbound-link deficits detected by the Internal Link Engine.",
                evidence=[f"orphans={len(orphan_pages or [])}", f"weak={len(weak_pages or [])}"],
                target_pages=isolated[:50],
                estimated_action_count=len(isolated),
                priority="high" if orphan_pages else "medium",
            ))

        # --- authority_building: cornerstone pages worth reinforcing once
        # linking/topical gaps exist (reuses the same evidence, different lens).
        if cornerstone_pages and (isolated or gap_entities):
            report.campaigns.append(CampaignPlan(
                campaign_type="authority_building",
                title=f"Reinforce authority around {len(cornerstone_pages)} cornerstone page(s)",
                reason="Cornerstone pages exist but surrounding topical/linking gaps limit their authority flow.",
                evidence=[f"cornerstone_pages={len(cornerstone_pages)}"],
                target_pages=list(cornerstone_pages),
                estimated_action_count=len(cornerstone_pages),
                priority="medium",
            ))

        # --- geo_optimization / ai_overview_optimization: real schema-readiness
        # gaps from the AI Visibility engine.
        gaps = list(schema_gaps or [])
        if gaps:
            report.campaigns.append(CampaignPlan(
                campaign_type="geo_optimization",
                title=f"Close {len(gaps)} AI/GEO schema-readiness gap(s)",
                reason="Real schema-readiness gaps reduce eligibility for AI Overview / LLM citation.",
                evidence=[f"gap={g}" for g in gaps],
                estimated_action_count=len(gaps),
                priority="medium",
            ))
            blocking = [g for g in gaps if "faq" in g.lower() or "article" in g.lower()]
            if blocking:
                report.campaigns.append(CampaignPlan(
                    campaign_type="ai_overview_optimization",
                    title="Add FAQ/Article schema for AI Overview eligibility",
                    reason="Missing FAQ/Article schema is a real, direct blocker to AI Overview citation.",
                    evidence=blocking,
                    estimated_action_count=1,
                    priority="medium",
                ))

        # --- product_launch: real, already-known products/services with no
        # dedicated page (cross-referenced with Programmatic SEO's create plans).
        for product in products_services or []:
            report.campaigns.append(CampaignPlan(
                campaign_type="product_launch",
                title=f"Launch campaign: {product}",
                reason=f"Real product/service '{product}' from the account's business profile "
                       "has no dedicated launch campaign yet.",
                evidence=[f"product={product}"],
                estimated_action_count=3,  # landing page + announcement blog + internal links
                priority="medium",
            ))

        # --- seasonal: real, already-recorded seasonal opportunities from CMO memory.
        for opportunity in seasonal_opportunities or []:
            name = opportunity.get("name") if isinstance(opportunity, dict) else str(opportunity)
            report.campaigns.append(CampaignPlan(
                campaign_type="seasonal",
                title=f"Seasonal campaign: {name}",
                reason=f"Real, account-recorded seasonal opportunity '{name}' has no active campaign.",
                evidence=[f"opportunity={name}"],
                estimated_action_count=2,
                priority="medium",
            ))

        if not report.campaigns:
            report.notes.append("No real evidence currently supports a campaign; nothing to plan.")
        return report
