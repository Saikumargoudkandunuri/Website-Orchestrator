"""Milestone 5 — Campaign Planner Engine (item 7).

Sequences real evidence from other engines into named campaigns. Every
assertion here checks that a campaign only appears when real, concrete
evidence for it was supplied — never fabricated.
"""
from __future__ import annotations

from engines.campaign_planner import CAMPAIGN_TYPES, CampaignPlannerService


def test_blog_cluster_campaign_from_thin_cluster() -> None:
    svc = CampaignPlannerService()
    report = svc.plan("site-1", clusters=[
        {"cluster_id": "c1", "topic_label": "SEO Basics", "member_page_ids": ["p1"], "strength": 1.0},
    ])
    types = {c.campaign_type for c in report.campaigns}
    assert "blog_cluster" in types
    campaign = next(c for c in report.campaigns if c.campaign_type == "blog_cluster")
    assert campaign.estimated_action_count == 2  # needs 2 more to reach 3


def test_topic_cluster_campaign_from_weak_cluster() -> None:
    svc = CampaignPlannerService()
    report = svc.plan("site-1", clusters=[
        {"cluster_id": "c2", "topic_label": "Local SEO", "member_page_ids": ["p1", "p2", "p3"], "strength": 0.2},
    ])
    types = {c.campaign_type for c in report.campaigns}
    assert "topic_cluster" in types


def test_topic_cluster_campaign_from_entity_gaps() -> None:
    svc = CampaignPlannerService()
    report = svc.plan("site-1", missing_entities=["Schema Markup"], missing_concepts=["EEAT"])
    campaign = next(c for c in report.campaigns if c.campaign_type == "topic_cluster")
    assert "gap=Schema Markup" in campaign.evidence
    assert "gap=EEAT" in campaign.evidence


def test_internal_linking_campaign_from_orphans() -> None:
    svc = CampaignPlannerService()
    report = svc.plan("site-1", orphan_pages=["https://example.com/orphan"])
    campaign = next(c for c in report.campaigns if c.campaign_type == "internal_linking")
    assert campaign.priority == "high"
    assert "https://example.com/orphan" in campaign.target_pages


def test_authority_building_requires_cornerstone_and_gap_evidence() -> None:
    svc = CampaignPlannerService()
    # Cornerstone pages alone, no gaps -> no authority_building campaign.
    report = svc.plan("site-1", cornerstone_pages=["https://example.com/pillar"])
    assert not any(c.campaign_type == "authority_building" for c in report.campaigns)

    # Cornerstone pages + real gap evidence -> campaign appears.
    report2 = svc.plan("site-1", cornerstone_pages=["https://example.com/pillar"], orphan_pages=["https://example.com/orphan"])
    assert any(c.campaign_type == "authority_building" for c in report2.campaigns)


def test_geo_and_ai_overview_campaigns_from_schema_gaps() -> None:
    svc = CampaignPlannerService()
    report = svc.plan("site-1", schema_gaps=["FAQ schema", "Author bio"])
    types = {c.campaign_type for c in report.campaigns}
    assert "geo_optimization" in types
    assert "ai_overview_optimization" in types


def test_product_launch_and_seasonal_from_business_profile() -> None:
    svc = CampaignPlannerService()
    report = svc.plan(
        "site-1",
        products_services=["Widget Pro"],
        seasonal_opportunities=[{"name": "Black Friday"}],
    )
    types = {c.campaign_type for c in report.campaigns}
    assert "product_launch" in types
    assert "seasonal" in types


def test_no_evidence_yields_no_campaigns_and_a_note() -> None:
    svc = CampaignPlannerService()
    report = svc.plan("site-1")
    assert report.campaigns == []
    assert report.notes


def test_all_campaign_types_are_valid_members_of_constant() -> None:
    svc = CampaignPlannerService()
    report = svc.plan(
        "site-1",
        clusters=[{"cluster_id": "c1", "topic_label": "X", "member_page_ids": ["p1"], "strength": 1.0}],
        orphan_pages=["u1"], schema_gaps=["FAQ schema"],
        products_services=["P"], seasonal_opportunities=[{"name": "S"}],
    )
    for campaign in report.campaigns:
        assert campaign.campaign_type in CAMPAIGN_TYPES
