"""Unit tests for the WebsiteDetector and IntegrationDiscoveryService."""

from __future__ import annotations

from onboarding.detector import WebsiteDetector, _classify_plugin_type
from onboarding.integrations import IntegrationDiscoveryService


def _wp_html() -> str:
    return (
        '<html><head><meta name="generator" content="WordPress 6.4" />'
        '<link rel="canonical" href="https://example.com/" />'
        '<meta property="og:title" content="x" /></head><body>'
        '<div class="elementor-widget">hi</div>'
        '<link rel="stylesheet" href="/wp-content/themes/astra/style.css" />'
        "</body></html>"
    )


def test_detect_wordpress_elementor_astra():
    def fake_get(method, url, headers):
        if url.endswith("/robots.txt") or url.endswith("/sitemap.xml"):
            return 200, {}, "x"
        if url.endswith("/feed/"):
            return 200, {}, "x"
        return 200, {"server": "nginx", "x-wp-engine": "1"}, _wp_html()

    det = WebsiteDetector(http_get=fake_get)
    result = det.detect("https://example.com")
    assert result.cms == "wordpress"
    assert result.builder == "elementor"
    assert result.theme == "astra"
    assert result.framework == "Astra"
    assert result.server == "nginx"
    assert result.hosting == "WP Engine"
    assert result.rest_api_available is True
    assert result.has_robots_txt is True
    assert result.has_sitemap is True
    assert result.has_canonical is True
    assert result.has_opengraph is True
    assert result.detection_confidence == "high"


def test_detect_non_wordpress_nextjs():
    def fake_get(method, url, headers):
        html = '<html><body><script src="/_next/static/chunk.js"></script></body></html>'
        return 200, {"server": "cloudflare"}, html

    det = WebsiteDetector(http_get=fake_get)
    result = det.detect("https://example.com")
    assert result.website_type == "nextjs"
    assert result.cdn == "cloudflare"
    assert result.waf == "cloudflare"


def test_classify_plugin_type():
    assert _classify_plugin_type("Yoast SEO") == "seo"
    assert _classify_plugin_type("WP Rocket") == "cache"
    assert _classify_plugin_type("WooCommerce") == "commerce"
    assert _classify_plugin_type("Elementor") == "builder"
    assert _classify_plugin_type("Some Random Thing") is None


def test_integration_discovery():
    def fake_get(method, url, headers):
        html = (
            '<html><head><meta name="google-site-verification" content="x" />'
            '<script src="https://www.googletagmanager.com/gtm.js"></script>'
            "</head><body></body></html>"
        )
        return 200, {"cf-ray": "abc", "x-wp-engine": "1"}, html

    svc = IntegrationDiscoveryService(http_get=fake_get)
    found = svc.discover("https://example.com")
    providers = {i.provider for i in found}
    assert "google_search_console" in providers
    assert "google_tag_manager" in providers
    assert "cloudflare" in providers
    assert "wp_engine" in providers
