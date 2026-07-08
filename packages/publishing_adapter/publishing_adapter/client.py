"""WordPress REST client — the Publishing_Adapter's concrete implementation.

:class:`WordPressClient` implements :class:`core.interfaces.PublishingAdapterPort`
against the WordPress REST API (``wp/v2``) over :mod:`httpx`. It is the only
subsystem with write access to the live site, and its writes are tightly scoped:
it writes *only* a page/post ``content`` field and a media ``alt_text`` field —
never meta descriptions, schema/JSON-LD, or any other field (Req 6.1, 6.2, 6.3).

Authentication (Req 6.4, 6.5)
-----------------------------
Every request is authenticated with a WordPress **Application_Password** over
HTTP Basic auth, paired with the configured username. The account login password
is never used. Authentication is attached to each individual request so no code
path can issue an unauthenticated call.

Credential handling (Req 6.6, 6.7, 7.5, 7.10)
---------------------------------------------
* The Application_Password is held as a :class:`pydantic.SecretStr`, so it never
  appears in ``repr``/``str`` output, logs, or tracebacks.
* If the Application_Password is missing or unconfigured, the adapter raises
  :class:`~core.exceptions.MissingCredentialError` *before* issuing any request.
* No credential value is ever placed into a return value, a raised error's
  message/attributes, or a log record.

Failure semantics (Req 7.1-7.4, 7.6, 7.8, 7.9, 12.4)
----------------------------------------------------
Every public method performs **exactly one** HTTP attempt — the adapter contains
no retry logic and leaves retries to the caller (Req 7.6). Every failure is
classified as *exactly one* typed :class:`~core.exceptions.PublishingError`
subclass (Req 7.9):

* HTTP ``401``/``403`` → :class:`~core.exceptions.WPAuthError` (Req 7.1)
* HTTP ``429`` → :class:`~core.exceptions.WPRateLimitError` (Req 7.2)
* HTTP ``404`` → :class:`~core.exceptions.WPNotFoundError` (Req 7.3)
* any other ``4xx``/``5xx`` → :class:`~core.exceptions.WPClientError` (Req 7.4)
* a request timeout or any other :mod:`httpx` transport/network failure →
  :class:`~core.exceptions.WPClientError` (Req 7.8)

Underlying :mod:`httpx` exceptions are **wrapped**, never propagated raw, so
callers only ever see the orchestrator's typed error contract (Req 12.4). The
wrapped errors carry only a safe summary (HTTP method + status code, or the
exception's *type*); auth material lives solely in request headers and is never
copied into an error message or attribute (Req 7.5, 7.10).

Idempotency (Req 7.7)
---------------------
The two write methods (:meth:`update_page_content`, :meth:`update_media_alt_text`)
POST to a **fixed resource id** (``.../pages/{id}`` / ``.../media/{id}``) with
the target value in the body. WordPress treats such a POST as a field update on
an existing resource, not a creation, so applying the same write twice with the
same value is naturally idempotent: no duplicate resource is created, the live
state converges to the target value, and a repeated successful write simply
returns success rather than raising. The client adds no create-then-update
branching that could break this, so the idempotency guarantee holds end to end.

Scope note
----------
Task 10.1 introduced the happy-path methods, authentication, the
missing-credential guard, and credential non-leakage. Task 10.2 (this change)
fills in the :meth:`_classify_response` seam with the exhaustive status-code
classification and hardens :meth:`_send` to wrap transport failures, while
keeping the single-attempt (no-retry) shape of the request pipeline.
"""

from __future__ import annotations

from typing import Any

import httpx
from pydantic import SecretStr

from core.constants import REQUEST_TIMEOUT_S
from core.exceptions import (
    MissingCredentialError,
    WPAuthError,
    WPClientError,
    WPNotFoundError,
    WPRateLimitError,
)
from core.interfaces import PublishingAdapterPort, WPMedia, WPPage

__all__ = ["WordPressClient"]

#: WordPress REST API namespace for the core content types.
_API_ROOT = "wp-json/wp/v2"

#: The only field the adapter is permitted to write on a page/post (Req 6.2).
_PAGE_WRITE_FIELD = "content"

#: The only field the adapter is permitted to write on a media item (Req 6.2).
_MEDIA_WRITE_FIELD = "alt_text"


class WordPressClient(PublishingAdapterPort):
    """A scoped, authenticated WordPress REST client.

    Args:
        base_url: The WordPress site base URL (e.g. ``https://example.com``).
        username: The WordPress username paired with the Application_Password
            for HTTP Basic auth.
        application_password: The WordPress **Application_Password**. Accepts a
            :class:`~pydantic.SecretStr` or a plain ``str``; either is held as a
            ``SecretStr`` so its value never leaks through ``repr``/logs. A
            ``None``/empty value means "unconfigured" and causes every method to
            raise :class:`MissingCredentialError` before any request (Req 6.6).
        client: An optional injected :class:`httpx.Client`. Injecting a client
            (e.g. one backed by :class:`httpx.MockTransport`) keeps tests
            network-free. When omitted, a client with the Core_Package request
            timeout is created.
    """

    def __init__(
        self,
        base_url: str,
        username: str,
        application_password: SecretStr | str | None,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._username = username
        self._application_password = self._coerce_secret(application_password)
        self._owns_client = client is None
        self._client = client if client is not None else httpx.Client(
            timeout=REQUEST_TIMEOUT_S
        )

    # --- Public contract (PublishingAdapterPort) -----------------------------

    def list_pages(self) -> list[WPPage]:
        """Return the live WordPress pages/posts (Req 6.1)."""
        response = self._send("GET", f"{_API_ROOT}/pages")
        payload = response.json()
        return [self._parse_page(item) for item in payload]

    def get_page(self, page_id: int) -> WPPage:
        """Return the live page/post identified by ``page_id`` (Req 6.1)."""
        response = self._send("GET", f"{_API_ROOT}/pages/{page_id}")
        return self._parse_page(response.json())

    def update_page_content(self, page_id: int, content: str) -> WPPage:
        """Write only ``content`` to page/post ``page_id`` and return the
        updated record (Req 6.2, 6.3).

        The request body contains the ``content`` field and nothing else, so no
        meta description, schema, or other field can be modified.
        """
        response = self._send(
            "POST",
            f"{_API_ROOT}/pages/{page_id}",
            json={_PAGE_WRITE_FIELD: content},
        )
        return self._parse_page(response.json())

    def get_media(self, media_id: int) -> WPMedia:
        """Return the live media item identified by ``media_id`` (Req 6.1)."""
        response = self._send("GET", f"{_API_ROOT}/media/{media_id}")
        return self._parse_media(response.json())

    def update_media_alt_text(self, media_id: int, alt_text: str) -> WPMedia:
        """Write only ``alt_text`` to media ``media_id`` and return the updated
        record (Req 6.2, 6.3).

        The request body contains the ``alt_text`` field and nothing else.
        """
        response = self._send(
            "POST",
            f"{_API_ROOT}/media/{media_id}",
            json={_MEDIA_WRITE_FIELD: alt_text},
        )
        return self._parse_media(response.json())

    # --- Request pipeline ----------------------------------------------------

    def _send(
        self, method: str, path: str, *, json: dict[str, Any] | None = None
    ) -> httpx.Response:
        """Issue **exactly one** authenticated request and classify the outcome.

        The missing-credential guard runs *before* any network activity, so an
        unconfigured Application_Password never results in an issued request
        (Req 6.6). Authentication is attached per-request (Req 6.4, 6.5).

        This method makes a single HTTP attempt and contains no retry logic; the
        caller owns retries (Req 7.6). Transport-level failures — request
        timeouts and any other :mod:`httpx` network error — are wrapped in a
        :class:`~core.exceptions.WPClientError` rather than propagated raw
        (Req 7.8, 12.4). Response-level failures are routed through
        :meth:`_classify_response`. In every case the raised error carries only
        a credential-free summary (Req 7.5, 7.10).
        """
        # Guard BEFORE building or sending anything (Req 6.6).
        auth = self._basic_auth()

        url = f"{self._base_url}/{path.lstrip('/')}"
        try:
            # Exactly one attempt — no retry loop (Req 7.6).
            response = self._client.request(method, url, json=json, auth=auth)
        except httpx.TimeoutException as exc:
            # Timeout → WPClientError (Req 7.8). Wrap, never propagate raw
            # (Req 12.4). Use the exception *type* only; its message/args are
            # not trusted to be credential-free.
            raise WPClientError(
                f"WordPress request timed out ({type(exc).__name__})"
            ) from None
        except httpx.HTTPError as exc:
            # Any other transport/network failure → WPClientError (Req 7.8).
            # Wrap, never propagate raw (Req 12.4).
            raise WPClientError(
                f"WordPress request failed ({type(exc).__name__})"
            ) from None
        self._classify_response(response)
        return response

    def _classify_response(self, response: httpx.Response) -> None:
        """Classify a response into exactly one typed error, or return on success.

        Maps every unsuccessful HTTP status to exactly one
        :class:`~core.exceptions.PublishingError` subclass (Req 7.1-7.4, 7.9):

        * ``401``/``403`` → :class:`WPAuthError` (Req 7.1)
        * ``429`` → :class:`WPRateLimitError` (Req 7.2)
        * ``404`` → :class:`WPNotFoundError` (Req 7.3)
        * any other ``4xx``/``5xx`` → :class:`WPClientError` (Req 7.4)

        Only the status code is surfaced in the error message; auth material
        lives solely in request headers and is never copied here (Req 7.5,
        7.10).
        """
        if response.is_success:
            return

        status = response.status_code
        if status in (401, 403):
            raise WPAuthError(
                f"WordPress authentication failed (HTTP {status})"
            )
        if status == 429:
            raise WPRateLimitError(
                f"WordPress request was rate limited (HTTP {status})"
            )
        if status == 404:
            raise WPNotFoundError(
                f"WordPress resource not found (HTTP {status})"
            )
        raise WPClientError(
            f"WordPress request failed with status {status}"
        )

    # --- Authentication ------------------------------------------------------

    def _basic_auth(self) -> httpx.BasicAuth:
        """Build HTTP Basic auth from the username + Application_Password.

        Raises :class:`MissingCredentialError` when the Application_Password is
        missing or unconfigured, before any request is attempted (Req 6.6). The
        account login password is never involved (Req 6.5).
        """
        secret = self._application_password
        if secret is None or not secret.get_secret_value():
            raise MissingCredentialError("Application_Password")
        return httpx.BasicAuth(self._username, secret.get_secret_value())

    # --- Parsing helpers -----------------------------------------------------

    def _parse_page(self, data: dict[str, Any]) -> WPPage:
        """Map a WordPress page/post payload to a :class:`WPPage`.

        WordPress renders ``content`` and ``title`` as objects with ``rendered``
        / ``raw`` members; this collapses them to the plain strings the
        orchestrator records carry.
        """
        return WPPage(
            id=int(data["id"]),
            content=self._coerce_rendered(data.get("content")),
            title=self._coerce_rendered(data.get("title")) or None,
            link=data.get("link"),
        )

    def _parse_media(self, data: dict[str, Any]) -> WPMedia:
        """Map a WordPress media payload to a :class:`WPMedia`."""
        return WPMedia(
            id=int(data["id"]),
            alt_text=self._coerce_rendered(data.get("alt_text")),
            source_url=data.get("source_url"),
        )

    @staticmethod
    def _coerce_rendered(value: Any) -> str:
        """Collapse a WordPress ``{"rendered": ..., "raw": ...}`` field or a
        plain scalar to a string."""
        if value is None:
            return ""
        if isinstance(value, dict):
            rendered = value.get("rendered")
            if rendered is None:
                rendered = value.get("raw", "")
            return str(rendered)
        return str(value)

    @staticmethod
    def _coerce_secret(
        application_password: SecretStr | str | None,
    ) -> SecretStr | None:
        """Normalize the Application_Password to a ``SecretStr`` (or ``None``)."""
        if application_password is None:
            return None
        if isinstance(application_password, SecretStr):
            return application_password
        return SecretStr(application_password)

    # --- Lifecycle / hygiene -------------------------------------------------

    def close(self) -> None:
        """Close the underlying client if this instance created it."""
        if self._owns_client:
            self._client.close()

    def __repr__(self) -> str:  # pragma: no cover - trivial, credential-safe
        """Credential-free ``repr`` (never renders the Application_Password)."""
        return (
            f"WordPressClient(base_url={self._base_url!r}, "
            f"username={self._username!r})"
        )
