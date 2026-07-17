"""Continuous, portfolio-aware cadence scheduler for the Executive CMO.

The scheduler is off by default unless explicitly started (or enabled in
configuration by the composition root). Once running, it periodically discovers
verified onboarding websites, keeps tenant/website identity on every job, and
invokes one governed CMO cycle when each eligible site is due.

It owns cadence only. Governance and execution remain in the canonical cycle.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Callable

__all__ = ["AgentScheduler", "get_scheduler"]

CycleFn = Callable[[dict], dict]
DiscoveryFn = Callable[[], list[dict]]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normal(value: str) -> str:
    return (value or "").strip().lower()


def _site_key(domain: str, tenant_id: str = "", website_id: str = "") -> str:
    identity = website_id or _normal(domain)
    return f"{_normal(tenant_id) or 'default'}::{_normal(identity)}"


class AgentScheduler:
    """A process-local cadence driver with durable site state in CMO memory."""

    def __init__(self) -> None:
        self._sites: dict[str, dict] = {}
        self._inflight: set[str] = set()
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._cycle_fn: CycleFn | None = None
        self._discovery_fn: DiscoveryFn | None = None
        self._started_at: str | None = None
        self._last_discovery: str | None = None
        self._next_discovery = 0.0
        self._poll_seconds = 5.0
        self._discovery_seconds = 300.0

    def register(
        self,
        domain: str,
        *,
        mode: str = "approval",
        cadence_seconds: int = 900,
        crawl: bool = False,
        tenant_id: str = "",
        website_id: str = "",
        url: str = "",
        name: str = "",
        eligible: bool = True,
        skip_reason: str | None = None,
        discovered: bool = False,
        **metadata: object,
    ) -> dict:
        key = _site_key(domain, tenant_id, website_id)
        if not _normal(domain):
            raise ValueError("domain is required")
        cadence = max(15, int(cadence_seconds or 900))
        with self._lock:
            existing = self._sites.get(key, {})
            site = {
                "key": key,
                "domain": _normal(domain),
                "url": url or domain,
                "name": name or domain,
                "tenant_id": tenant_id,
                "website_id": website_id,
                "mode": mode,
                "cadence_seconds": cadence,
                "crawl": bool(crawl),
                "eligible": bool(eligible),
                "skip_reason": skip_reason,
                "discovered": bool(discovered),
                "runs": existing.get("runs", 0),
                "last_run": existing.get("last_run"),
                "last_outcome": existing.get("last_outcome"),
                "next_due": existing.get("next_due", time.monotonic()),
                "metadata": dict(metadata),
            }
            self._sites[key] = site
            return self._public_site(site)

    def _find_key(self, identifier: str, tenant_id: str = "") -> str | None:
        normalized = _normal(identifier)
        with self._lock:
            if identifier in self._sites:
                candidate = self._sites[identifier]
                if not tenant_id or candidate.get("tenant_id") == tenant_id:
                    return identifier
            matches = [
                key for key, site in self._sites.items()
                if normalized in {site.get("domain"), _normal(site.get("website_id", ""))}
                and (not tenant_id or site.get("tenant_id") == tenant_id)
            ]
        return matches[0] if len(matches) == 1 else None

    def unregister(self, identifier: str, tenant_id: str = "") -> bool:
        key = self._find_key(identifier, tenant_id)
        if key is None:
            return False
        with self._lock:
            return self._sites.pop(key, None) is not None

    def sync_discovered(self, entries: list[dict]) -> dict:
        """Reconcile scheduler registrations with the connected-site portfolio."""
        seen: set[str] = set()
        for entry in entries:
            public = self.register(**entry)
            seen.add(public["key"])
        with self._lock:
            stale = [
                key for key, site in self._sites.items()
                if site.get("discovered") and key not in seen
            ]
            for key in stale:
                self._sites.pop(key, None)
            self._last_discovery = _now_iso()
            self._next_discovery = time.monotonic() + self._discovery_seconds
        return {
            "discovered": len(entries),
            "eligible": sum(1 for entry in entries if entry.get("eligible", True)),
            "removed": len(stale),
            "at": self._last_discovery,
        }

    def discover_now(self, discovery_fn: DiscoveryFn | None = None) -> dict:
        fn = discovery_fn or self._discovery_fn
        if fn is None:
            return {"discovered": 0, "eligible": 0, "removed": 0, "at": None}
        return self.sync_discovered(fn())

    def start(self, cycle_fn: CycleFn, discovery_fn: DiscoveryFn | None = None) -> dict:
        with self._lock:
            self._cycle_fn = cycle_fn
            if discovery_fn is not None:
                self._discovery_fn = discovery_fn
            if self._thread and self._thread.is_alive():
                return self.status()
            self._stop.clear()
            self._started_at = _now_iso()
        if self._discovery_fn is not None:
            try:
                self.discover_now()
            except Exception:  # noqa: BLE001 - discovery retries in the worker
                pass
        with self._lock:
            self._thread = threading.Thread(
                target=self._run,
                name="executive-cmo-scheduler",
                daemon=True,
            )
            self._thread.start()
        return self.status()

    def stop(self) -> dict:
        self._stop.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=2.0)
        with self._lock:
            # Never clear a still-running worker or its stop event: doing so
            # would allow start() to launch an overlapping replacement.
            if self._thread is not None and not self._thread.is_alive():
                self._thread = None
                self._started_at = None
        return self.status()

    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def tick_now(
        self,
        identifier: str,
        cycle_fn: CycleFn | None = None,
        tenant_id: str = "",
    ) -> dict:
        fn = cycle_fn or self._cycle_fn
        if fn is None:
            raise RuntimeError("no cycle function configured")
        key = self._find_key(identifier, tenant_id)
        if key is None:
            raise KeyError(identifier)
        with self._lock:
            site = self._sites[key]
        self._run_one(site, fn)
        with self._lock:
            return self._public_site(self._sites[key])

    def _run(self) -> None:
        while not self._stop.is_set():
            if self._discovery_fn is not None and time.monotonic() >= self._next_discovery:
                try:
                    self.discover_now()
                except Exception:  # noqa: BLE001 - one discovery cannot kill the worker
                    self._next_discovery = time.monotonic() + self._discovery_seconds
            fn = self._cycle_fn
            if fn is not None:
                now = time.monotonic()
                with self._lock:
                    due = [
                        site for site in self._sites.values()
                        if site["next_due"] <= now and site.get("eligible", True)
                    ]
                for site in due:
                    if self._stop.is_set():
                        break
                    self._run_one(site, fn)
            self._stop.wait(self._poll_seconds)

    def _run_one(self, site: dict, fn: CycleFn) -> None:
        key = str(site["key"])
        with self._lock:
            if key in self._inflight:
                return
            self._inflight.add(key)
        try:
            if not site.get("eligible", True):
                run = {
                    "status": "skipped",
                    "summary": {},
                    "verification": {},
                    "error": site.get("skip_reason") or "site_not_eligible",
                }
            else:
                try:
                    run = fn(dict(site))
                except Exception as exc:  # noqa: BLE001 - one site cannot kill the portfolio
                    run = {
                        "summary": {},
                        "verification": {},
                        "error": f"{type(exc).__name__}: {exc}",
                    }
            summary = run.get("summary", {}) if isinstance(run, dict) else {}
            verification = run.get("verification", {}) if isinstance(run, dict) else {}
            actions = run.get("actions", []) if isinstance(run, dict) else []
            applied = sum(1 for action in actions if action.get("status") == "applied")
            cmo = run.get("cmo", {}) if isinstance(run, dict) else {}
            scores = cmo.get("scores", {}) if isinstance(cmo, dict) else {}
            changes = cmo.get("changes", []) if isinstance(cmo, dict) else []
            with self._lock:
                site["runs"] = site.get("runs", 0) + 1
                site["last_run"] = _now_iso()
                site["last_outcome"] = {
                    "run_id": run.get("id") if isinstance(run, dict) else None,
                    "health": summary.get("health_score"),
                    "marketing_score": scores.get("marketing_score"),
                    "delta": verification.get("delta"),
                    "material_changes": sum(1 for change in changes if change.get("material")),
                    "missions": cmo.get("mission_count") if isinstance(cmo, dict) else None,
                    "proposed": summary.get("proposed_actions"),
                    "applied": applied,
                    "memory_storage": cmo.get("memory", {}).get("storage") if isinstance(cmo, dict) else None,
                    "error": run.get("error") if isinstance(run, dict) else None,
                }
                site["next_due"] = time.monotonic() + site["cadence_seconds"]
        finally:
            with self._lock:
                self._inflight.discard(key)

    def _public_site(self, site: dict) -> dict:
        now = time.monotonic()
        return {
            "key": site["key"],
            "domain": site["domain"],
            "url": site.get("url"),
            "name": site.get("name"),
            "tenant_id": site.get("tenant_id"),
            "website_id": site.get("website_id"),
            "mode": site["mode"],
            "cadence_seconds": site["cadence_seconds"],
            "crawl": site["crawl"],
            "eligible": site.get("eligible", True),
            "skip_reason": site.get("skip_reason"),
            "policy_notes": site.get("metadata", {}).get("policy_notes", []),
            "publisher_bound": bool(site.get("metadata", {}).get("publisher_bound", False)),
            "can_execute_live": bool(site.get("metadata", {}).get("can_execute_live", False)),
            "discovered": site.get("discovered", False),
            "runs": site.get("runs", 0),
            "last_run": site.get("last_run"),
            "last_outcome": site.get("last_outcome"),
            "next_run_in_seconds": max(0, round(site["next_due"] - now)),
        }

    def status(self, tenant_id: str | None = None) -> dict:
        with self._lock:
            rows = self._sites.values()
            if tenant_id:
                rows = [site for site in rows if site.get("tenant_id") == tenant_id]
            sites = [self._public_site(site) for site in rows]
            inflight = sum(1 for site in sites if site["key"] in self._inflight)
        return {
            "running": self.is_running(),
            "started_at": self._started_at,
            "last_discovery": self._last_discovery,
            "poll_seconds": self._poll_seconds,
            "discovery_seconds": self._discovery_seconds,
            "site_count": len(sites),
            "eligible_site_count": sum(1 for site in sites if site["eligible"]),
            "inflight_site_count": inflight,
            "sites": sites,
        }


_SCHEDULER: AgentScheduler | None = None


def get_scheduler() -> AgentScheduler:
    global _SCHEDULER
    if _SCHEDULER is None:
        _SCHEDULER = AgentScheduler()
    return _SCHEDULER
