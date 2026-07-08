"""LLM client seam for the AI_Generator (Milestone 1).

This module provides concrete :class:`core.interfaces.LLMClient` implementations
— the single, swappable boundary through which the AI generation layer reaches a
language model. Keeping the vendor behind a thin ``LLMClient`` means the
concrete provider is injectable and mockable, so the rest of the orchestrator
(and its tests) never depends on a particular AI vendor or the network.

Two implementations are provided:

* :class:`HttpLLMClient` — a real client targeting the widely-adopted
  **OpenAI-compatible Chat Completions** schema (``POST {base_url}/chat/completions``),
  which also fits local/self-hosted servers (Ollama, LM Studio, vLLM, ...). It
  makes exactly one attempt (no retry), authenticates with a Bearer token when an
  API key is configured, and wraps every transport/HTTP failure into a
  credential-free :class:`~core.exceptions.LLMUnavailableError`. Like the
  Publishing_Adapter it accepts an injected :class:`httpx.Client`, so its request
  building and error handling are fully unit-testable via
  :class:`httpx.MockTransport` without any network.
* :class:`StaticLLMClient` — a deterministic, network-free double that returns a
  canned completion (optionally derived from the prompt), for tests and offline
  use.

.. note:: ``TODO(llm-vendor-integration)`` — :class:`HttpLLMClient` targets the
   generic OpenAI-compatible schema and is exercised only against an injected
   mock transport in this milestone; it has **not** been validated against a
   live provider account. Point ``base_url`` at your provider, supply
   ``api_key``, and verify the response shape before relying on it in
   production. It never fakes success: with no reachable provider it raises
   :class:`~core.exceptions.LLMUnavailableError` rather than inventing content.

Credential handling
-------------------
The API key is held as a :class:`pydantic.SecretStr`, so it never appears in
``repr``/``str`` output, logs, or tracebacks, and it is never copied into a
raised error's message or attributes (only the exception *type* and the HTTP
method/status are surfaced).
"""

from __future__ import annotations

from typing import Any

import httpx
from pydantic import SecretStr

from core.constants import REQUEST_TIMEOUT_S
from core.exceptions import LLMUnavailableError

__all__ = ["HttpLLMClient", "StaticLLMClient"]

#: The OpenAI-compatible chat-completions path appended to the configured base URL.
_CHAT_COMPLETIONS_PATH = "chat/completions"


class HttpLLMClient:
    """An OpenAI-compatible :class:`core.interfaces.LLMClient` over :mod:`httpx`.

    Args:
        base_url: The provider base URL (e.g. ``https://api.openai.com/v1`` or a
            local ``http://localhost:11434/v1``). Required — with no base URL the
            client raises :class:`~core.exceptions.LLMUnavailableError` before any
            request rather than fabricating a completion.
        model: The model/version identifier sent with each request.
        api_key: Optional provider API key. Accepts a :class:`~pydantic.SecretStr`
            or plain ``str`` (held as ``SecretStr``); when present a
            ``Bearer`` ``Authorization`` header is attached. ``None`` suits local
            servers that need no key.
        client: An optional injected :class:`httpx.Client`. Injecting one (e.g.
            backed by :class:`httpx.MockTransport`) keeps tests network-free.
            When omitted a client with the Core_Package request timeout is made.
    """

    def __init__(
        self,
        base_url: str | None,
        model: str,
        api_key: SecretStr | str | None = None,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/") if base_url else None
        self._model = model
        self._api_key = self._coerce_secret(api_key)
        self._owns_client = client is None
        self._client = (
            client if client is not None else httpx.Client(timeout=REQUEST_TIMEOUT_S)
        )

    # --- core.interfaces.LLMClient -------------------------------------------

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_output_tokens: int | None = None,
    ) -> str:
        """Return the model's completion for ``prompt`` (single attempt).

        Builds an OpenAI-compatible chat-completions request (an optional
        ``system`` message followed by the ``prompt`` as the user message),
        issues exactly one authenticated POST, and returns the assistant text.
        Any missing configuration, transport failure, non-2xx status, or
        unparseable body is wrapped in a credential-free
        :class:`~core.exceptions.LLMUnavailableError`.
        """
        if not self._base_url:
            raise LLMUnavailableError(
                "No LLM base_url is configured; cannot contact a provider."
            )

        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        body: dict[str, Any] = {"model": self._model, "messages": messages}
        if max_output_tokens is not None:
            body["max_tokens"] = max_output_tokens

        url = f"{self._base_url}/{_CHAT_COMPLETIONS_PATH}"
        headers = {"Content-Type": "application/json"}
        if self._api_key is not None and self._api_key.get_secret_value():
            headers["Authorization"] = f"Bearer {self._api_key.get_secret_value()}"

        try:
            # Exactly one attempt — no retry loop (mirrors the Publishing_Adapter).
            response = self._client.post(url, json=body, headers=headers)
        except httpx.TimeoutException as exc:
            raise LLMUnavailableError(
                f"LLM request timed out ({type(exc).__name__})"
            ) from None
        except httpx.HTTPError as exc:
            raise LLMUnavailableError(
                f"LLM request failed ({type(exc).__name__})"
            ) from None

        if not response.is_success:
            # Only the status code is surfaced; auth material lives in headers and
            # is never copied into the error (credential non-leakage).
            raise LLMUnavailableError(
                f"LLM request failed with status {response.status_code}"
            )

        return self._extract_text(response)

    # --- Helpers --------------------------------------------------------------

    @staticmethod
    def _extract_text(response: httpx.Response) -> str:
        """Pull the assistant text out of an OpenAI-compatible response body."""
        try:
            payload = response.json()
            choice = payload["choices"][0]
            # Chat schema nests content under message.content.
            content = choice["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMUnavailableError(
                f"LLM response was not in the expected shape ({type(exc).__name__})"
            ) from None
        if not isinstance(content, str):
            raise LLMUnavailableError("LLM response content was not text.")
        return content

    @staticmethod
    def _coerce_secret(api_key: SecretStr | str | None) -> SecretStr | None:
        """Normalize the API key to a ``SecretStr`` (or ``None``)."""
        if api_key is None:
            return None
        if isinstance(api_key, SecretStr):
            return api_key
        return SecretStr(api_key)

    def close(self) -> None:
        """Close the underlying client if this instance created it."""
        if self._owns_client:
            self._client.close()

    def __repr__(self) -> str:  # pragma: no cover - trivial, credential-safe
        """Credential-free ``repr`` (never renders the API key)."""
        return f"HttpLLMClient(base_url={self._base_url!r}, model={self._model!r})"


class StaticLLMClient:
    """A deterministic, network-free :class:`core.interfaces.LLMClient`.

    Returns a fixed completion, or — when constructed with ``echo_prompt=True`` —
    the prompt itself, so tests can assert the prompt content flowed through. It
    never touches the network, making it a safe default for offline environments
    and a simple double for unit tests.
    """

    def __init__(
        self, completion: str = "A descriptive image", *, echo_prompt: bool = False
    ) -> None:
        self._completion = completion
        self._echo_prompt = echo_prompt
        #: Recorded (prompt, system, max_output_tokens) calls, for test spying.
        self.calls: list[tuple[str, str | None, int | None]] = []

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_output_tokens: int | None = None,
    ) -> str:
        """Return the canned completion, recording the call."""
        self.calls.append((prompt, system, max_output_tokens))
        return prompt if self._echo_prompt else self._completion
