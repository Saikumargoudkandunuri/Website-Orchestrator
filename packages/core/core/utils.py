"""Core_Package utilities — shared, dependency-free helper functions (Req 15.1).

This module provides the small set of pure helpers every subsystem relies on:

* :func:`registrable_domain` / :func:`same_registrable_domain` — registrable
  (eTLD+1) domain extraction and comparison, correct for multi-label public
  suffixes and inclusive of subdomains (Req 1.2, 1.3).
* :func:`normalize_url` — canonical URL form for stable comparison and storage.
* :func:`utc_now` — the single source of timezone-aware UTC "now".
* :func:`redact_secrets` — scrubs known secret values from arbitrary structured
  payloads before they reach logs or return values (Req 13.4, 13.5).

Per Requirement 15, this module imports nothing internal to the orchestrator.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import tldextract

__all__ = [
    "registrable_domain",
    "same_registrable_domain",
    "normalize_url",
    "utc_now",
    "redact_secrets",
]

#: Placeholder substituted in place of any redacted secret value.
REDACTION_PLACEHOLDER: str = "***REDACTED***"

# A tldextract instance configured to avoid network calls at runtime. Passing
# ``suffix_list_urls=()`` disables live fetching of the public suffix list; the
# library falls back to its bundled snapshot, keeping domain parsing offline and
# deterministic (Req 15: no external dependencies for core logic at call time).
_extract = tldextract.TLDExtract(suffix_list_urls=())


def registrable_domain(url: str) -> str:
    """Return the registrable (eTLD+1) domain for ``url``.

    The registrable domain is the registered name plus its public suffix, e.g.
    ``https://blog.example.co.uk/path`` -> ``example.co.uk``. Subdomains are
    stripped, so any host under the same registered name maps to the same value.

    A bare host (no scheme) is also accepted. When no registrable domain can be
    determined (e.g. an IP address, ``localhost``, or an empty string), the
    lower-cased host is returned as a best-effort fallback so callers still get a
    stable, comparable key.
    """
    if url is None:
        return ""

    candidate = url.strip()
    if not candidate:
        return ""

    # tldextract operates on hosts; give it a scheme-bearing URL when one is
    # missing so it parses the authority rather than treating the whole string
    # as a path.
    if "//" not in candidate:
        candidate = "//" + candidate

    extracted = _extract(candidate)

    if extracted.domain and extracted.suffix:
        return f"{extracted.domain}.{extracted.suffix}".lower()

    # No public suffix (IP address, localhost, intranet host, etc.). Fall back to
    # the host portion so comparisons remain meaningful and deterministic.
    fallback = extracted.domain or urlsplit(candidate).hostname or ""
    return fallback.lower()


def same_registrable_domain(a: str, b: str) -> bool:
    """Return ``True`` when ``a`` and ``b`` share the same registrable domain.

    Comparison is inclusive of subdomains: ``blog.example.com`` and
    ``shop.example.com`` are considered the same registrable domain, as are
    ``example.com`` and ``www.example.com`` (Req 1.2). Two URLs with no
    resolvable registrable domain are only equal when their fallback hosts match.
    """
    domain_a = registrable_domain(a)
    domain_b = registrable_domain(b)
    if not domain_a or not domain_b:
        return False
    return domain_a == domain_b


def normalize_url(url: str) -> str:
    """Return a canonical form of ``url`` for stable comparison and storage.

    Normalization is conservative and side-effect free:

    * scheme and host are lower-cased,
    * the fragment (``#...``) is dropped,
    * a trailing slash on a path is removed (except for the root ``/``),
    * an empty path is left empty,
    * query string and everything else are preserved as-is.

    The input is returned unchanged (aside from stripping surrounding
    whitespace) when it has no network location to normalize.
    """
    if url is None:
        return ""

    stripped = url.strip()
    if not stripped:
        return ""

    parts = urlsplit(stripped)

    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()

    path = parts.path
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")

    # Drop the fragment; keep the query.
    return urlunsplit((scheme, netloc, path, parts.query, ""))


def utc_now() -> datetime:
    """Return the current time as a timezone-aware UTC :class:`datetime`.

    This is the single source of "now" for the orchestrator so that persisted
    timestamps and freshness comparisons are always UTC and comparable.
    """
    return datetime.now(timezone.utc)


def redact_secrets(obj: Any, secret_values: Any) -> Any:
    """Return a copy of ``obj`` with every occurrence of a secret redacted.

    ``obj`` may be any JSON-like structure (dict, list, tuple, str, or scalar).
    ``secret_values`` is an iterable of secret strings to scrub. Behavior:

    * A string equal to a secret is replaced wholesale by
      :data:`REDACTION_PLACEHOLDER`.
    * A string that *contains* a secret substring has that substring replaced,
      retaining the surrounding non-secret content (Req 13.5).
    * dicts, lists, and tuples are traversed recursively, preserving structure
      and non-secret content (Req 13.4).
    * Any other value is returned unchanged.

    The original ``obj`` is never mutated. Empty or falsy secret values are
    ignored so a stray empty string can never blank out the entire payload.
    """
    secrets = [s for s in _as_secret_list(secret_values) if s]
    if not secrets:
        return _deep_copy_structure(obj)
    return _redact(obj, secrets)


def _as_secret_list(secret_values: Any) -> list[str]:
    """Coerce ``secret_values`` into a list of secret strings."""
    if secret_values is None:
        return []
    if isinstance(secret_values, str):
        return [secret_values]
    try:
        return [str(s) for s in secret_values]
    except TypeError:
        return [str(secret_values)]


def _redact(obj: Any, secrets: list[str]) -> Any:
    if isinstance(obj, str):
        redacted = obj
        for secret in secrets:
            if redacted == secret:
                return REDACTION_PLACEHOLDER
            if secret in redacted:
                redacted = redacted.replace(secret, REDACTION_PLACEHOLDER)
        return redacted
    if isinstance(obj, dict):
        return {key: _redact(value, secrets) for key, value in obj.items()}
    if isinstance(obj, list):
        return [_redact(item, secrets) for item in obj]
    if isinstance(obj, tuple):
        return tuple(_redact(item, secrets) for item in obj)
    return obj


def _deep_copy_structure(obj: Any) -> Any:
    """Shallow-structural copy so callers never receive the original container."""
    if isinstance(obj, dict):
        return {key: _deep_copy_structure(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [_deep_copy_structure(item) for item in obj]
    if isinstance(obj, tuple):
        return tuple(_deep_copy_structure(item) for item in obj)
    return obj
