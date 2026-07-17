"""Durable, tenant/site-scoped memory for the autonomous Executive CMO.

The canonical persisted document lives under ``Website.agent_config`` so it
shares the website's lifecycle and tenant boundary without introducing a
second source of site identity. Histories are deliberately bounded: this is a
strategic memory/index, not an analytics warehouse. Full action provenance and
rollback history remain in the existing onboarding and Digital Twin audits.

When no connected Website repository is available (unit tests, ad-hoc domain
analysis, or memory disabled by site policy), the same document is kept in a
process-local fallback. Callers can inspect ``storage`` to distinguish durable
and ephemeral state and must never describe the fallback as durable.
"""
from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

__all__ = [
    "CMOMemoryStore",
    "MEMORY_KEY",
    "SCHEMA_VERSION",
    "default_memory",
    "detect_changes",
    "extract_metric",
    "memory_store_for_app",
    "metric_for_category",
    "provider_descriptor",
    "strategy_adjustment",
]

MEMORY_KEY = "executive_cmo"
SCHEMA_VERSION = 1
_MAX_PERFORMANCE = 104
_MAX_CYCLES = 104
_MAX_STRATEGIES = 100
_MAX_CONTENT_HISTORY = 250
_MAX_VALUE_TEXT = 4096
_MAX_PENDING_VERIFICATIONS = 200
#: How long a mission's real-world effect is given to show up in the next
#: measured snapshot before it is verified (Milestone 5 — Continuous Learning).
_VERIFICATION_WINDOW_SECONDS = 24 * 3600
_PROFILE_LIST_LIMITS = {
    "products_services": 100,
    "competitors": 100,
    "target_keywords": 200,
    "seasonal_opportunities": 100,
    "content_history": _MAX_CONTENT_HISTORY,
    "published_pages": 500,
    "published_blogs": 500,
    "internal_link_map": 2000,
    "conversion_funnels": 100,
}

_FALLBACK: dict[str, dict] = {}
_MAX_FALLBACK_SITES = 500


def _remember_fallback(key: str, memory: dict) -> None:
    _FALLBACK.pop(key, None)
    _FALLBACK[key] = deepcopy(memory)
    while len(_FALLBACK) > _MAX_FALLBACK_SITES:
        _FALLBACK.pop(next(iter(_FALLBACK)))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _key(tenant_id: str, site: str, website_id: str | None = None) -> str:
    return f"{tenant_id}::{website_id or site}".strip().lower()


def _bounded(items: list[Any], limit: int) -> list[Any]:
    return items[-limit:]


def _sanitize(value: Any, *, list_limit: int = 100, depth: int = 0) -> Any:
    """Bound user/business context before placing it in the Website JSON row."""
    if depth >= 5:
        return str(value)[:_MAX_VALUE_TEXT]
    if isinstance(value, str):
        return value[:_MAX_VALUE_TEXT]
    if isinstance(value, list):
        return [
            _sanitize(item, list_limit=list_limit, depth=depth + 1)
            for item in value[-list_limit:]
        ]
    if isinstance(value, dict):
        return {
            str(key)[:128]: _sanitize(item, list_limit=list_limit, depth=depth + 1)
            for key, item in list(value.items())[:100]
        }
    return deepcopy(value)


def _deep_defaults(value: Any, defaults: Any) -> Any:
    """Apply schema defaults without discarding future/unknown memory keys."""
    if not isinstance(defaults, dict):
        return deepcopy(value if value is not None else defaults)
    source = value if isinstance(value, dict) else {}
    result = deepcopy(source)
    for key, default in defaults.items():
        result[key] = _deep_defaults(source.get(key), default)
    return result


def default_memory(*, tenant_id: str, site: str, website_id: str | None = None) -> dict:
    """Return the complete v1 CMO memory schema for one website."""
    return {
        "schema_version": SCHEMA_VERSION,
        "tenant_id": tenant_id,
        "website_id": website_id,
        "site": site,
        "storage": "ephemeral",
        "created_at": _now(),
        "updated_at": _now(),
        "business_goals": {"primary": "traffic", "description": ""},
        "brand_identity": {},
        "products_services": [],
        "target_audience": {},
        "competitors": [],
        "target_keywords": [],
        "business_category": "",
        "country": "",
        "language": "en",
        "timezone": "UTC",
        "historical_performance": [],
        "successful_strategies": [],
        "failed_strategies": [],
        "seasonal_opportunities": [],
        "content_history": [],
        "published_pages": [],
        "published_blogs": [],
        "internal_link_map": [],
        "conversion_funnels": [],
        "strategy_stats": {},
        "latest_snapshot": {},
        "latest_changes": [],
        "current_roadmap": {
            "daily": [],
            "weekly": [],
            "monthly": [],
            "quarterly": [],
            "annual": [],
            "capacity": {},
        },
        "cycle_history": [],
        "provider": {
            "route": "provider-agnostic-intelligence-gateway",
            "selected": "deterministic",
            "available": False,
        },
        # Milestone 5 — Continuous Learning: missions awaiting their
        # measurement window before an outcome can be attributed and fed back
        # into strategy_stats. See queue_mission_verification/resolve_pending_verifications.
        "pending_verifications": [],
    }


def _snapshot(assessment: dict) -> dict:
    scores = assessment.get("scores", {})
    components = scores.get("components", {})
    backlog = assessment.get("backlog", [])
    return {
        "recorded_at": assessment.get("generated_at") or _now(),
        "health_score": float(scores.get("health_score", 0) or 0),
        "seo_score": float(scores.get("seo_score", 0) or 0),
        "marketing_score": float(scores.get("marketing_score", 0) or 0),
        "components": {
            str(name): float(value or 0) for name, value in components.items()
            if isinstance(value, (int, float))
        },
        "competitor_gaps": int(scores.get("competitor_gaps", 0) or 0),
        "mission_count": len(backlog),
        "mission_categories": sorted({str(m.get("category", "unknown")) for m in backlog}),
        "top_mission": backlog[0].get("title") if backlog else None,
        "top_priority": float(backlog[0].get("priority_score", 0) or 0) if backlog else 0,
    }


def detect_changes(previous: dict | None, current: dict) -> list[dict]:
    """Explain material site-condition changes between two CMO observations."""
    if not previous:
        return [{
            "metric": "baseline",
            "before": None,
            "after": current.get("marketing_score", 0),
            "delta": None,
            "direction": "baseline",
            "material": True,
        }]

    changes: list[dict] = []
    metrics = ("health_score", "seo_score", "marketing_score", "competitor_gaps", "mission_count")
    for metric in metrics:
        before = float(previous.get(metric, 0) or 0)
        after = float(current.get(metric, 0) or 0)
        delta = round(after - before, 2)
        threshold = 1.0 if metric.endswith("score") else 0.0
        if abs(delta) > threshold:
            changes.append({
                "metric": metric,
                "before": before,
                "after": after,
                "delta": delta,
                "direction": "improved" if delta > 0 else "declined",
                "material": abs(delta) >= (5.0 if metric.endswith("score") else 1.0),
            })

    old_components = previous.get("components", {}) if isinstance(previous.get("components"), dict) else {}
    for name, value in current.get("components", {}).items():
        before = float(old_components.get(name, value) or 0)
        after = float(value or 0)
        delta = round(after - before, 2)
        if abs(delta) > 1.0:
            changes.append({
                "metric": f"component.{name}",
                "before": before,
                "after": after,
                "delta": delta,
                "direction": "improved" if delta > 0 else "declined",
                "material": abs(delta) >= 5.0,
            })
    return changes


def strategy_adjustment(memory: dict | None, category: str) -> dict:
    """Return a bounded priority/confidence adjustment learned from outcomes.

    Laplace smoothing keeps a new strategy neutral and prevents one lucky or
    unlucky result from dominating the roadmap.
    """
    stats = (memory or {}).get("strategy_stats", {}).get(category, {})
    successes = int(stats.get("successful", 0) or 0)
    failures = int(stats.get("failed", 0) or 0)
    samples = successes + failures
    if samples == 0:
        return {"multiplier": 1.0, "confidence_delta": 0.0, "samples": 0, "success_rate": None}
    rate = (successes + 1) / (samples + 2)
    strength = min(1.0, samples / 8.0)
    multiplier = 1.0 + (rate - 0.5) * 0.30 * strength
    confidence_delta = (rate - 0.5) * 0.20 * strength
    return {
        "multiplier": round(max(0.85, min(1.15, multiplier)), 3),
        "confidence_delta": round(max(-0.10, min(0.10, confidence_delta)), 3),
        "samples": samples,
        "success_rate": round(rate, 3),
    }


#: Missions in these categories are measured against the correspondingly
#: named component of the real, deterministic marketing-score snapshot
#: (see ``_snapshot``/``_compute_scores`` in executive_brain.py) — the only
#: continuously-measured signal available without a connected GSC/GA4
#: integration. Rankings/CTR/traffic/leads/revenue require those external
#: integrations (Section: unavoidable external-integration dependencies).
_CATEGORY_METRIC = {
    "technical_seo": "component.technical_health",
    "crawl": "component.technical_health",
    "health": "component.technical_health",
    "content": "component.content_quality",
    "strategy": "marketing_score",
    "backlinks": "component.backlink_safety",
    "geo": "component.ai_visibility",
    "competitor": "marketing_score",
    "local": "marketing_score",
    "cro": "marketing_score",
}


def extract_metric(snapshot: dict, metric: str) -> float:
    """Read a metric (``"marketing_score"`` or ``"component.<name>"``) out of a
    CMO snapshot dict, defaulting honestly to ``0.0`` when absent."""
    if metric.startswith("component."):
        return float((snapshot.get("components") or {}).get(metric.split(".", 1)[1], 0) or 0)
    return float(snapshot.get(metric, 0) or 0)


def metric_for_category(category: str) -> str:
    """The real, measured metric this mission category is verified against."""
    return _CATEGORY_METRIC.get(category, "marketing_score")


def provider_descriptor(app: Any) -> dict:
    """Describe the configured provider-neutral intelligence route safely."""
    container = getattr(getattr(app, "state", None), "intelligence", None)
    provider = getattr(container, "provider", None)
    if provider is None:
        return {
            "route": "provider-agnostic-intelligence-gateway",
            "selected": "deterministic",
            "available": False,
        }
    try:
        name = provider.name()
    except Exception:  # noqa: BLE001 - metadata must not break a CMO cycle
        name = type(provider).__name__
    return {
        "route": "provider-agnostic-intelligence-gateway",
        "selected": str(name or "configured-provider"),
        "available": True,
    }


class CMOMemoryStore:
    """Read/write the CMO document through the authoritative Website record."""

    def __init__(self, repository: Any | None = None) -> None:
        self._repo = repository

    def _website(self, tenant_id: str, website_id: str | None) -> Any | None:
        if self._repo is None or not website_id:
            return None
        try:
            return self._repo.get_website(tenant_id, website_id)
        except Exception:  # noqa: BLE001 - fallback remains explicitly ephemeral
            return None

    def load(self, *, tenant_id: str, site: str, website_id: str | None = None) -> dict:
        defaults = default_memory(tenant_id=tenant_id, site=site, website_id=website_id)
        website = self._website(tenant_id, website_id)
        if website is not None:
            config = getattr(website, "agent_config", None) or {}
            raw = config.get(MEMORY_KEY) if isinstance(config, dict) else None
            if isinstance(raw, dict):
                memory = _deep_defaults(raw, defaults)
                memory.update({
                    "schema_version": SCHEMA_VERSION,
                    "tenant_id": tenant_id,
                    "website_id": website_id,
                    "site": site,
                    "storage": "durable" if bool(getattr(website, "memory_enabled", False)) else "ephemeral",
                })
                _remember_fallback(_key(tenant_id, site, website_id), memory)
                return memory

        memory = deepcopy(_FALLBACK.get(_key(tenant_id, site, website_id), defaults))
        memory = _deep_defaults(memory, defaults)
        memory.update({"tenant_id": tenant_id, "website_id": website_id, "site": site, "storage": "ephemeral"})
        return memory

    def save(
        self,
        memory: dict,
        *,
        tenant_id: str,
        site: str,
        website_id: str | None = None,
        action: str = "cmo.memory.updated",
        reason: str = "Executive CMO memory updated",
    ) -> dict:
        memory = _deep_defaults(
            memory,
            default_memory(tenant_id=tenant_id, site=site, website_id=website_id),
        )
        memory.update({
            "schema_version": SCHEMA_VERSION,
            "tenant_id": tenant_id,
            "website_id": website_id,
            "site": site,
            "updated_at": _now(),
        })
        fallback_key = _key(tenant_id, site, website_id)
        website = self._website(tenant_id, website_id)
        durable = bool(website is not None and getattr(website, "memory_enabled", False) and self._repo is not None)
        memory["storage"] = "durable" if durable else "ephemeral"
        _remember_fallback(fallback_key, memory)

        if not durable:
            return memory

        existing_config = getattr(website, "agent_config", None) or {}
        config = dict(existing_config) if isinstance(existing_config, dict) else {}
        previous = config.get(MEMORY_KEY, {})
        before_summary = {
            "schema_version": previous.get("schema_version") if isinstance(previous, dict) else None,
            "updated_at": previous.get("updated_at") if isinstance(previous, dict) else None,
            "cycles": len(previous.get("cycle_history", [])) if isinstance(previous, dict) else 0,
        }
        after_summary = {
            "schema_version": SCHEMA_VERSION,
            "updated_at": memory["updated_at"],
            "cycles": len(memory.get("cycle_history", [])),
            "latest_changes": len(memory.get("latest_changes", [])),
        }
        try:
            updated = self._repo.update_agent_config_section_with_audit(
                tenant_id,
                website_id,
                section=MEMORY_KEY,
                value=deepcopy(memory),
                expected_section_updated_at=before_summary["updated_at"],
                actor_id="executive-cmo",
                action=action,
                reason=reason,
                before_value=json.dumps(before_summary, sort_keys=True),
                after_value=json.dumps(after_summary, sort_keys=True),
            )
            if updated is None:
                memory["storage"] = "ephemeral"
                _remember_fallback(fallback_key, memory)
                return memory
        except Exception:  # noqa: BLE001 - stale/concurrent state fails closed
            memory["storage"] = "ephemeral"
            _remember_fallback(fallback_key, memory)
        return memory

    def update_profile(
        self,
        *,
        tenant_id: str,
        site: str,
        website_id: str | None = None,
        profile: dict,
    ) -> dict:
        """Merge user/business context into the long-term profile."""
        memory = self.load(tenant_id=tenant_id, site=site, website_id=website_id)
        editable = {
            "business_goals", "brand_identity", "products_services", "target_audience",
            "competitors", "target_keywords", "business_category", "country", "language",
            "timezone", "seasonal_opportunities", "content_history", "published_pages",
            "published_blogs", "internal_link_map", "conversion_funnels",
        }
        for key in editable:
            if key in profile and profile[key] is not None:
                memory[key] = _sanitize(
                    profile[key],
                    list_limit=_PROFILE_LIST_LIMITS.get(key, 100),
                )
        return self.save(
            memory,
            tenant_id=tenant_id,
            site=site,
            website_id=website_id,
            action="cmo.profile.updated",
            reason="Executive CMO business context updated",
        )

    def record_assessment(
        self,
        *,
        tenant_id: str,
        site: str,
        assessment: dict,
        website_id: str | None = None,
        provider: dict | None = None,
        cycle_id: str | None = None,
        mode: str | None = None,
    ) -> dict:
        """Persist one assessed state, detected changes, and adaptive roadmap."""
        memory = self.load(tenant_id=tenant_id, site=site, website_id=website_id)
        current = _snapshot(assessment)
        changes = detect_changes(memory.get("latest_snapshot"), current)
        memory["business_goals"] = deepcopy(assessment.get("goals", memory["business_goals"]))
        memory["historical_performance"] = _bounded(
            [*memory.get("historical_performance", []), current], _MAX_PERFORMANCE
        )
        memory["latest_snapshot"] = current
        memory["latest_changes"] = changes
        roadmap = assessment.get("roadmap", {})
        memory["current_roadmap"] = {
            "daily": deepcopy(roadmap.get("daily", roadmap.get("today", []))[:50]),
            "weekly": deepcopy(roadmap.get("weekly", roadmap.get("next_7_days", []))[:50]),
            "monthly": deepcopy(roadmap.get("monthly", roadmap.get("next_30_days", []))[:50]),
            "quarterly": deepcopy(roadmap.get("quarterly", roadmap.get("next_90_days", []))[:50]),
            "annual": deepcopy(roadmap.get("annual", roadmap.get("next_365_days", []))[:50]),
            "capacity": deepcopy(roadmap.get("capacity", {})),
        }
        memory["provider"] = deepcopy(provider or memory.get("provider", {}))
        memory["cycle_history"] = _bounded(
            [
                *memory.get("cycle_history", []),
                {
                    "cycle_id": cycle_id,
                    "recorded_at": current["recorded_at"],
                    "mode": mode,
                    "marketing_score": current["marketing_score"],
                    "mission_count": current["mission_count"],
                    "material_changes": sum(1 for c in changes if c.get("material")),
                    "top_mission": current.get("top_mission"),
                },
            ],
            _MAX_CYCLES,
        )
        return self.save(
            memory,
            tenant_id=tenant_id,
            site=site,
            website_id=website_id,
            action="cmo.cycle.assessed",
            reason="Executive CMO completed a change-aware strategic assessment",
        )

    def record_strategy_outcome(
        self,
        *,
        tenant_id: str,
        site: str,
        category: str,
        title: str,
        successful: bool,
        metric_delta: float = 0.0,
        website_id: str | None = None,
        mission_id: str | None = None,
        evidence: str = "",
    ) -> dict:
        """Calibrate future priorities from a verified successful/failed strategy."""
        memory = self.load(tenant_id=tenant_id, site=site, website_id=website_id)
        record = {
            "mission_id": mission_id,
            "title": title,
            "category": category,
            "verified_at": _now(),
            "metric_delta": round(float(metric_delta), 3),
            "evidence": evidence,
        }
        target = "successful_strategies" if successful else "failed_strategies"
        memory[target] = _bounded([*memory.get(target, []), record], _MAX_STRATEGIES)
        stats = dict(memory.get("strategy_stats", {}).get(category, {}))
        stats["attempts"] = int(stats.get("attempts", 0) or 0) + 1
        result_key = "successful" if successful else "failed"
        stats[result_key] = int(stats.get(result_key, 0) or 0) + 1
        stats["cumulative_metric_delta"] = round(
            float(stats.get("cumulative_metric_delta", 0) or 0) + float(metric_delta), 3
        )
        stats["last_verified_at"] = record["verified_at"]
        memory.setdefault("strategy_stats", {})[category] = stats
        return self.save(
            memory,
            tenant_id=tenant_id,
            site=site,
            website_id=website_id,
            action="cmo.strategy.learned",
            reason=f"Executive CMO verified a {'successful' if successful else 'failed'} strategy outcome",
        )

    def queue_mission_verification(
        self,
        *,
        tenant_id: str,
        site: str,
        mission: dict,
        website_id: str | None = None,
    ) -> dict:
        """Register a just-applied mission for post-publish measurement
        (Milestone 5 — Continuous Learning, item 8).

        Records the mission's category, id, and the metric snapshot value at
        the moment of publish; :meth:`resolve_pending_verifications` compares
        that baseline against the metric's value in a later real assessment
        once the observation window has elapsed, and feeds the verified
        outcome back into ``strategy_stats`` via
        :meth:`record_strategy_outcome` — never a fabricated result.
        """
        memory = self.load(tenant_id=tenant_id, site=site, website_id=website_id)
        metric = metric_for_category(str(mission.get("category") or "unknown"))
        baseline = extract_metric(memory.get("latest_snapshot") or {}, metric)
        entry = {
            "mission_id": mission.get("id"),
            "title": str(mission.get("title") or "Mission"),
            "category": str(mission.get("category") or "unknown"),
            "metric": metric,
            "baseline_value": baseline,
            "queued_at": _now(),
        }
        pending = [p for p in memory.get("pending_verifications", []) if p.get("mission_id") != entry["mission_id"]]
        pending.append(entry)
        memory["pending_verifications"] = _bounded(pending, _MAX_PENDING_VERIFICATIONS)
        return self.save(
            memory,
            tenant_id=tenant_id,
            site=site,
            website_id=website_id,
            action="cmo.mission.queued_for_verification",
            reason=f"Mission {entry['mission_id']} queued for post-publish measurement",
        )

    def resolve_pending_verifications(
        self,
        *,
        tenant_id: str,
        site: str,
        website_id: str | None = None,
    ) -> list[dict]:
        """Verify every due mission against the current real metric snapshot
        and feed the outcome back into ``strategy_stats`` (Continuous Learning
        item 8's "after every publication, measure and feed results back").

        A mission is due once ``_VERIFICATION_WINDOW_SECONDS`` has elapsed
        since it was queued. The metric_delta fed back is the real, measured
        change in the mission's own category metric (technical_health,
        content_quality, backlink_safety, ai_visibility, or the composite
        marketing_score) between the queued baseline and now — never a
        simulated number. Ranking/CTR/traffic/leads/revenue verification
        additionally requires a connected Search Console/Analytics/CRM
        integration; until one exists this only measures the deterministic
        engine-derived component the mission actually targeted.
        """
        memory = self.load(tenant_id=tenant_id, site=site, website_id=website_id)
        pending = list(memory.get("pending_verifications", []))
        if not pending:
            return []
        now = datetime.now(timezone.utc)
        current_snapshot = memory.get("latest_snapshot") or {}
        resolved: list[dict] = []
        still_pending: list[dict] = []
        for entry in pending:
            try:
                queued_at = datetime.fromisoformat(str(entry["queued_at"]))
            except (KeyError, ValueError):
                continue
            if (now - queued_at).total_seconds() < _VERIFICATION_WINDOW_SECONDS:
                still_pending.append(entry)
                continue
            after_value = extract_metric(current_snapshot, entry["metric"])
            delta = round(after_value - float(entry.get("baseline_value", 0) or 0), 3)
            successful = delta >= 0
            outcome = self.record_strategy_outcome(
                tenant_id=tenant_id,
                site=site,
                website_id=website_id,
                category=entry["category"],
                title=entry["title"],
                successful=successful,
                metric_delta=delta,
                mission_id=entry.get("mission_id"),
                evidence=f"{entry['metric']} moved {entry.get('baseline_value', 0)} -> {after_value}",
            )
            resolved.append({
                "mission_id": entry.get("mission_id"), "title": entry["title"],
                "category": entry["category"], "metric": entry["metric"],
                "baseline_value": entry.get("baseline_value"), "current_value": after_value,
                "metric_delta": delta, "successful": successful,
            })
            memory = outcome  # record_strategy_outcome already reloaded+saved
        memory["pending_verifications"] = still_pending
        if resolved:
            self.save(
                memory,
                tenant_id=tenant_id,
                site=site,
                website_id=website_id,
                action="cmo.mission.verifications_resolved",
                reason=f"Resolved {len(resolved)} due mission verification(s)",
            )
        return resolved

    @staticmethod
    def public_view(memory: dict) -> dict:
        """Return decision-useful memory without flooding the dashboard."""
        return {
            "schema_version": memory.get("schema_version", SCHEMA_VERSION),
            "storage": memory.get("storage", "ephemeral"),
            "updated_at": memory.get("updated_at"),
            "business_goals": memory.get("business_goals", {}),
            "brand_identity": memory.get("brand_identity", {}),
            "products_services": memory.get("products_services", []),
            "target_audience": memory.get("target_audience", {}),
            "competitors": memory.get("competitors", []),
            "target_keywords": memory.get("target_keywords", []),
            "business_category": memory.get("business_category", ""),
            "country": memory.get("country", ""),
            "language": memory.get("language", "en"),
            "timezone": memory.get("timezone", "UTC"),
            "seasonal_opportunities": memory.get("seasonal_opportunities", []),
            "content_counts": {
                "history": len(memory.get("content_history", [])),
                "pages": len(memory.get("published_pages", [])),
                "blogs": len(memory.get("published_blogs", [])),
                "internal_links": len(memory.get("internal_link_map", [])),
                "funnels": len(memory.get("conversion_funnels", [])),
            },
            "performance_observations": len(memory.get("historical_performance", [])),
            "historical_performance": memory.get("historical_performance", [])[-12:],
            "cycle_history": memory.get("cycle_history", [])[-12:],
            "successful_strategies": memory.get("successful_strategies", [])[-5:],
            "failed_strategies": memory.get("failed_strategies", [])[-5:],
            "strategy_stats": memory.get("strategy_stats", {}),
            "latest_changes": memory.get("latest_changes", []),
            "cycle_count": len(memory.get("cycle_history", [])),
            "provider": memory.get("provider", {}),
            "pending_verifications": memory.get("pending_verifications", []),
        }


def memory_store_for_app(app: Any) -> CMOMemoryStore:
    onboarding = getattr(getattr(app, "state", None), "onboarding", None)
    repository = onboarding.get("repository") if isinstance(onboarding, dict) else None
    return CMOMemoryStore(repository)
