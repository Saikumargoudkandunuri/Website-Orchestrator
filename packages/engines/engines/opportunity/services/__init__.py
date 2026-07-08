"""Opportunity Engine service (section 4.9).

Prioritizes work items from upstream engine findings. Scores are computed
deterministically; ai_justification is the only AI-generated field.
"""
from __future__ import annotations
import uuid
from typing import Any
from engines.opportunity.models import EffortLevel, Opportunity, OpportunityReport

__all__ = ["OpportunityService"]

_EFFORT_MAP = {
    "update_alt_text": EffortLevel.SMALL,
    "update_meta_description": EffortLevel.SMALL,
    "update_title": EffortLevel.SMALL,
    "update_slug": EffortLevel.SMALL,
    "update_schema": EffortLevel.MEDIUM,
    None: EffortLevel.MEDIUM,
}


class OpportunityService:
    def __init__(self, capability_runner=None):
        self._runner = capability_runner

    def analyze(self, site_id, *, site_context=None, options=None,
                technical_audits=None, seo_scores=None):
        tenant_id = getattr(site_context, "tenant_id", "") if site_context else ""
        opportunities: list[Opportunity] = []

        # Build opportunities from technical findings
        for page_id, audit in (technical_audits or {}).items():
            for finding in getattr(audit, "findings", []) or []:
                if getattr(finding, "passed", True):
                    continue
                sev = getattr(finding, "severity", None)
                critical = sev is not None and sev.value == "critical"
                impact = {"critical": 0.95, "high": 0.75, "medium": 0.45, "low": 0.2, "info": 0.05}.get(
                    getattr(sev, "value", "medium"), 0.45)
                fix_type = getattr(finding, "related_fix_type", None)
                effort = _EFFORT_MAP.get(fix_type, EffortLevel.MEDIUM)
                effort_val = {"small": 0.2, "medium": 0.5, "large": 0.8}.get(effort.value, 0.5)
                priority = round(impact * (1.0 - effort_val * 0.5), 4)
                quick_win = impact >= 0.6 and effort == EffortLevel.SMALL
                justification = self._get_justification(finding, page_id) if self._runner else ""
                opportunities.append(Opportunity(
                    id=uuid.uuid4().hex[:12],
                    source_finding_ref=f"technical_seo/{page_id}/{getattr(finding,'check_name','unknown')}",
                    source_engine="technical_seo",
                    effort=effort,
                    impact_estimate=impact,
                    revenue_potential=None,
                    quick_win=quick_win,
                    critical=critical,
                    priority_score=priority,
                    ai_justification=justification,
                    data_completeness=1.0,
                ))

        opportunities.sort(key=lambda o: o.priority_score, reverse=True)
        quick_wins = [o.id for o in opportunities if o.quick_win]
        critical_ids = [o.id for o in opportunities if o.critical]
        return OpportunityReport(
            site_id=site_id, tenant_id=tenant_id,
            opportunities=opportunities, quick_wins=quick_wins, critical_issues=critical_ids,
        )

    def _get_justification(self, finding, page_id):
        try:
            from intelligence.prompts.base_prompt_template import PromptContext
            ctx = PromptContext(page_url=page_id)
            result = self._runner.run("seo_audit", ctx, page_id=page_id)
            payload = result.payload or {}
            return payload.get("page_purpose", "")[:200]
        except Exception:
            return ""
