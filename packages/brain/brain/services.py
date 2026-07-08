"""SeoBrain — the unified cross-engine synthesis service (M5 Phase 1).

Given a ``site_id``, assembles a ``SiteSynthesis`` by reading the latest version
of every M3 and M4 engine output. This is explicitly NOT a new analysis engine —
it performs no scoring or inference, only structured aggregation so Phase 2's
Decision Engine has one clean input surface instead of twenty.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from brain.models import EngineSummary, SiteSynthesis
from brain.repositories import KnowledgeGraphRepository, SiteSynthesisRepository

__all__ = ["SeoBrain"]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex


class SeoBrain:
    """Assembles ``SiteSynthesis`` from all engine repositories (read-only).

    Injected with the repositories from all 20 engines. Each repository is
    accessed via its ``get_latest(tenant_id, site_id)`` method to pull the
    most recent output.
    """

    # M3 engine names and their repository attribute names on EnginesContainer
    M3_ENGINES: list[tuple[str, str]] = [
        ("technical_seo", "technical_seo_repo"),
        ("site_architecture", "site_arch_repo"),
        ("keyword_intelligence", "keyword_repo"),
        ("content_intelligence", "content_repo"),
        ("competitor_intelligence", "competitor_repo"),
        ("backlink_intelligence", "backlink_repo"),
        ("topical_authority", "topical_authority_repo"),
        ("seo_scoring", "seo_score_repo"),
        ("opportunity", "opportunity_repo"),
        ("recommendation", "recommendation_repo"),
    ]

    # M4 engine names and their repository attribute names on GrowthContainer
    M4_ENGINES: list[tuple[str, str]] = [
        ("content_generation", "content_asset_repo"),
        ("content_optimization", "content_optimization_repo"),
        ("local_seo", "local_seo_repo"),
        ("reputation_management", "reputation_repo"),
        ("rank_tracking", "rank_tracking_repo"),
        ("reporting", "reporting_repo"),
        ("analytics_intelligence", "analytics_repo"),
        ("outreach", "outreach_repo"),
        ("automation", "automation_repo"),
        ("agency_management", "agency_repo"),
    ]

    def __init__(
        self,
        *,
        m3_repos: dict[str, Any] | None = None,
        m4_repos: dict[str, Any] | None = None,
        synthesis_repo: SiteSynthesisRepository | None = None,
        kg_repo: KnowledgeGraphRepository | None = None,
    ) -> None:
        self._m3_repos = m3_repos or {}
        self._m4_repos = m4_repos or {}
        self._synthesis_repo = synthesis_repo
        self._kg_repo = kg_repo

    def _read_engine_output(
        self,
        repo: Any,
        tenant_id: str,
        site_id: str,
    ) -> EngineSummary | None:
        """Try to read latest output from a repository, return None on failure."""
        try:
            result = repo.get_latest(tenant_id, site_id)
            if result is None:
                return None
            version = getattr(result, "version", None)
            computed_at = getattr(result, "computed_at", None)
            data_completeness = getattr(result, "data_completeness", 1.0)
            output_data = result.model_dump(mode="json") if hasattr(result, "model_dump") else result
            return EngineSummary(
                engine_name="",  # set by caller
                has_data=True,
                latest_version=version,
                computed_at=computed_at,
                output=output_data,
                data_completeness=data_completeness if data_completeness is not None else 1.0,
            )
        except Exception:
            return None

    def get_synthesis(
        self, tenant_id: str, site_id: str
    ) -> SiteSynthesis:
        """Assemble and return a ``SiteSynthesis`` for the given site.

        Reads the latest output from every engine repository (M3 + M4).
        Does not persist — call ``save_synthesis()`` to store the result.
        """
        m3_summaries: dict[str, EngineSummary] = {}
        m4_summaries: dict[str, EngineSummary] = {}
        engines_with_data = 0
        total_opportunities = 0
        total_recommendations = 0
        overall_seo_score: float | None = None
        total_issues = 0

        # Collect M3 engine outputs
        for engine_name, repo_key in self.M3_ENGINES:
            repo = self._m3_repos.get(repo_key)
            if repo is None:
                m3_summaries[engine_name] = EngineSummary(
                    engine_name=engine_name,
                    engine_category="m3",
                    has_data=False,
                )
                continue
            summary = self._read_engine_output(repo, tenant_id, site_id)
            if summary is None:
                m3_summaries[engine_name] = EngineSummary(
                    engine_name=engine_name,
                    engine_category="m3",
                    has_data=False,
                )
            else:
                summary = summary.model_copy(update={
                    "engine_name": engine_name,
                    "engine_category": "m3",
                })
                m3_summaries[engine_name] = summary
                engines_with_data += 1

                # Extract aggregate metrics from specific engines
                if engine_name == "opportunity" and summary.output:
                    opps = summary.output.get("opportunities", [])
                    total_opportunities = len(opps)
                if engine_name == "recommendation" and summary.output:
                    recs = summary.output.get("recommendations", [])
                    total_recommendations = len(recs)
                if engine_name == "seo_scoring" and summary.output:
                    overall_seo_score = summary.output.get("overall_score")
                if engine_name == "technical_seo" and summary.output:
                    issues = summary.output.get("issues", [])
                    total_issues += len(issues)

        # Collect M4 engine outputs
        for engine_name, repo_key in self.M4_ENGINES:
            repo = self._m4_repos.get(repo_key)
            if repo is None:
                m4_summaries[engine_name] = EngineSummary(
                    engine_name=engine_name,
                    engine_category="m4",
                    has_data=False,
                )
                continue
            summary = self._read_engine_output(repo, tenant_id, site_id)
            if summary is None:
                m4_summaries[engine_name] = EngineSummary(
                    engine_name=engine_name,
                    engine_category="m4",
                    has_data=False,
                )
            else:
                summary = summary.model_copy(update={
                    "engine_name": engine_name,
                    "engine_category": "m4",
                })
                m4_summaries[engine_name] = summary
                engines_with_data += 1

        return SiteSynthesis(
            id=_new_id(),
            site_id=site_id,
            tenant_id=tenant_id,
            m3_engines=m3_summaries,
            m4_engines=m4_summaries,
            engines_with_data=engines_with_data,
            total_opportunities=total_opportunities,
            total_recommendations=total_recommendations,
            overall_seo_score=overall_seo_score,
            total_issues_found=total_issues,
        )

    def save_synthesis(
        self, tenant_id: str, synthesis: SiteSynthesis
    ) -> SiteSynthesis:
        """Persist a ``SiteSynthesis`` via the repository."""
        if self._synthesis_repo is None:
            raise RuntimeError("No SiteSynthesisRepository configured.")
        return self._synthesis_repo.save(tenant_id, synthesis)

    def get_latest_synthesis(
        self, tenant_id: str, site_id: str
    ) -> SiteSynthesis | None:
        """Return the latest persisted synthesis, or None."""
        if self._synthesis_repo is None:
            return None
        return self._synthesis_repo.get_latest(tenant_id, site_id)
