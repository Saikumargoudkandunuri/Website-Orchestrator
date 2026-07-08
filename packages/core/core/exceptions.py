"""Core_Package exception hierarchy — the platform's typed error contract.

Every subsystem raises its own custom exception rather than a bare ``Exception``
for any handled condition (Req 12.3), and every subsystem-specific exception
subclasses a base defined here in ``Core_Package`` (Req 15.4). The single root of
the tree is :class:`OrchestratorError`, so any orchestrator failure can be caught
with one ``except`` while still allowing narrow, per-subsystem handling.

Hierarchy (mirrors the design's "Exception Hierarchy (Core_Package)")::

    OrchestratorError                     # base for the whole platform
    ├── CrawlerError
    │   ├── InvalidCrawlRequest           # malformed start_url / bad max_pages (1.5)
    │   └── RobotsUnavailableError        # robots.txt fetch failed → fail closed (1.7)
    ├── DigitalTwinError
    │   ├── PageNotFound                  # surfaced as NotFound read (3.6)
    │   └── StaleDataError                # surfaced as Stale read (3.5)
    ├── CheckEngineError
    ├── FixGeneratorError
    ├── AiGeneratorError
    │   └── GenerationError                # handled AI generation failure (M1)
    │       └── LLMUnavailableError        # LLM provider unreachable / timed out
    ├── PublishingError
    │   ├── WPAuthError                   # 7.1
    │   ├── WPRateLimitError              # 7.2
    │   ├── WPNotFoundError               # 7.3
    │   ├── WPClientError                 # 7.4, 7.8
    │   └── MissingCredentialError        # Application_Password absent (6.6)
    ├── GovernanceError
    │   ├── FixNotFoundError              # 8.9
    │   ├── FixAlreadyDecidedError        # 8.8
    │   ├── InvalidDecisionError          # missing actor / empty rationale (8.11)
    │   ├── BeforeReadError               # BEFORE-read failed → fail closed (8.10)
    │   └── RollbackNotAllowedError       # rollback from non-applied / no before_value (9.1, 9.7)
    ├── ApiError
    └── ConfigError
        └── MissingSecretError            # required secret absent at startup (14.2)

Per Requirement 15, this module imports nothing internal to the orchestrator.
"""

from __future__ import annotations

__all__ = [
    # Root
    "OrchestratorError",
    # Crawler
    "CrawlerError",
    "InvalidCrawlRequest",
    "RobotsUnavailableError",
    # Digital_Twin
    "DigitalTwinError",
    "PageNotFound",
    "StaleDataError",
    # Check_Engine
    "CheckEngineError",
    # Fix_Generator
    "FixGeneratorError",
    # AI_Generator
    "AiGeneratorError",
    "GenerationError",
    "LLMUnavailableError",
    # Publishing_Adapter
    "PublishingError",
    "WPAuthError",
    "WPRateLimitError",
    "WPNotFoundError",
    "WPClientError",
    "MissingCredentialError",
    # Governance_Layer
    "GovernanceError",
    "FixNotFoundError",
    "FixAlreadyDecidedError",
    "InvalidDecisionError",
    "BeforeReadError",
    "RollbackNotAllowedError",
    # API_Surface
    "ApiError",
    # Configuration
    "ConfigError",
    "MissingSecretError",
]


# --- Root ---------------------------------------------------------------------


class OrchestratorError(Exception):
    """Base class for every error raised anywhere in the Website Orchestrator.

    All subsystem exceptions subclass this (directly or transitively), so a
    caller can catch every orchestrator-originated failure with a single
    ``except OrchestratorError`` while still being able to handle narrower
    subsystem types when needed (Req 12.3, 15.4).
    """


# --- Crawler ------------------------------------------------------------------


class CrawlerError(OrchestratorError):
    """Base for all Crawler failures."""


class InvalidCrawlRequest(CrawlerError):
    """A crawl was requested with a malformed ``start_url`` or out-of-range
    ``max_pages``; nothing is retrieved (Req 1.5)."""


class RobotsUnavailableError(CrawlerError):
    """A URL's ``robots.txt`` could not be retrieved, so the Crawler fails
    closed and excludes the affected URLs (Req 1.7, 1.8)."""


# --- Digital_Twin -------------------------------------------------------------


class DigitalTwinError(OrchestratorError):
    """Base for all Digital_Twin persistence failures."""


class PageNotFound(DigitalTwinError):
    """A requested page has no persisted record (surfaced as a ``NotFound``
    read sentinel, Req 3.6)."""


class StaleDataError(DigitalTwinError):
    """A persisted page is older than the staleness threshold (surfaced as a
    ``Stale`` read sentinel, Req 3.5)."""


# --- Check_Engine -------------------------------------------------------------


class CheckEngineError(OrchestratorError):
    """Base for all Check_Engine failures."""


# --- Fix_Generator ------------------------------------------------------------


class FixGeneratorError(OrchestratorError):
    """Base for all Fix_Generator failures."""


# --- AI_Generator -------------------------------------------------------------


class AiGeneratorError(OrchestratorError):
    """Base for all AI generation-layer failures (Milestone 1).

    The AI generation layer (:class:`~core.interfaces.AltTextGenerationService`
    and its :class:`~core.interfaces.LLMClient` seam) is the first component that
    produces *real* fix content rather than a deterministic heuristic. Its
    handled failures subclass this base so a caller can catch every
    generation-layer failure with one ``except`` while still handling narrower
    cases.
    """


class GenerationError(AiGeneratorError):
    """A handled AI generation failure surfaced as a typed
    :class:`~core.results.Err`.

    Raised/returned when the model cannot produce usable content — it is
    unavailable, it times out, or it returns empty/unusable output. The
    Fix_Generator treats this as a signal to degrade gracefully to a report-only
    fix (recording the reason) rather than crashing the crawl workflow, so an AI
    outage never fails an entire ``POST /crawl``.
    """


class LLMUnavailableError(GenerationError):
    """The configured LLM provider could not be reached or timed out.

    A narrower :class:`GenerationError` for transport/provider failures at the
    :class:`~core.interfaces.LLMClient` boundary. Like every orchestrator error
    it carries only a safe, credential-free summary — no API key or provider
    secret is ever placed in its message or attributes.
    """


# --- Publishing_Adapter -------------------------------------------------------


class PublishingError(OrchestratorError):
    """Base for all Publishing_Adapter (WordPress) failures.

    Every WordPress failure is classified as exactly one subclass of this type;
    underlying HTTP exceptions are wrapped rather than propagated raw (Req 12.4,
    7.9). No subclass ever includes a credential in its message or attributes
    (Req 6.7, 7.10).
    """


class WPAuthError(PublishingError):
    """A WordPress request failed authentication (Req 7.1)."""


class WPRateLimitError(PublishingError):
    """A WordPress request was rate limited (Req 7.2)."""


class WPNotFoundError(PublishingError):
    """A requested WordPress resource was not found (Req 7.3)."""


class WPClientError(PublishingError):
    """A WordPress request failed for a client/network reason not covered by the
    more specific errors, including timeouts (Req 7.4, 7.8)."""


class MissingCredentialError(PublishingError):
    """The WordPress ``Application_Password`` is missing or unconfigured, so the
    adapter raises before issuing any request (Req 6.6).

    The offending credential is identified by *name* only. The credential
    *value* is never accepted, stored, or rendered, so this error can never leak
    a secret through its message or attributes (Req 6.7, 7.10).
    """

    def __init__(self, credential_name: str = "Application_Password") -> None:
        # Store the key name only — never a value.
        self.credential_name = credential_name
        super().__init__(
            f"Required credential '{credential_name}' is missing or not configured"
        )


# --- Governance_Layer ---------------------------------------------------------


class GovernanceError(OrchestratorError):
    """Base for all Governance_Layer failures."""


class FixNotFoundError(GovernanceError):
    """A decision referenced a SuggestedFix id that does not exist; no WordPress
    write is performed (Req 8.9)."""


class FixAlreadyDecidedError(GovernanceError):
    """A decision targeted a fix already in ``approved``, ``applied``,
    ``rejected``, or ``rolled_back``; the status is left unchanged (Req 8.8)."""


class InvalidDecisionError(GovernanceError):
    """A decision was invoked with a missing actor or an empty/whitespace-only
    rationale; the operation fails closed with no transition (Req 8.11)."""


class BeforeReadError(GovernanceError):
    """The live BEFORE value could not be read prior to an auto-applicable
    write, so governance fails closed and skips the write (Req 8.10)."""


class RollbackNotAllowedError(GovernanceError):
    """A rollback was requested for a fix that is not ``applied`` or that lacks
    an audited ``before_value``; no write occurs and status is unchanged
    (Req 9.1, 9.7)."""


# --- API_Surface --------------------------------------------------------------


class ApiError(OrchestratorError):
    """Base for all API_Surface failures."""


# --- Configuration ------------------------------------------------------------


class ConfigError(OrchestratorError):
    """Base for all configuration failures."""


class MissingSecretError(ConfigError):
    """A required secret is absent from the environment and ``.env`` at startup.

    The error names the missing secret *key(s)* so operators can fix their
    configuration, but it never accepts, stores, or renders the secret *value*
    (Req 14.2). This keeps startup diagnostics useful without leaking secrets
    into logs or process output.

    Accepts either a single key (``str``) or multiple keys (``list[str]``).

    The rendered message lists each missing key on its own line under a
    ``Missing required secret(s):`` header, e.g.::

        Missing required secret:
        WP_APPLICATION_PASSWORD

    so operators see a clean, scannable list rather than a raw Python list repr
    (``['WP_APPLICATION_PASSWORD']``). The key *names* are the only thing
    rendered — no secret value is ever accepted, stored, or shown.
    """

    def __init__(self, key: "str | list[str]") -> None:
        # Normalize to a list internally — never store a value.
        if isinstance(key, str):
            keys = [key]
        else:
            keys = list(key)
        self.keys: list[str] = keys
        # Backward-compat: .key returns the first key (or comma-joined for multi)
        self.key: str = keys[0] if len(keys) == 1 else ", ".join(keys)

        label = "secret" if len(keys) == 1 else "secrets"
        # One key per line under the header — never a raw list repr.
        formatted = "\n".join(keys)
        super().__init__(f"Missing required {label}:\n{formatted}")
