"""Milestone 5 — Automatic Landing Page Generator page-type coverage.

``ProgrammaticSeoService.plan`` covers service/city/category/comparison plus
the Milestone-5 additions (product/location/industry/pricing/faq), each gated
strictly on real, already-known entities supplied by the caller — never
fabricated placeholders.
"""
from __future__ import annotations

from engines.programmatic_seo import ProgrammaticSeoService


def test_plan_covers_every_page_type_when_entities_present() -> None:
    svc = ProgrammaticSeoService()
    report = svc.plan("site-1", {
        "services": ["SEO Audit"],
        "cities": ["Austin"],
        "categories": ["Local SEO"],
        "competitors": ["rival.com"],
        "products": ["Widget Pro"],
        "locations": ["Austin, TX"],
        "industries": ["Healthcare"],
        "pricing_plans": [{"name": "Starter"}, {"name": "Pro"}],
        "faqs": [{"question": "Q1", "answer": "A1"}],
    })
    types = {p.page_type for p in report.plans}
    assert types == {"service", "city", "category", "comparison", "product",
                      "location", "industry", "pricing", "faq"}
    # service x city cross-product produces one dedicated city page.
    city_plans = [p for p in report.plans if p.page_type == "city"]
    assert len(city_plans) == 1
    assert city_plans[0].entity == "SEO Audit::Austin"
    # Two pricing plans -> two pricing pages.
    pricing_plans = [p for p in report.plans if p.page_type == "pricing"]
    assert len(pricing_plans) == 2
    # One faq page regardless of FAQ count.
    faq_plans = [p for p in report.plans if p.page_type == "faq"]
    assert len(faq_plans) == 1


def test_plan_never_fabricates_missing_entity_types() -> None:
    svc = ProgrammaticSeoService()
    report = svc.plan("site-1", {"services": ["SEO Audit"]})
    types = {p.page_type for p in report.plans}
    assert types == {"service"}
    assert not any(p.page_type in {"product", "location", "industry", "pricing", "faq"} for p in report.plans)


def test_plan_empty_entities_produces_no_plans_and_a_note() -> None:
    svc = ProgrammaticSeoService()
    report = svc.plan("site-1", {})
    assert report.plans == []
    assert report.notes
