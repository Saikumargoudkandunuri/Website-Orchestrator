"""Programmatic SEO service — pure planning over real, already-known entities.

Input is a plain dict of real site data the caller already has (never
fabricated by this service):

    {
      "services": ["SEO Audit", "Content Writing"],
      "cities": ["Austin", "Denver"],
      "categories": ["Local SEO", "Technical SEO"],
      "competitors": ["competitor-a.com", "competitor-b.com"],
    }

Any key that is empty/absent simply yields no plans of that page_type — the
engine never invents an entity to fill a template.
"""
from __future__ import annotations

import re

from engines.programmatic_seo.models import ProgrammaticPagePlan, ProgrammaticSeoReport

__all__ = ["ProgrammaticSeoService"]


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "page"


class ProgrammaticSeoService:
    engine_name = "programmatic_seo"
    engine_version = "1.0.0"

    def plan(self, site_id: str, entities: dict) -> ProgrammaticSeoReport:
        report = ProgrammaticSeoReport(site_id=site_id)
        services = entities.get("services") or []
        cities = entities.get("cities") or []
        categories = entities.get("categories") or []
        competitors = entities.get("competitors") or []
        products = entities.get("products") or []
        locations = entities.get("locations") or []
        industries = entities.get("industries") or []
        pricing_plans = entities.get("pricing_plans") or []
        faqs = entities.get("faqs") or []

        for service in services:
            report.plans.append(ProgrammaticPagePlan(
                page_type="service", slug=_slugify(service),
                title=f"{service} Services", entity=service,
                reason=f"Real service '{service}' has no dedicated landing page.",
                template_vars={"service": service},
            ))
            for city in cities:
                report.plans.append(ProgrammaticPagePlan(
                    page_type="city", slug=_slugify(f"{service}-in-{city}"),
                    title=f"{service} in {city}", entity=f"{service}::{city}",
                    reason=f"Real service '{service}' x real city '{city}' combination has no page.",
                    template_vars={"service": service, "city": city},
                ))

        for category in categories:
            report.plans.append(ProgrammaticPagePlan(
                page_type="category", slug=_slugify(category),
                title=f"{category} Resources", entity=category,
                reason=f"Real category '{category}' has no hub/category page.",
                template_vars={"category": category},
            ))

        for competitor in competitors:
            report.plans.append(ProgrammaticPagePlan(
                page_type="comparison", slug=_slugify(f"vs-{competitor}"),
                title=f"Comparison vs {competitor}", entity=competitor,
                reason=f"Real tracked competitor '{competitor}' has no comparison page.",
                template_vars={"competitor": competitor},
            ))

        for product in products:
            report.plans.append(ProgrammaticPagePlan(
                page_type="product", slug=_slugify(product),
                title=product, entity=product,
                reason=f"Real product '{product}' has no dedicated product page.",
                template_vars={"product": product},
            ))

        for location in locations:
            report.plans.append(ProgrammaticPagePlan(
                page_type="location", slug=_slugify(location),
                title=f"{location} Location", entity=location,
                reason=f"Real business location '{location}' has no dedicated location page.",
                template_vars={"location": location},
            ))

        for industry in industries:
            report.plans.append(ProgrammaticPagePlan(
                page_type="industry", slug=_slugify(f"{industry}-solutions"),
                title=f"{industry} Solutions", entity=industry,
                reason=f"Real target industry '{industry}' has no industry-specific page.",
                template_vars={"industry": industry},
            ))

        for plan_item in pricing_plans:
            name = plan_item.get("name") if isinstance(plan_item, dict) else str(plan_item)
            report.plans.append(ProgrammaticPagePlan(
                page_type="pricing", slug=_slugify(f"pricing-{name}"),
                title=f"{name} Pricing", entity=name,
                reason=f"Real pricing plan '{name}' has no dedicated pricing page.",
                template_vars={"plan": plan_item if isinstance(plan_item, dict) else {"name": name}},
            ))

        if faqs:
            report.plans.append(ProgrammaticPagePlan(
                page_type="faq", slug="faq",
                title="Frequently Asked Questions", entity="faq",
                reason=f"{len(faqs)} real, already-collected FAQ entr(ies) have no dedicated FAQ page.",
                template_vars={"faqs": faqs},
            ))

        if not report.plans:
            report.notes.append(
                "No service/city/category/competitor/product/location/industry/"
                "pricing/faq entities supplied; nothing to plan."
            )
        return report
