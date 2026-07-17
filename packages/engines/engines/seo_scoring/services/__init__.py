"""SEO Scoring Engine service (section 4.8).

Aggregates component scores from upstream engine outputs.
"""
from __future__ import annotations
from typing import Any
from engines.seo_scoring.models import ComponentScore, SCORING_VERSION, SeoScoreBreakdown, SeoScoreReport

__all__ = ["SeoScoringService"]

_WEIGHTS = {
    "technical_score": 0.20,
    "content_score": 0.20,
    "keyword_score": 0.15,
    "internal_link_score": 0.10,
    "authority_score": 0.10,
    "performance_score": 0.05,
    "accessibility_score": 0.10,
    "trust_score": 0.10,
}


class SeoScoringService:
    def analyze(self, page_id, site_id, *, knowledge_object=None, site_context=None,
                options=None, technical_audit=None, site_arch_report=None):
        tenant_id = getattr(knowledge_object, "tenant_id", "") if knowledge_object else ""
        components = {
            "technical_score": self._technical_component(technical_audit),
            "content_score": self._content_component(knowledge_object),
            "keyword_score": self._keyword_component(knowledge_object),
            "internal_link_score": self._link_component(page_id, knowledge_object, site_arch_report),
            "authority_score": self._authority_component(options),
            "performance_score": ComponentScore(value=0.0, data_completeness=0.0,
                notes="Performance signals not collected this milestone.", weight=_WEIGHTS["performance_score"]),
            "accessibility_score": self._accessibility_component(knowledge_object),
            "trust_score": self._trust_component(knowledge_object),
        }
        overall = self._weighted_overall(components)
        breakdown = SeoScoreBreakdown(component_scores=components, weights=dict(_WEIGHTS), overall_score=overall)
        return SeoScoreReport(page_id=page_id, site_id=site_id, tenant_id=tenant_id, breakdown=breakdown)

    def _technical_component(self, audit):
        if audit is None:
            return ComponentScore(value=0.0, data_completeness=0.0, notes="No audit.", weight=_WEIGHTS["technical_score"])
        # Use the canonical Site Audit Health Score (0-100) from TechnicalSeoService.
        from engines.technical_seo.services import TechnicalSeoService  # noqa: PLC0415
        health = TechnicalSeoService.health_score(audit)
        critical = getattr(audit, "critical_count", 0) or 0
        high = getattr(audit, "high_count", 0) or 0
        return ComponentScore(value=round(health, 2), data_completeness=1.0,
            notes=f"Health Score {health:.0f}/100 ({critical} critical, {high} high).", weight=_WEIGHTS["technical_score"])

    def _content_component(self, ko):
        if ko is None:
            return ComponentScore(value=0.0, data_completeness=0.0, notes="No KO.", weight=_WEIGHTS["content_score"])
        content = getattr(ko, "content_intelligence", None)
        cs = getattr(content, "content_score", None) if content else None
        m2_score = getattr(cs, "score", None) if cs else None
        if m2_score is not None:
            return ComponentScore(value=float(m2_score), data_completeness=1.0,
                notes="M2.1 deterministic ContentScore.", weight=_WEIGHTS["content_score"])
        wc = getattr(content, "word_count", 0) if content else 0
        return ComponentScore(value=round(min(100.0, (wc / 1000) * 100), 2), data_completeness=0.5,
            notes="Estimated from word count.", weight=_WEIGHTS["content_score"])

    def _keyword_component(self, ko):
        if ko is None:
            return ComponentScore(value=0.0, data_completeness=0.0, notes="No KO.", weight=_WEIGHTS["keyword_score"])
        kw = getattr(ko, "keyword_intelligence", None)
        focus = getattr(kw, "primary_focus_keyphrase", None) if kw else None
        if not focus:
            return ComponentScore(value=0.0, data_completeness=1.0, notes="No focus keyphrase.", weight=_WEIGHTS["keyword_score"])
        placement = getattr(kw, "keyword_placement", None) if kw else None
        if placement is None:
            return ComponentScore(value=50.0, data_completeness=0.5, notes="Placement not assessed.", weight=_WEIGHTS["keyword_score"])
        signals = [getattr(placement, k, False) for k in
                   ("in_title","in_h1","in_first_100_words","in_meta_description","in_url")]
        score = (sum(signals) / len(signals)) * 100
        return ComponentScore(value=round(score, 2), data_completeness=1.0,
            notes=f"Keyphrase in {sum(signals)}/{len(signals)} locations.", weight=_WEIGHTS["keyword_score"])

    def _link_component(self, page_id, ko, site_arch):
        if site_arch is not None:
            equity = (getattr(site_arch, "link_equity_scores", {}) or {}).get(page_id)
            if equity is not None:
                return ComponentScore(value=round(float(equity)*100,2), data_completeness=1.0,
                    notes="PageRank link equity.", weight=_WEIGHTS["internal_link_score"])
        if ko is not None:
            internal_seo = getattr(ko, "internal_seo", None)
            inlinks = getattr(internal_seo, "internal_links", []) if internal_seo else []
            return ComponentScore(value=min(100.0, len(inlinks)*20), data_completeness=0.5,
                notes=f"{len(inlinks)} inlinks estimate.", weight=_WEIGHTS["internal_link_score"])
        return ComponentScore(value=0.0, data_completeness=0.0, notes="No link data.", weight=_WEIGHTS["internal_link_score"])

    def _authority_component(self, options):
        ext = (options or {}).get("authority_score")
        completeness = float((options or {}).get("authority_data_completeness", 0.0))
        if ext is not None:
            return ComponentScore(value=round(float(ext)*100,2), data_completeness=completeness,
                notes=f"From upstream engines (completeness={completeness:.0%}).", weight=_WEIGHTS["authority_score"])
        return ComponentScore(value=0.0, data_completeness=0.0,
            notes="Authority unavailable (fake provider data).", weight=_WEIGHTS["authority_score"])

    def _accessibility_component(self, ko):
        if ko is None:
            return ComponentScore(value=0.0, data_completeness=0.0, notes="No KO.", weight=_WEIGHTS["accessibility_score"])
        images_section = getattr(ko, "image_intelligence", None)
        images = getattr(images_section, "images", []) if images_section else []
        if not images:
            return ComponentScore(value=100.0, data_completeness=1.0, notes="No images.", weight=_WEIGHTS["accessibility_score"])
        with_alt = sum(1 for i in images if (getattr(i,"current_alt_text",None) or "").strip())
        return ComponentScore(value=round((with_alt/len(images))*100,2), data_completeness=1.0,
            notes=f"{with_alt}/{len(images)} images have alt.", weight=_WEIGHTS["accessibility_score"])

    def _trust_component(self, ko):
        if ko is None:
            return ComponentScore(value=0.0, data_completeness=0.0, notes="No KO.", weight=_WEIGHTS["trust_score"])
        eeat = getattr(ko, "eeat", None)
        if eeat is None:
            return ComponentScore(value=50.0, data_completeness=0.5, notes="EEAT not assessed.", weight=_WEIGHTS["trust_score"])
        signals = getattr(eeat, "trust_signals", []) or []
        contact = getattr(eeat, "contact_info_present", False)
        org = getattr(eeat, "organization_info_present", False)
        score = min(100.0, len(signals)*15 + (25 if contact else 0) + (25 if org else 0))
        return ComponentScore(value=round(score,2), data_completeness=1.0,
            notes=f"{len(signals)} trust signals.", weight=_WEIGHTS["trust_score"])

    @staticmethod
    def _weighted_overall(components):
        total_w = 0.0
        ws = 0.0
        for comp in components.values():
            ew = comp.weight * comp.data_completeness
            ws += comp.value * ew
            total_w += ew
        if total_w == 0.0:
            return 0.0
        return round(ws / total_w, 2)
