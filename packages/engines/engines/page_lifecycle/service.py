"""Page Lifecycle Engine service — pure computation over real Digital Twin data.

Reuses the real Internal Link Engine (authority/orphans) and real Content
Refresh Engine (thin/duplicate findings) — never re-implements their logic.

Decision rules (deterministic, from real evidence only):

* Orphan page with real inbound-link deficit -> ``edit`` (needs internal links);
  surfaced by the Internal Link Engine already, cross-referenced here.
* Two+ pages sharing an identical real title/H1 (duplicate_title /
  duplicate_heading findings) -> ``merge`` the weaker-authority page into the
  stronger-authority one.
* A page below the thin-content threshold with zero real inbound internal
  links and near-zero authority -> ``delete`` candidate (thin + isolated).
* A topic cluster (from Site Architecture) with 3+ real member pages and no
  single page carrying majority of that cluster's aggregate authority ->
  ``make_pillar`` on the highest-authority member, ``expand_cluster`` for the
  rest.
* A real topical-authority ``missing_entity``/``missing_concept`` with no
  existing page addressing it -> ``create``.
"""
from __future__ import annotations

from urllib.parse import urlsplit

from engines.content_refresh.service import ContentRefreshService
from engines.internal_link.service import InternalLinkService
from engines.page_lifecycle.models import LifecycleDecision, PageLifecycleReport

__all__ = ["PageLifecycleService"]


def _slug(url: str) -> str:
    path = urlsplit(url).path.rstrip("/")
    return path.rsplit("/", 1)[-1] if path else ""


class PageLifecycleService:
    engine_name = "page_lifecycle"
    engine_version = "1.0.0"

    def analyze(
        self, site_id: str, pages: list, *,
        missing_entities: list[str] | None = None,
        missing_concepts: list[str] | None = None,
        clusters: list[dict] | None = None,
    ) -> PageLifecycleReport:
        report = PageLifecycleReport(site_id=site_id, pages_analyzed=len(pages))
        if not pages:
            report.notes.append("No crawled pages available; run a crawl first.")
            report.provenance = "no_data"
            return report

        link_report = InternalLinkService().analyze(site_id, pages)
        refresh_report = ContentRefreshService().analyze(site_id, pages)
        authority_by_url = {a.url: a for a in link_report.authorities}

        # --- edit: orphan/weak pages already identified by the real link graph
        for authority in link_report.authorities:
            if authority.is_orphan:
                report.decisions.append(LifecycleDecision(
                    action="edit", page_url=authority.url,
                    reason="Orphan page (zero real inbound internal links); needs internal linking.",
                    evidence=[f"inbound_internal_links={authority.inbound_internal_links}"],
                    priority="high",
                ))

        # --- merge: duplicate_title / duplicate_heading findings, weaker into stronger
        seen_pairs: set[tuple[str, str]] = set()
        by_finding: dict[str, list[str]] = {}
        for finding in refresh_report.findings:
            if finding.finding_type in ("duplicate_title", "duplicate_heading"):
                by_finding.setdefault(finding.finding_type + "::" + finding.evidence[0], []).append(finding.page_url)
        for urls in by_finding.values():
            if len(urls) < 2:
                continue
            ranked = sorted(urls, key=lambda u: authority_by_url.get(u).authority_score if authority_by_url.get(u) else 0.0, reverse=True)
            strongest = ranked[0]
            for weaker in ranked[1:]:
                pair = (weaker, strongest)
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                report.decisions.append(LifecycleDecision(
                    action="merge", page_url=weaker, merge_into_url=strongest,
                    reason="Duplicate title/heading with another real page; consolidate ranking signals.",
                    evidence=[f"duplicate content vs {strongest}"],
                    priority="medium",
                ))

        # --- delete: thin AND isolated (zero inbound, near-zero authority)
        thin_urls = {f.page_url for f in refresh_report.findings if f.finding_type == "thin_content"}
        merged_sources = {d.page_url for d in report.decisions if d.action == "merge"}
        for url in thin_urls - merged_sources:
            authority = authority_by_url.get(url)
            # Isolation is measured by real inbound-link count, not the raw
            # PageRank score: with few/no edges in the graph, PageRank
            # normalizes to a uniform value across every node and cannot
            # distinguish "isolated" from "well-linked" on its own.
            if authority and authority.is_orphan and authority.outbound_internal_links == 0:
                report.decisions.append(LifecycleDecision(
                    action="delete", page_url=url,
                    reason="Thin content with zero inbound and zero outbound internal links; isolated and low value to maintain.",
                    evidence=[f"inbound_internal_links={authority.inbound_internal_links}",
                              f"outbound_internal_links={authority.outbound_internal_links}",
                              "thin_content finding"],
                    priority="low",
                ))

        # --- pillar/cluster: real Site Architecture clusters, 3+ real members
        for cluster in clusters or []:
            members = cluster.get("member_page_ids") or []
            if len(members) < 3:
                continue
            member_authorities = [(m, authority_by_url.get(m)) for m in members]
            ranked = sorted(
                [(m, a.authority_score if a else 0.0) for m, a in member_authorities],
                key=lambda pair: pair[1], reverse=True,
            )
            if not ranked:
                continue
            pillar_url, pillar_score = ranked[0]
            total = sum(score for _, score in ranked) or 1.0
            if pillar_score / total < 0.5:
                report.decisions.append(LifecycleDecision(
                    action="make_pillar", page_url=pillar_url,
                    reason=f"Highest-authority member of cluster '{cluster.get('topic_label', cluster.get('cluster_id'))}' "
                           "should anchor the cluster as its pillar.",
                    evidence=[f"authority_share={round(pillar_score / total, 2)}", f"cluster_members={len(members)}"],
                    priority="medium",
                ))
            for member_url, _ in ranked[1:]:
                report.decisions.append(LifecycleDecision(
                    action="expand_cluster", page_url=member_url,
                    reason="Supporting cluster member; strengthen internal links to/from the pillar.",
                    evidence=[f"cluster={cluster.get('cluster_id')}"],
                    priority="low",
                ))

        # --- create: real entity/concept gaps with no matching page
        existing_slugs = {_slug(p.url) for p in pages}
        for entity in missing_entities or []:
            candidate_slug = entity.lower().replace(" ", "-")
            if candidate_slug not in existing_slugs:
                report.decisions.append(LifecycleDecision(
                    action="create", proposed_url=f"/{candidate_slug}",
                    reason=f"Topical authority gap: entity '{entity}' has no dedicated page.",
                    evidence=[f"missing_entity={entity}"], priority="medium",
                ))
        for concept in missing_concepts or []:
            candidate_slug = concept.lower().replace(" ", "-")
            if candidate_slug not in existing_slugs:
                report.decisions.append(LifecycleDecision(
                    action="create", proposed_url=f"/{candidate_slug}",
                    reason=f"Topical authority gap: concept '{concept}' has no supporting content.",
                    evidence=[f"missing_concept={concept}"], priority="medium",
                ))

        if not report.decisions:
            report.notes.append("No lifecycle action indicated by current real evidence.")
        return report
