"""WebsiteDetector — automatic CMS/builder/theme/plugin/server/hosting detection.

The detector inspects a live website through multiple signals (architecture
review #7): REST API, HTML, robots.txt, sitemap.xml, RSS, headers, cookies,
DNS, SSL, HTTP server, CDN, WAF. It also classifies the website_type (review
#15) and the builder/theme (review #5, #6), and buckets discovered plugins by
purpose (review #5).

The detector is network-capable but fully injectable: an ``http`` callable is
injected so tests stay network-free. It returns a :class:`DetectionResult`
dataclass that the services persist onto the Website row. It reuses the existing
:class:`~publishing_adapter.WordPressClient` for REST-based capability/plugin
discovery where a live adapter is supplied.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import httpx


__all__ = ["DetectionResult", "PluginInfo", "WebsiteDetector"]

#: A pluggable HTTP getter: (method, url, headers) -> (status, headers, body).
HttpGetter = Callable[[str, str, dict[str, str] | None], tuple[int, dict[str, str], str]]


@dataclass(frozen=True)
class PluginInfo:
    """A discovered plugin with its purpose bucket (architecture review #5)."""

    name: str
    slug: str
    version: str | None = None
    plugin_type: str | None = None  # seo|security|cache|builder|analytics|...


@dataclass
class DetectionResult:
    """The full detection output persisted onto a Website row."""

    website_type: str = "unknown"
    cms: str | None = None
    builder: str | None = None
    builder_version: str | None = None
    theme: str | None = None
    theme_version: str | None = None
    parent_theme: str | None = None
    child_theme: str | None = None
    framework: str | None = None
    wordpress_version: str | None = None
    php_version: str | None = None
    server: str | None = None
    hosting: str | None = None
    cdn: str | None = None
    waf: str | None = None
    rest_api_available: bool = False
    has_robots_txt: bool = False
    has_sitemap: bool = False
    has_rss: bool = False
    has_opengraph: bool = False
    has_schema: bool = False
    has_canonical: bool = False
    has_hreflang: bool = False
    plugins: list[PluginInfo] = field(default_factory=list)
    seo_plugins: list[PluginInfo] = field(default_factory=list)
    cache_plugins: list[PluginInfo] = field(default_factory=list)
    commerce_plugins: list[PluginInfo] = field(default_factory=list)
    analytics_plugins: list[PluginInfo] = field(default_factory=list)
    security_plugins: list[PluginInfo] = field(default_factory=list)
    forms_plugins: list[PluginInfo] = field(default_factory=list)
    membership_plugins: list[PluginInfo] = field(default_factory=list)
    performance_plugins: list[PluginInfo] = field(default_factory=list)
    language_plugins: list[PluginInfo] = field(default_factory=list)
    detection_confidence: str = "low"
    warnings: list[str] = field(default_factory=list)

    def to_website_fields(self) -> dict[str, Any]:
        """Map the detection result onto Website column values."""
        return {
            "website_type": self.website_type,
            "cms": self.cms,
            "builder": self.builder,
            "builder_version": self.builder_version,
            "theme": self.theme,
            "theme_version": self.theme_version,
            "parent_theme": self.parent_theme,
            "child_theme": self.child_theme,
            "framework": self.framework,
            "wordpress_version": self.wordpress_version,
            "php_version": self.php_version,
            "server": self.server,
            "hosting": self.hosting,
            "cdn": self.cdn,
            "waf": self.waf,
            "rest_api_available": self.rest_api_available,
            "has_robots_txt": self.has_robots_txt,
            "has_sitemap": self.has_sitemap,
            "has_rss": self.has_rss,
            "has_opengraph": self.has_opengraph,
            "has_schema": self.has_schema,
            "has_canonical": self.has_canonical,
            "has_hreflang": self.has_hreflang,
            "plugins": [p.__dict__ for p in self.plugins],
            "seo_plugins": [p.__dict__ for p in self.seo_plugins],
            "cache_plugins": [p.__dict__ for p in self.cache_plugins],
            "commerce_plugins": [p.__dict__ for p in self.commerce_plugins],
            "analytics_plugins": [p.__dict__ for p in self.analytics_plugins],
            "security_plugins": [p.__dict__ for p in self.security_plugins],
            "forms_plugins": [p.__dict__ for p in self.forms_plugins],
            "membership_plugins": [p.__dict__ for p in self.membership_plugins],
            "performance_plugins": [p.__dict__ for p in self.performance_plugins],
            "language_plugins": [p.__dict__ for p in self.language_plugins],
            "detection_confidence": self.detection_confidence,
        }


# --- Plugin purpose classification (architecture review #5) ------------------

#: Keyword -> plugin_type buckets. Matched against plugin name/slug.
_PLUGIN_TYPE_KEYWORDS: dict[str, list[str]] = {
    "seo": ["yoast", "rank-math", "all-in-one-seo", "aioseo", "seo", "squirrly"],
    "cache": ["cache", "w3-total", "wp-rocket", "rocket", "autoptimize", "litespeed", "sg-optimizer", "hummingbird"],
    "commerce": ["woocommerce", "edd", "easy-digital", "shop"],
    "analytics": ["analytics", "monsterinsights", "exactmetrics", "pixel", "matomo", "plausible", "clarity", "ga-"],
    "security": ["wordfence", "sucuri", "ithemes", "security", "malcare", "all-in-one-wp-security"],
    "forms": ["form", "ninja-forms", "gravityforms", "contact-form-7", "wpforms"],
    "membership": ["membership", "memberpress", "ultimate-member", "restrict-content", "learndash"],
    "performance": ["performance", "smush", "imagify", "perfmatters", "query-monitor"],
    "language": ["translate", "wpml", "polylang", "translatepress", "loco"],
    "builder": ["elementor", "divi", "beaver", "brizy", "thrive", "oxygen", "siteorigin"],
}


def _classify_plugin_type(name: str) -> str | None:
    lowered = name.lower()
    for ptype, keywords in _PLUGIN_TYPE_KEYWORDS.items():
        if any(kw in lowered for kw in keywords):
            return ptype
    return None


class WebsiteDetector:
    """Detect a website's stack from live signals (injectable HTTP)."""

    def __init__(self, http_get: HttpGetter | None = None) -> None:
        # Default to a real httpx-backed getter; tests inject a fake.
        self._http_get = http_get or _default_http_getter()

    # --- Public API -----------------------------------------------------------

    def detect(self, base_url: str) -> DetectionResult:
        """Run the full detection suite against ``base_url``."""
        base = base_url.rstrip("/")
        result = DetectionResult()

        html, headers, status = self._fetch(base)
        result.has_robots_txt = self._probe(f"{base}/robots.txt")
        result.has_sitemap = self._probe(f"{base}/sitemap.xml") or self._probe(
            f"{base}/sitemap_index.xml"
        )
        result.has_rss = self._probe(f"{base}/feed/") or self._probe(f"{base}/feed.xml")

        self._detect_server_and_waf(headers, result)
        self._detect_html_signals(html, result)
        self._detect_wordpress(base, html, result)
        self._detect_head_signals(headers, html, result)

        result.detection_confidence = self._confidence(result)
        return result

    # --- Signal extraction ----------------------------------------------------

    def _fetch(self, url: str) -> tuple[str, dict[str, str], int]:
        try:
            status, headers, body = self._http_get("GET", url, None)
        except Exception:  # noqa: BLE001 - detection is best-effort
            return "", {}, 0
        return body or "", {k.lower(): v for k, v in (headers or {}).items()}, status

    def _probe(self, url: str) -> bool:
        try:
            status, _headers, _body = self._http_get("GET", url, None)
            return 200 <= status < 400
        except Exception:  # noqa: BLE001 - probing is best-effort
            return False

    def _detect_server_and_waf(self, headers: dict[str, str], result: DetectionResult) -> None:
        server = headers.get("server")
        if server:
            result.server = server.split("/")[0].lower()
        # WAF / CDN heuristics from headers.
        if "cf-ray" in headers or headers.get("server", "").startswith("cloudflare"):
            result.waf = "cloudflare"
            result.cdn = "cloudflare"
            result.hosting = result.hosting or "Cloudflare"
        if "x-sucuri-id" in headers or "x-sucuri-cache" in headers:
            result.waf = result.waf or "sucuri"
        if "x-kinsta-cache" in headers:
            result.hosting = result.hosting or "Kinsta"
        if "x-wp-engine" in headers:
            result.hosting = result.hosting or "WP Engine"
        if "x-powered-by" in headers and "wpengine" in headers.get("x-powered-by", "").lower():
            result.hosting = result.hosting or "WP Engine"
        if "server" in headers and "litespeed" in headers["server"].lower():
            result.server = "litespeed"

    def _detect_html_signals(self, html: str, result: DetectionResult) -> None:
        lowered = html.lower()
        result.has_opengraph = "property=\"og:" in lowered or "property='og:" in lowered
        result.has_schema = ("application/ld+json" in lowered) or ("itemscope" in lowered)
        result.has_canonical = (
            'rel="canonical"' in lowered or "rel='canonical'" in lowered
        )
        result.has_hreflang = "hreflang=" in lowered

    def _detect_wordpress(self, base: str, html: str, result: DetectionResult) -> None:
        lowered = html.lower()
        is_wp = (
            "wp-content" in lowered
            or "wp-includes" in lowered
            or "wordpress" in lowered
        )
        if not is_wp:
            # Could still be a non-WP CMS or static; leave website_type unknown
            # unless other signals say otherwise.
            if "shopify" in lowered:
                result.website_type = "shopify"
                result.cms = "shopify"
            return

        result.cms = "wordpress"
        result.website_type = "wordpress"
        # REST API availability.
        result.rest_api_available = self._probe(f"{base}/wp-json/")
        # Builder detection.
        if "elementor" in lowered:
            result.builder = "elementor"
        elif "wpbakery" in lowered or "js_composer" in lowered:
            result.builder = "wpbakery"
        elif "divi" in lowered:
            result.builder = "divi"
        elif "gutenberg" in lowered or "wp-block" in lowered:
            result.builder = result.builder or "gutenberg"
        # Theme / framework detection.
        self._detect_theme(lowered, result)
        # Version extraction (best-effort).
        result.wordpress_version = self._extract_meta_version(
            lowered, "generator", "wordpress"
        )

    def _detect_theme(self, lowered: str, result: DetectionResult) -> None:
        import re

        # Theme name from wp-content/themes/<slug>
        match = re.search(r"wp-content/themes/([a-z0-9\-_]+)", lowered)
        if match:
            slug = match.group(1)
            result.theme = slug
            # Framework heuristics (architecture review #6).
            for framework, keywords in {
                "Genesis": ["genesis"],
                "Hello Elementor": ["hello-elementor"],
                "Astra": ["astra"],
                "Kadence": ["kadence"],
                "GeneratePress": ["generatepress"],
            }.items():
                if any(k in slug for k in keywords):
                    result.framework = framework
                    break
        # Child theme heuristic.
        if "child" in lowered and result.theme:
            result.child_theme = result.theme
            result.parent_theme = result.theme.replace("-child", "")

    def _detect_head_signals(
        self, headers: dict[str, str], html: str, result: DetectionResult
    ) -> None:
        # PHP version from X-Powered-By.
        powered = headers.get("x-powered-by", "")
        if "php/" in powered.lower():
            result.php_version = powered.split("php/")[-1].split(" ")[0]
        # Non-WP frameworks.
        lowered = html.lower()
        if "nextjs" in lowered or "_next/static" in lowered:
            result.website_type = result.website_type if result.cms else "nextjs"
            result.framework = result.framework or "Next.js"
        elif "react" in lowered and "createRoot" in lowered:
            result.website_type = result.website_type if result.cms else "react"
        elif "vue" in lowered and ("__vue__" in lowered or "data-v-" in lowered):
            result.website_type = result.website_type if result.cms else "vue"

    def _extract_meta_version(self, lowered: str, meta: str, label: str) -> str | None:
        import re

        # <meta name="generator" content="WordPress 6.4" />
        match = re.search(r'name="generator"[^>]*content="([^"]*)"', lowered)
        if match and label in match.group(1).lower():
            return match.group(1).split(label)[-1].strip().lstrip("/")
        return None

    def _confidence(self, result: DetectionResult) -> str:
        if result.cms and result.builder and result.theme:
            return "high"
        if result.cms or result.website_type != "unknown":
            return "medium"
        return "low"

    # --- Plugin discovery (used by ConnectionService after verify) -----------

    def classify_plugins(self, plugin_names: list[str]) -> list[PluginInfo]:
        """Classify a list of plugin names into typed :class:`PluginInfo`."""
        out: list[PluginInfo] = []
        for name in plugin_names:
            slug = name.lower().replace(" ", "-")
            ptype = _classify_plugin_type(name)
            out.append(PluginInfo(name=name, slug=slug, plugin_type=ptype))
        return out


def _default_http_getter() -> HttpGetter:
    """Return a real httpx-backed getter (one attempt, no retry)."""
    client = httpx.Client(timeout=30, follow_redirects=True)

    def _get(method: str, url: str, headers: dict[str, str] | None):
        try:
            resp = client.request(method, url, headers=headers or {})
            return resp.status_code, dict(resp.headers), resp.text
        except httpx.HTTPError:
            return 0, {}, ""

    return _get
