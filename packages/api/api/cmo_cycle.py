"""Portfolio coordinator for the autonomous Chief Marketing Officer.

This layer binds the pure Executive Brain to durable website memory and the
connected-site portfolio. It does not execute live changes itself: callers pass
specialist analysis produced by the governed loop, preserving the canonical
SENSE -> ANALYZE -> PRIORITIZE -> PLAN -> GOVERN -> EXECUTE -> VERIFY -> LEARN
boundary.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from api import agent_loop
from api import executive_brain
from api.cmo_memory import CMOMemoryStore, memory_store_for_app, provider_descriptor

__all__ = ["CMOCoordinator", "coordinator_for_app"]


def _domain(value: str) -> str:
    raw = (value or "").strip()
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    host = (parsed.hostname or raw).lower().strip("/")
    return host[4:] if host.startswith("www.") else host


def _same_site(left: str, right: str) -> bool:
    """Require matching hosts and compatible configured path prefixes."""
    if not left or not right:
        return False
    first = urlparse(left if "://" in left else f"https://{left}")
    second = urlparse(right if "://" in right else f"https://{right}")
    if _domain(left) != _domain(right):
        return False
    first_path = (first.path or "/").rstrip("/") or "/"
    second_path = (second.path or "/").rstrip("/") or "/"
    return first_path == second_path


def _configured_publisher_url() -> str:
    try:
        from core.config import get_settings

        return str(get_settings().wp_base_url or "")
    except Exception:  # noqa: BLE001 - absence means live execution is unsafe
        return ""


class CMOCoordinator:
    """Tenant/site-safe bridge between onboarding, memory, and brain."""

    def __init__(self, app: Any, store: CMOMemoryStore | None = None) -> None:
        self.app = app
        self.store = store or memory_store_for_app(app)
        onboarding = getattr(getattr(app, "state", None), "onboarding", None)
        self._onboarding = onboarding if isinstance(onboarding, dict) else {}
        self._repo = self._onboarding.get("repository")

    def configured_tenant(self) -> str:
        tenant = self._onboarding.get("tenant_id")
        if tenant:
            return str(tenant)
        try:
            return str(self.app.state.subsystems.tenant_id)
        except Exception:  # noqa: BLE001
            return "demo-tenant"

    def connected_sites(self, tenant_id: str | None = None) -> list[dict]:
        """Discover every verified site and explain its CMO eligibility."""
        tenant = tenant_id or self.configured_tenant()
        if self._repo is None:
            return []
        websites = self._repo.list_connected_websites(tenant)

        sites: list[dict] = []
        for website in websites:
            try:
                connections = self._repo.list_connections(tenant, website.id)
            except Exception:  # noqa: BLE001
                connections = []
            capabilities: dict[str, bool] = {}
            for connection in connections:
                if not getattr(connection, "is_active", False):
                    continue
                for name, allowed in (getattr(connection, "capabilities", None) or {}).items():
                    capabilities[str(name)] = capabilities.get(str(name), False) or bool(allowed)

            ai_enabled = bool(getattr(website, "ai_enabled", False))
            memory_enabled = bool(getattr(website, "memory_enabled", False))
            automation_enabled = bool(getattr(website, "automation_enabled", False))
            reasons: list[str] = []
            if not ai_enabled:
                reasons.append("ai_disabled")
            if not memory_enabled:
                reasons.append("memory_disabled")
            eligible = not reasons
            requested_mode = agent_loop.normalize_mode(getattr(website, "approval_mode", None))
            # The current composition root owns one configured publisher. Fail
            # closed for every other connected site until publishing is resolved
            # from that website's encrypted connection at execution time.
            publisher_bound = (
                bool(capabilities.get("publish"))
                and bool(capabilities.get("rollback"))
                and _same_site(str(website.url), _configured_publisher_url())
            )
            effective_mode = requested_mode
            if requested_mode == agent_loop.AUTONOMOUS and not automation_enabled:
                effective_mode = agent_loop.APPROVAL
                reasons.append("autonomous_execution_disabled")
            if requested_mode == agent_loop.AUTONOMOUS and not publisher_bound:
                effective_mode = agent_loop.APPROVAL
                reasons.append("site_bound_publisher_unavailable")

            config = getattr(website, "agent_config", None) or {}
            schedule = config.get("executive_cmo_schedule", {}) if isinstance(config, dict) else {}
            cadence = int(schedule.get("cadence_seconds") or 86400)
            sites.append({
                "tenant_id": tenant,
                "website_id": website.id,
                "domain": _domain(website.url),
                "url": website.url,
                "name": website.display_name or website.name,
                "mode": effective_mode,
                "requested_mode": requested_mode,
                "cadence_seconds": max(300, cadence),
                "crawl": bool(capabilities.get("crawl", capabilities.get("read", True))),
                "eligible": eligible,
                "skip_reason": ",".join(reasons) if not eligible else None,
                "policy_notes": reasons,
                "publisher_bound": publisher_bound,
                "can_execute_live": bool(
                    eligible
                    and effective_mode == agent_loop.AUTONOMOUS
                    and automation_enabled
                    and publisher_bound
                ),
                "ai_enabled": ai_enabled,
                "memory_enabled": memory_enabled,
                "automation_enabled": automation_enabled,
                "capabilities": capabilities,
                "discovered": True,
            })
        return sites

    def site_policy(
        self,
        *,
        tenant_id: str,
        website_id: str | None,
        requested_mode: str | None = None,
    ) -> dict:
        """Resolve a fail-closed policy; callers may lower but never escalate it."""
        requested = agent_loop.normalize_mode(requested_mode)
        if not website_id:
            # An arbitrary domain has no persisted governance/connection context.
            # It may be analyzed and prepared, but never autonomously published.
            mode = agent_loop.APPROVAL if requested == agent_loop.AUTONOMOUS else requested
            return {
                "allowed": True,
                "connected": False,
                "mode": mode,
                "requested_mode": requested,
                "publisher_bound": False,
                "can_execute_live": False,
                "reason": "unconnected_target_cannot_autonomously_publish",
            }
        site = next(
            (entry for entry in self.connected_sites(tenant_id) if entry["website_id"] == website_id),
            None,
        )
        if site is None:
            return {
                "allowed": False,
                "connected": False,
                "mode": agent_loop.ADVISORY,
                "requested_mode": requested,
                "publisher_bound": False,
                "can_execute_live": False,
                "reason": "website_has_no_active_verified_connection",
            }
        rank = {agent_loop.ADVISORY: 0, agent_loop.APPROVAL: 1, agent_loop.AUTONOMOUS: 2}
        persisted_cap = str(site["mode"])
        requested_for_site = (
            agent_loop.normalize_mode(requested_mode)
            if requested_mode is not None
            else persisted_cap
        )
        effective = requested_for_site if rank[requested_for_site] <= rank[persisted_cap] else persisted_cap
        return {
            "allowed": bool(site["eligible"]),
            "connected": True,
            "mode": effective,
            "requested_mode": requested_for_site,
            "persisted_mode": site["requested_mode"],
            "publisher_bound": bool(site["publisher_bound"]),
            "can_execute_live": bool(site["can_execute_live"] and effective == agent_loop.AUTONOMOUS),
            "reason": site.get("skip_reason") or ",".join(site.get("policy_notes", [])) or None,
            "website_id": website_id,
        }

    def memory(
        self,
        *,
        tenant_id: str,
        site: str,
        website_id: str | None = None,
    ) -> dict:
        return self.store.load(tenant_id=tenant_id, site=site, website_id=website_id)

    def update_profile(
        self,
        *,
        tenant_id: str,
        site: str,
        profile: dict,
        website_id: str | None = None,
    ) -> dict:
        memory = self.store.update_profile(
            tenant_id=tenant_id,
            site=site,
            website_id=website_id,
            profile=profile,
        )
        goals = memory.get("business_goals", {})
        executive_brain.set_goals(
            tenant_id,
            site,
            str(goals.get("primary") or "traffic"),
            str(goals.get("description") or ""),
        )
        return self.store.public_view(memory)

    def assess(
        self,
        *,
        tenant_id: str,
        site: str,
        analysis: dict,
        website_id: str | None = None,
        mode: str | None = None,
        cycle_id: str | None = None,
        requested_goals: dict | None = None,
    ) -> dict:
        """Create, persist, and return one complete CMO assessment."""
        memory = self.store.load(tenant_id=tenant_id, site=site, website_id=website_id)
        saved_goals = memory.get("business_goals", {})
        source = requested_goals or saved_goals
        goals = executive_brain.set_goals(
            tenant_id,
            site,
            str(source.get("primary") or "traffic"),
            str(source.get("description") or ""),
        )
        provider = provider_descriptor(self.app)
        assessment = executive_brain.assess(
            site=site,
            tenant=tenant_id,
            analysis=analysis,
            goals=goals,
            memory=memory,
            provider=provider,
            website_id=website_id,
        )
        saved = self.store.record_assessment(
            tenant_id=tenant_id,
            site=site,
            website_id=website_id,
            assessment=assessment,
            provider=provider,
            cycle_id=cycle_id,
            mode=mode,
        )
        assessment["changes"] = saved.get("latest_changes", [])
        assessment["memory"] = self.store.public_view(saved)
        assessment["governance"] = {
            "mode": agent_loop.normalize_mode(mode),
            "website_id": website_id,
            "audited": True,
            "live_writes_require_governance": True,
        }
        return assessment

    def record_mission_result(
        self,
        *,
        tenant_id: str,
        site: str,
        mission: dict,
        successful: bool,
        metric_delta: float = 0.0,
        website_id: str | None = None,
        evidence: str = "",
    ) -> dict:
        memory = self.store.record_strategy_outcome(
            tenant_id=tenant_id,
            site=site,
            website_id=website_id,
            category=str(mission.get("category") or "unknown"),
            title=str(mission.get("title") or "Mission"),
            successful=successful,
            metric_delta=metric_delta,
            mission_id=mission.get("id"),
            evidence=evidence,
        )
        return self.store.public_view(memory)

    def queue_mission_verification(
        self, *, tenant_id: str, site: str, mission: dict, website_id: str | None = None,
    ) -> dict:
        """Register a just-applied mission for Continuous Learning (item 8):
        its real category metric is measured again once the observation
        window elapses, and the outcome is fed back automatically on the next
        governed cycle via :meth:`resolve_mission_verifications`."""
        memory = self.store.queue_mission_verification(
            tenant_id=tenant_id, site=site, website_id=website_id, mission=mission,
        )
        return self.store.public_view(memory)

    def resolve_mission_verifications(
        self, *, tenant_id: str, site: str, website_id: str | None = None,
    ) -> list[dict]:
        """Verify every due mission against the current real metric snapshot
        and feed learned outcomes back into strategy_stats (Continuous
        Learning, item 8). Called once per governed cycle (see
        ``_make_cycle_fn`` in agent_router.py) so learning never depends on a
        human remembering to check back in."""
        return self.store.resolve_pending_verifications(
            tenant_id=tenant_id, site=site, website_id=website_id,
        )


def coordinator_for_app(app: Any) -> CMOCoordinator:
    return CMOCoordinator(app)
