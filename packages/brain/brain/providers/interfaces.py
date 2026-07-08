"""Provider interfaces for the Platform AI & Provider Layer."""

from __future__ import annotations

import abc
from typing import Any

__all__ = [
    "SearchEngineProvider",
    "CDNProvider",
    "CodeRepositoryProvider",
    "NotificationProvider",
]


class SearchEngineProvider(abc.ABC):
    """Interface for search engine API interactions (e.g., Bing Webmaster Tools)."""
    
    @abc.abstractmethod
    def submit_url(self, url: str) -> bool:
        """Submit a URL for indexing."""
        ...


class CDNProvider(abc.ABC):
    """Interface for CDN interactions (e.g., Cloudflare)."""
    
    @abc.abstractmethod
    def purge_cache(self, url: str) -> bool:
        """Purge the cache for a specific URL."""
        ...


class CodeRepositoryProvider(abc.ABC):
    """Interface for code repository interactions (e.g., GitHub)."""
    
    @abc.abstractmethod
    def create_pull_request(self, title: str, branch: str, body: str) -> str:
        """Create a pull request and return its URL."""
        ...


class NotificationProvider(abc.ABC):
    """Interface for notifications (e.g., Slack, Email, Webhook)."""
    
    @property
    @abc.abstractmethod
    def channel_type(self) -> str:
        """The type of notification channel (e.g., 'slack', 'email', 'webhook')."""
        ...
        
    @abc.abstractmethod
    def send_notification(self, subject: str, message: str) -> bool:
        """Dispatch the notification."""
        ...
