"""IntegrationDiscoveryService — auto-discover third-party integrations.

Discovers analytics/SEO/search-console/CDN/hosting integrations from live
signals (architecture review #4) and stores them as first-class Integration
rows (never JSON-only). Auto-discovered integrations never require user input.

The service is injectable: an ``http`` getter keeps tests network-free. It
returns a list of :class:`DiscoveredIntegration` that the services persist.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

__all__ = ["DiscoveredIntegration", "IntegrationDiscoveryService"]

#: A pluggable HTTP getter: (method, url, headers) -> (status, headers, body).
HttpGetter = Callable[[str, str, dict[str, str] | None], tuple[int, dict[str, str], str]]


@dataclass
class DiscoveredIntegration:
    """A discovered integration to persist as an Integration row."""

    provider: str
    status: str = "discovered"
    metadata: dict = field(default_factory=dict)


class IntegrationDiscoveryService:
    """Detect integrations embedded in a website's HTML/headers."""

    #: Provider -> signature present in HTML/headers.
    _SIGNATURES: dict[str, list[str]] = {
        "google_analytics": ["google-analytics.com", "gtag(", "ga(", "googletagmanager"],
        "google_tag_manager": ["googletagmanager.com"],
        "google_search_console": ["google-site-verification"],
        "bing_webmaster": ["msvalidate.01"],
        "cloudflare": ["cf-ray", "cloudflare"],
        "microsoft_clarity": ["clarity.ms", "clarity("],
        "facebook_pixel": ["connect.facebook.net", "fbq("],
        "meta_conversion_api": ["facebook.com/tr"],
        "hotjar": ["hotjar.com", "hj("],
        "plausible": ["plausible.io"],
        "matomo": ["matomo", "piwik"],
        "hubspot": ["hs-scripts.com", "hubspot"],
        "mailchimp": ["mailchimp", "mc.us"],
        "github": ["github.com"],
        "gitlab": ["gitlab.com"],
        "wp_engine": ["x-wp-engine"],
        "kinsta": ["x-kinsta-cache"],
        "siteground": ["x-sg-cache"],
        "plesk": ["plesk"],
        "cpanel": ["cpanel"],
    }

    def __init__(self, http_get: HttpGetter | None = None) -> None:
        self._http_get = http_get or _default_http_getter()

    def discover(self, base_url: str) -> list[DiscoveredIntegration]:
        """Scan the homepage HTML/headers and return discovered integrations."""
        base = base_url.rstrip("/")
        try:
            _status, headers, body = self._http_get("GET", f"{base}/", None)
        except Exception:  # noqa: BLE001 - discovery is best-effort
            _status, headers, body = 0, {}, ""
        lowered = (body or "").lower()
        header_blob = " ".join(f"{k}:{v}" for k, v in (headers or {}).items()).lower()

        found: list[DiscoveredIntegration] = []
        for provider, sigs in self._SIGNATURES.items():
            if any(sig in lowered or sig in header_blob for sig in sigs):
                found.append(DiscoveredIntegration(provider=provider))
        return found


def _default_http_getter() -> HttpGetter:
    import httpx

    client = httpx.Client(timeout=30, follow_redirects=True)

    def _get(method: str, url: str, headers: dict[str, str] | None):
        try:
            resp = client.request(method, url, headers=headers or {})
            return resp.status_code, dict(resp.headers), resp.text
        except httpx.HTTPError:
            return 0, {}, ""

    return _get
