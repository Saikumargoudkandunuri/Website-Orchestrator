"""Core_Package structured logging (Req 13.1, 13.2, 13.4, 13.5).

Every log entry is emitted as a single-line structured JSON object carrying at
minimum a ``timestamp``, a severity ``level``, a ``message`` (structlog's
``event`` key), and a ``trace_id`` (Req 13.1). All entries produced during one
orchestration operation share the same trace identifier so they can be
correlated (Req 13.2); use :func:`operation_trace` (a context manager) or
:func:`bind_trace_id` to establish that id.

Before any entry is written it is routed through :func:`core.utils.redact_secrets`
as a structlog processor, so a credential value (e.g. the WordPress
``Application_Password``) that finds its way into a log payload is replaced with a
redaction placeholder while every other field is retained (Req 13.4, 13.5). The
secret values are sourced from :mod:`core.config` when available, but importing
or configuring this module never requires a loadable configuration — if settings
cannot be read (e.g. in a test with no environment), redaction simply has no
secrets to scrub and logging continues to work.

Per Requirement 15 this module depends only on ``structlog`` and other
Core_Package modules, never on another subsystem.
"""

from __future__ import annotations

import contextlib
import logging as _stdlib_logging
import uuid
from collections.abc import Iterator
from typing import Any, Callable

import structlog
from structlog.contextvars import (
    bind_contextvars,
    bound_contextvars,
    merge_contextvars,
    unbind_contextvars,
)

from core.utils import redact_secrets, utc_now

__all__ = [
    "TRACE_ID_KEY",
    "configure_logging",
    "get_logger",
    "new_trace_id",
    "bind_trace_id",
    "clear_trace_id",
    "operation_trace",
]

#: Key under which the per-operation trace identifier is recorded in every entry.
TRACE_ID_KEY: str = "trace_id"

#: Set once :func:`configure_logging` has run so :func:`get_logger` can lazily
#: configure structlog on first use without reconfiguring on every call.
_configured: bool = False


# --- Trace identifiers --------------------------------------------------------


def new_trace_id() -> str:
    """Return a fresh, unique trace identifier for one orchestration operation."""
    return uuid.uuid4().hex


def bind_trace_id(trace_id: str | None = None) -> str:
    """Bind ``trace_id`` to the current context, generating one when omitted.

    Every subsequent log entry emitted from the same execution context (thread /
    async task) carries this identifier until it is cleared or rebound, so all
    entries for one operation correlate (Req 13.2). Returns the bound id.
    """
    tid = trace_id or new_trace_id()
    bind_contextvars(**{TRACE_ID_KEY: tid})
    return tid


def clear_trace_id() -> None:
    """Remove any trace identifier bound to the current context."""
    unbind_contextvars(TRACE_ID_KEY)


@contextlib.contextmanager
def operation_trace(trace_id: str | None = None) -> Iterator[str]:
    """Context manager binding a single trace id for the enclosed operation.

    All log entries emitted inside the ``with`` block share the same trace
    identifier (Req 13.2); on exit the previous context state is restored, so
    nested or sequential operations do not bleed trace ids into one another.
    Yields the trace id in use.
    """
    tid = trace_id or new_trace_id()
    with bound_contextvars(**{TRACE_ID_KEY: tid}):
        yield tid


# --- Secret sourcing / redaction ----------------------------------------------


def _settings_secret_values() -> list[str]:
    """Best-effort list of secret *values* to redact, sourced from config.

    Reads ``WP_APPLICATION_PASSWORD`` from :func:`core.config.get_settings` when
    it is loadable. Any failure (config not importable, required settings absent
    in a test environment, etc.) is swallowed and yields an empty list, so
    configuring or using logging never depends on a loadable configuration.
    """
    try:
        from core.config import get_settings

        settings = get_settings()
        values = [settings.wp_application_password.get_secret_value()]
        # The optional Milestone 1 AI-provider key is redacted too when present.
        if settings.llm_api_key is not None:
            values.append(settings.llm_api_key.get_secret_value())
    except Exception:  # noqa: BLE001 - logging must never fail on config errors
        return []
    return [value for value in values if value]


def _make_redact_processor(
    secret_values: Any | None,
) -> Callable[[Any, str, dict[str, Any]], dict[str, Any]]:
    """Build a structlog processor that scrubs secrets from each event dict.

    When ``secret_values`` is ``None`` the secrets are sourced dynamically from
    configuration on every call, so credentials become redactable as soon as
    settings are loaded. Otherwise the supplied values are used verbatim.
    """
    if secret_values is None:
        provider: Callable[[], list[str]] = _settings_secret_values
    else:
        fixed = list(secret_values)
        provider = lambda: fixed  # noqa: E731 - tiny constant provider

    def processor(
        _logger: Any, _method_name: str, event_dict: dict[str, Any]
    ) -> dict[str, Any]:
        secrets = provider()
        if not secrets:
            return event_dict
        # redact_secrets returns a redacted copy, preserving non-secret content
        # (Req 13.5); reassigning keeps the structure structlog expects.
        return redact_secrets(event_dict, secrets)

    return processor


def _add_timestamp(
    _logger: Any, _method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Add an ISO-8601 UTC ``timestamp`` using the single source of "now"."""
    event_dict.setdefault("timestamp", utc_now().isoformat())
    return event_dict


# --- Configuration ------------------------------------------------------------


def configure_logging(
    *,
    level: int = _stdlib_logging.INFO,
    secret_values: Any | None = None,
    stream: Any | None = None,
) -> None:
    """Configure structlog for single-line JSON output with redaction.

    Processor pipeline (in order):

    1. merge the per-operation trace id from context (Req 13.2),
    2. add the severity ``level`` (Req 13.1),
    3. add the ISO-8601 UTC ``timestamp`` (Req 13.1),
    4. redact any credential values from the whole payload (Req 13.4, 13.5),
    5. render the event dict as a single-line JSON object (Req 13.1).

    Redaction runs last before rendering so it also covers keys added by earlier
    processors. ``secret_values`` overrides the default config-sourced secrets
    (useful in tests); ``stream`` overrides the output stream (defaults to
    stdout).
    """
    global _configured

    processors = [
        merge_contextvars,
        structlog.processors.add_log_level,
        _add_timestamp,
        _make_redact_processor(secret_values),
        structlog.processors.JSONRenderer(),
    ]

    factory = (
        structlog.PrintLoggerFactory(file=stream)
        if stream is not None
        else structlog.PrintLoggerFactory()
    )

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=factory,
        cache_logger_on_first_use=False,
    )
    _configured = True


def get_logger(name: str | None = None, **initial_values: Any) -> Any:
    """Return a bound structlog logger, configuring logging on first use.

    ``name`` is recorded under the ``logger`` key; ``initial_values`` are bound
    to every entry the returned logger emits.
    """
    if not _configured:
        configure_logging()
    return structlog.get_logger(name, **initial_values)
