"""Governed continuous reasoning loop — the DME core (Phase A vertical).

This module holds the *pure, reusable* pieces of the continuous reasoning loop
described in the ``autonomous-marketing-executive`` steering doc, so that the
agent router can compose them into the canonical cycle for a connected site:

    SENSE      -> engines audit (+ optional live crawl -> persisted fixes)
    ANALYZE    -> findings
    PRIORITIZE -> rank actions/opportunities by business impact / ROI   (here)
    PLAN       -> ordered action list                                    (here)
    GOVERN     -> per-site mode gate: advisory | approval | autonomous   (here)
    EXECUTE    -> governed apply (governance -> publishing)  (router, real)
    VERIFY     -> re-audit health delta                      (router)
    LEARN      -> persist an outcome record                  (here)

Design rules honoured (see steering doc §7):
* Governed autonomy — the mode gate below decides advisory/approval/autonomous.
* Prioritise by business impact / ROI — :func:`prioritize` and
  :func:`build_opportunities`.
* Explainability — every opportunity carries reasoning + expected impact.
* Learn from outcomes — :data:`OUTCOMES` + :func:`record_outcome`.
* Provider-agnostic — nothing here binds a specific LLM/provider.
* Multi-tenant / multi-site — everything is keyed by tenant + site.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

__all__ = [
    "ADVISORY",
    "APPROVAL",
    "AUTONOMOUS",
    "VALID_MODES",
    "normalize_mode",
    "score_impact",
    "prioritize",
    "govern_actions",
    "build_opportunities",
    "record_outcome",
    "list_outcomes",
    "resolve_site_mode",
]


# --------------------------------------------------------------------------- #
# Governance modes (per-site) — the gate on every action
# --------------------------------------------------------------------------- #
ADVISORY = "advisory"
APPROVAL = "approval"
AUTONOMOUS = "autonomous"
VALID_MODES = frozenset({ADVISORY, APPROVAL, AUTONOMOUS})

# Accept both the canonical modes and the legacy UI "autonomy" vocabulary.
_MODE_ALIASES = {
    "advisory": ADVISORY,
    "recommend": ADVISORY,
    "recommendation": ADVISORY,
    "approval": APPROVAL,
    "approve": APPROVAL,
    "supervised": APPROVAL,
    "manual": APPROVAL,
    "human": APPROVAL,
    "scheduled": APPROVAL,
    "autonomous": AUTONOMOUS,
    "auto": AUTONOMOUS,
    "auto_safe": AUTONOMOUS,
    "automatic": AUTONOMOUS,
}


def normalize_mode(value: str | None) -> str:
    """Map any accepted mode/autonomy string to a canonical governance mode.

    Defaults to the safe ``approval`` mode for unknown/empty input.
    """
    if not value:
        return APPROVAL
    return _MODE_ALIASES.get(str(value).strip().lower(), APPROVAL)


# --------------------------------------------------------------------------- #
# Business-impact / ROI scoring (PRIORITIZE)
# --------------------------------------------------------------------------- #
_SEVERITY_WEIGHT = {
    "critical": 100,
    "high": 80,
    "medium": 55,
    "low": 30,
    "info": 15,
}
_CATEGORY_WEIGHT = {
    "technical_seo": 1.0,
    "crawl": 1.0,
    "content": 0.85,
    "performance": 0.9,
    "system": 0.2,
}
# Effort proxy from the action's risk band — lower effort ⇒ higher ROI.
_EFFORT = {"low": 0.8, "medium": 1.0, "review": 1.2, "high": 1.3}


def _severity_of(action: dict) -> str:
    sev = (action.get("severity") or "").lower()
    if sev in _SEVERITY_WEIGHT:
        return sev
    # Fall back to inferring severity from the risk band.
    risk = (action.get("risk") or "").lower()
    return {"review": "high", "medium": "medium", "low": "low"}.get(risk, "medium")


def score_impact(action: dict) -> tuple[int, str]:
    """Return ``(impact_score, impact_label)`` for a proposed action.

    Impact rises with severity and category weight and falls with effort, so a
    high-severity, low-effort fix (the classic quick win) ranks highest — this
    is the "prioritise by business impact / ROI" rule made concrete.
    """
    severity = _severity_of(action)
    base = _SEVERITY_WEIGHT.get(severity, 40)
    cat = _CATEGORY_WEIGHT.get((action.get("category") or "technical_seo"), 0.8)
    effort = _EFFORT.get((action.get("risk") or "medium").lower(), 1.0)
    score = int(round(base * cat / effort))
    label = "high" if score >= 70 else "medium" if score >= 40 else "low"
    return score, label


def prioritize(actions: list[dict]) -> list[dict]:
    """Annotate each action with impact and return them ranked, highest first."""
    for a in actions:
        score, label = score_impact(a)
        a["impact_score"] = score
        a["impact"] = label
    return sorted(actions, key=lambda a: a.get("impact_score", 0), reverse=True)


# --------------------------------------------------------------------------- #
# Explainable opportunity backlog
# --------------------------------------------------------------------------- #
_EXPECTED_IMPACT = {
    "critical": "Removing this unblocks indexing/ranking and can materially lift organic traffic.",
    "high": "Resolving this should improve rankings and crawlability within a few weeks.",
    "medium": "A solid on-page win that compounds with the other fixes.",
    "low": "A quick hygiene win with low effort.",
    "info": "Informational — worth monitoring.",
}


def build_opportunities(findings: list[dict], actions: list[dict]) -> list[dict]:
    """Turn the highest-impact actions into an explainable opportunity backlog.

    Each opportunity carries the *what*, *why*, *expected impact* and the
    *evidence* (the finding it came from) — satisfying the explainability rule.
    """
    opportunities: list[dict] = []
    for a in actions:
        severity = _severity_of(a)
        opportunities.append(
            {
                "id": uuid.uuid4().hex[:12],
                "title": a.get("title", "Opportunity"),
                "category": a.get("category", "technical_seo"),
                "impact": a.get("impact", "medium"),
                "impact_score": a.get("impact_score", 0),
                "recommendation": a.get("after") or a.get("description", ""),
                "expected_impact": _EXPECTED_IMPACT.get(severity, _EXPECTED_IMPACT["medium"]),
                "evidence": a.get("detail") or a.get("title", ""),
                "action_id": a.get("id"),
            }
        )
    return opportunities


# --------------------------------------------------------------------------- #
# Governance gate (GOVERN)
# --------------------------------------------------------------------------- #
def govern_actions(actions: list[dict], mode: str) -> dict:
    """Apply the per-site governance disposition to each action in place.

    Returns a small policy summary describing what the mode permits. This is the
    single gate that decides advisory-vs-prepared-vs-auto-applied; the router
    performs the actual (audited, reversible) execution for autonomous mode.
    """
    mode = normalize_mode(mode)
    if mode == ADVISORY:
        for a in actions:
            a["status"] = "advisory"
            a["requires_approval"] = True
            a["governance"] = "advisory: recommendation only, no change prepared"
        return {"mode": ADVISORY, "prepares_changes": False, "auto_applies": False,
                "note": "Recommendations only — nothing is prepared or applied."}
    if mode == AUTONOMOUS:
        for a in actions:
            a.setdefault("status", "proposed")
            low = (a.get("risk") or "").lower() == "low"
            a["requires_approval"] = not low
            a["governance"] = (
                "autonomous: low-risk auto-applied within policy"
                if low else "autonomous: high-risk still needs human approval"
            )
        return {"mode": AUTONOMOUS, "prepares_changes": True, "auto_applies": True,
                "auto_apply_policy": "risk == low",
                "note": "Low-risk actions auto-applied through governance; high-risk await approval."}
    # APPROVAL (default, safe)
    for a in actions:
        a.setdefault("status", "proposed")
        a["requires_approval"] = True
        a["governance"] = "approval: prepared, awaits human approval before going live"
    return {"mode": APPROVAL, "prepares_changes": True, "auto_applies": False,
            "note": "Concrete changes prepared; a human approves before anything goes live."}


# --------------------------------------------------------------------------- #
# Outcomes / learning store (LEARN)
# --------------------------------------------------------------------------- #
# In-process learning substrate. Durable per-fix history still lives in the
# Digital_Twin audit trail; this records loop-level outcomes for prioritisation
# and confidence over time.
OUTCOMES: list[dict] = []


def record_outcome(
    *,
    run_id: str,
    tenant_id: str,
    site: str,
    mode: str,
    actions_proposed: int,
    actions_applied: int,
    actions_accepted: int,
    health_before: float,
    health_after: float,
    top_opportunity: str | None,
) -> dict:
    """Persist a loop outcome so future cycles can learn from what happened."""
    delta = round(float(health_after) - float(health_before), 2)
    outcome = {
        "id": uuid.uuid4().hex[:12],
        "run_id": run_id,
        "tenant_id": tenant_id,
        "site": site,
        "mode": mode,
        "actions_proposed": actions_proposed,
        "actions_applied": actions_applied,
        "actions_accepted": actions_accepted,
        "health_before": round(float(health_before), 1),
        "health_after": round(float(health_after), 1),
        "health_delta": delta,
        "top_opportunity": top_opportunity,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    OUTCOMES.append(outcome)
    return outcome


def list_outcomes(tenant_id: str | None = None, site: str | None = None) -> list[dict]:
    """Return recorded outcomes, newest first, optionally scoped to a site."""
    rows = OUTCOMES
    if tenant_id:
        rows = [o for o in rows if o["tenant_id"] == tenant_id]
    if site:
        rows = [o for o in rows if o["site"] == site]
    return sorted(rows, key=lambda o: o["recorded_at"], reverse=True)


# --------------------------------------------------------------------------- #
# Per-site governance mode resolution (best-effort, from onboarding)
# --------------------------------------------------------------------------- #
def resolve_site_mode(request: Any, website_id: str) -> str | None:
    """Best-effort read of a connected website's ``approval_mode``.

    Returns the normalized governance mode for the site, or ``None`` if it
    cannot be resolved (so the caller falls back to an explicit/default mode).
    Never raises — a wiring/DB issue must not break a run.
    """
    if not website_id:
        return None
    try:
        from core.config import get_settings
        from digital_twin.db import create_db_engine, make_session_factory
        from onboarding.repository import OnboardingRepository

        settings = get_settings()
        engine = create_db_engine(settings.database_url)
        session_factory = make_session_factory(engine)
        repo = OnboardingRepository(session_factory, tenant_id=settings.tenant_id)
        website = repo.get_website(settings.tenant_id, website_id)
        mode = getattr(website, "approval_mode", None) if website else None
        return normalize_mode(mode) if mode else None
    except Exception:  # noqa: BLE001 - best-effort; fall back to explicit/default
        return None
