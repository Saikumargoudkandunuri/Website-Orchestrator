"""Provider Registry and stub implementations."""

from __future__ import annotations

import logging
from typing import Any

from brain.providers.interfaces import (
    CDNProvider,
    CodeRepositoryProvider,
    NotificationProvider,
    SearchEngineProvider,
)

__all__ = [
    "PlatformAIProviderRegistry",
    "StubBingProvider",
    "StubCloudflareProvider",
    "StubGitHubProvider",
    "StubSlackProvider",
]

logger = logging.getLogger(__name__)


class StubBingProvider(SearchEngineProvider):
    """Placeholder Bing Webmaster Tools provider."""
    
    def submit_url(self, url: str) -> bool:
        logger.warning("StubBingProvider.submit_url called for %s", url)
        return True


class StubCloudflareProvider(CDNProvider):
    """Placeholder Cloudflare provider."""
    
    def purge_cache(self, url: str) -> bool:
        logger.warning("StubCloudflareProvider.purge_cache called for %s", url)
        return True


class StubGitHubProvider(CodeRepositoryProvider):
    """Placeholder GitHub provider."""
    
    def create_pull_request(self, title: str, branch: str, body: str) -> str:
        logger.warning("StubGitHubProvider.create_pull_request called for %s", title)
        return "https://github.com/stub/stub/pull/1"


class StubSlackProvider(NotificationProvider):
    """Placeholder Slack notification provider."""
    
    @property
    def channel_type(self) -> str:
        return "slack"
        
    def send_notification(self, subject: str, message: str) -> bool:
        logger.warning("StubSlackProvider.send_notification called: %s", subject)
        return True


class PlatformAIProviderRegistry:
    """Registry holding all active providers for the Brain to orchestrate."""

    def __init__(self) -> None:
        self.search_engines: list[SearchEngineProvider] = []
        self.cdns: list[CDNProvider] = []
        self.code_repositories: list[CodeRepositoryProvider] = []
        self.notification_channels: dict[str, NotificationProvider] = {}

    def register_search_engine(self, provider: SearchEngineProvider) -> None:
        """Register a search engine provider."""
        self.search_engines.append(provider)

    def register_cdn(self, provider: CDNProvider) -> None:
        """Register a CDN provider."""
        self.cdns.append(provider)

    def register_code_repository(self, provider: CodeRepositoryProvider) -> None:
        """Register a code repository provider."""
        self.code_repositories.append(provider)

    def register_notification_channel(self, provider: NotificationProvider) -> None:
        """Register a notification provider by its channel type."""
        self.notification_channels[provider.channel_type] = provider


def build_default_provider_registry() -> PlatformAIProviderRegistry:
    """Build the default registry with stub providers."""
    registry = PlatformAIProviderRegistry()
    registry.register_search_engine(StubBingProvider())
    registry.register_cdn(StubCloudflareProvider())
    registry.register_code_repository(StubGitHubProvider())
    registry.register_notification_channel(StubSlackProvider())
    return registry
