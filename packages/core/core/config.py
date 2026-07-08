"""Core_Package configuration loading (Req 14.1, 14.2).

Settings and secrets are loaded from environment variables or a ``.env`` file
via ``pydantic-settings`` when the Website Orchestrator starts (Req 14.1). If a
required secret is not available, startup fails with a :class:`MissingSecretError`
that names the missing key but never exposes any secret value (Req 14.2,
Property 55).

The single secret in Milestone 0 is ``WP_APPLICATION_PASSWORD`` (the WordPress
Application_Password). It is held as a :class:`pydantic.SecretStr` so its value
never appears in ``repr``/``str`` output, logs, or tracebacks. The remaining
settings (``DATABASE_URL``, ``TENANT_ID``, ``WP_BASE_URL``, ``WP_USERNAME``) are
required but non-secret; the threshold overrides are optional and fall back to
the canonical Core_Package defaults in :mod:`core.constants`.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from core import constants

# --- Exception wiring ---------------------------------------------------------
#
# ``ConfigError`` and ``MissingSecretError`` are the canonical configuration
# exceptions defined in ``core.exceptions`` (Req 12.3 / 15.4). That module is a
# dependency-free leaf — per Requirement 15 it imports nothing internal to the
# orchestrator — so importing it here can never create a circular import, and it
# is always present in the built Core_Package. Importing the canonical classes
# directly guarantees exactly one definition of each, so they cannot drift out
# of sync (an earlier transitional fallback defined a second copy here, which is
# exactly how the two once diverged).
from core.exceptions import ConfigError, MissingSecretError


__all__ = ["Settings", "load_settings", "get_settings"]

#: Field names that hold credential values. Used to reason about secret handling;
#: their values are never included in error messages (Req 14.2). ``llm_api_key``
#: is the optional Milestone 1 AI-provider credential.
SECRET_FIELD_NAMES: frozenset[str] = frozenset(
    {"wp_application_password", "llm_api_key"}
)


class Settings(BaseSettings):
    """Runtime settings loaded from the environment and/or a ``.env`` file.

    Field names map to environment variables case-insensitively, so the field
    ``database_url`` is populated from ``DATABASE_URL`` and so on.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Required, non-secret settings ---------------------------------------
    database_url: str
    tenant_id: str
    wp_base_url: str
    wp_username: str

    # --- Required secret (Application_Password) ------------------------------
    # SecretStr prevents the value from leaking via repr/str/logs (Req 6.7, 14.2).
    wp_application_password: SecretStr

    # --- Optional threshold overrides (default to Core_Package constants) -----
    rate_limit_ms: int = constants.DEFAULT_RATE_LIMIT_MS
    degradation_threshold_ms: int = constants.DEGRADATION_THRESHOLD_MS
    request_timeout_s: int = constants.REQUEST_TIMEOUT_S
    link_timeout_s: int = constants.LINK_TIMEOUT_S
    redirect_hard_cap: int = constants.REDIRECT_HARD_CAP
    thin_content_min_words: int = constants.THIN_CONTENT_MIN_WORDS
    redirect_chain_threshold: int = constants.REDIRECT_CHAIN_THRESHOLD
    max_alt_text_len: int = constants.MAX_ALT_TEXT_LEN

    #: Maximum age (seconds) of Digital_Twin page data before a re-crawl is
    #: required (Req 3.4, 3.5). Overridable via ``STALENESS_THRESHOLD``.
    staleness_threshold: int = 3600

    # --- Milestone 1: AI alt-text generation (all optional) ------------------
    #: Whether the composition root wires the LLM-backed
    #: :class:`~core.interfaces.AltTextGenerationService` into the Fix_Generator.
    #: Defaults to ``False`` so production behavior is unchanged until an operator
    #: opts in and configures a provider; when ``False`` the Fix_Generator falls
    #: back to the deterministic filename heuristic (Milestone 0 behavior).
    alt_text_ai_enabled: bool = False

    #: The LLM model/version identifier recorded on generated fixes for
    #: provenance and used when calling the provider.
    llm_model: str = "gpt-4o-mini"

    #: Optional AI-provider base URL (for a self-hosted or proxied endpoint).
    llm_base_url: str | None = None

    #: Optional AI-provider API key. Held as a :class:`~pydantic.SecretStr` so it
    #: never appears in ``repr``/logs/tracebacks (Req 14.2). Optional because AI
    #: generation is opt-in; the LLM-backed service validates its presence when
    #: it is actually enabled.
    llm_api_key: SecretStr | None = None

    #: Soft cap on generated tokens; alt text is short, so a small default keeps
    #: latency and cost low. Length is still validated as a business rule.
    llm_max_output_tokens: int = 64

    #: Whether the production API factory auto-mounts Milestone 4 Growth routes.
    #: Defaults to false so GrowthBase tables are not created in the Digital Twin
    #: schema unless an operator explicitly opts in or injects a GrowthContainer.
    growth_engine_enabled: bool = False

    #: Whether the production API factory auto-mounts Milestone 2 Intelligence
    #: routes. Defaults to false so a plain API boot does not create Intelligence
    #: tables in the Digital Twin schema unless an operator explicitly opts in or
    #: injects an IntelligenceContainer.
    intelligence_engine_enabled: bool = False

    #: HS256 secret used by the Growth API JWT authenticator when Growth is
    #: enabled in production. Optional because Growth itself is opt-in.
    growth_auth_jwt_secret: SecretStr | None = None

    #: Semicolon-separated Growth API key identities. Each entry is
    #: ``key:tenant_id:principal_id:role1,role2``.
    growth_auth_api_keys: str = ""

    #: Semicolon-separated Growth service-account credentials. Each entry is
    #: ``account_id:token:tenant_id:role1,role2``.
    growth_auth_service_accounts: str = ""

    #: Maximum retry attempts for a failed background job before it is moved to
    #: the dead-letter queue (§2.3 production scheduler).
    growth_job_max_retries: int = 3

    #: Base delay in seconds for the first retry backoff (§2.3 production scheduler).
    growth_job_retry_base_delay_s: float = 1.0

    #: Cap on the retry backoff delay in seconds (§2.3 production scheduler).
    growth_job_retry_max_delay_s: float = 60.0


def load_settings(**overrides: object) -> Settings:
    """Load and validate :class:`Settings`, failing fast on missing requirements.

    Returns a fully-populated :class:`Settings` instance. If any required
    setting (including the required secret ``WP_APPLICATION_PASSWORD``) is absent
    from the environment and ``.env``, raises :class:`MissingSecretError` naming
    the missing key(s) but never any secret value (Req 14.2, Property 55).

    Any other validation failure is surfaced as :class:`ConfigError` with a
    generic, value-free message so a rejected input value can never leak into an
    error, message, or traceback.
    """
    try:
        return Settings(**overrides)  # type: ignore[arg-type]
    except ValidationError as exc:
        missing: list[str] = []
        other: list[str] = []
        for error in exc.errors():
            loc = error.get("loc") or ()
            field = str(loc[0]) if loc else "<unknown>"
            key = field.upper()
            if error.get("type") == "missing":
                missing.append(key)
            else:
                other.append(key)

        # Never chain the original ValidationError: for non-missing errors it can
        # embed the offending input value, which may be a secret. Suppress it.
        if missing:
            raise MissingSecretError(missing) from None
        raise ConfigError(
            "Invalid configuration for: " + ", ".join(sorted(set(other)))
        ) from None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a process-wide cached :class:`Settings` instance.

    Loads settings on first call (failing fast per :func:`load_settings`) and
    caches the result so the environment/``.env`` is read once at startup.
    """
    return load_settings()
