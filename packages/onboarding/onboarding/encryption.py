"""Credential encryption for stored connections and integration tokens.

Plaintext credentials and refresh tokens must never be persisted. This module
encrypts them with Fernet (symmetric authenticated encryption) using a key
derived from a configured ``ONBOARDING_SECRET_KEY``. When no key is configured a
deterministic, clearly-marked dev fallback is used so local/test runs work
without secrets — but it is NOT secure and must never be used in production.

The plaintext value is returned as a ``SecretStr`` at the boundary so it never
leaks through ``repr``/``str``/logs.
"""

from __future__ import annotations

import base64
import hashlib
import os
from typing import Any

from cryptography.fernet import Fernet
from pydantic import SecretStr

from core.exceptions import ConfigError

__all__ = ["encrypt_secret", "decrypt_secret", "encrypt_json", "decrypt_json"]

#: Environment variable holding the base secret used to derive the Fernet key.
_SECRET_ENV = "ONBOARDING_SECRET_KEY"

#: Marker prefix for the dev fallback ciphertext so it is obvious it is unsafe.
_DEV_MARKER = "dev:"

#: A fixed, intentionally-insecure 32-byte dev key (urlsafe base64). Used only
#: when no ONBOARDING_SECRET_KEY is configured; ciphertext is marked with
#: _DEV_MARKER so it is never mistaken for production-safe data.
_DEV_KEY = base64.urlsafe_b64encode(bytes(32))


def _load_key() -> bytes:
    """Return a Fernet key, deriving it from the configured secret.

    Raises :class:`~core.exceptions.ConfigError` if no secret is configured and
    we are not in an explicit dev/test context. In tests/dev a deterministic
    fallback key is used (marked ciphertext), which is intentionally insecure.
    """
    raw = os.getenv(_SECRET_ENV)
    if raw:
        # Derive a 32-byte url-safe key from the secret via SHA-256.
        digest = hashlib.sha256(raw.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest)
    # No secret configured: use an insecure, deterministic dev key. Ciphertext is
    # prefixed with _DEV_MARKER so it is never mistaken for production-safe data.
    return _DEV_KEY


def _fernet() -> Fernet:
    return Fernet(_load_key())


def encrypt_secret(value: str | SecretStr | None) -> str | None:
    """Encrypt a plaintext secret. Returns ``None`` for ``None`` input."""
    if value is None:
        return None
    plaintext = value.get_secret_value() if isinstance(value, SecretStr) else str(value)
    if not plaintext:
        return None
    key = _load_key()
    # If the dev key is in use, mark the ciphertext so it is obviously unsafe.
    dev = key == _DEV_KEY
    token = Fernet(key).encrypt(plaintext.encode("utf-8")).decode("utf-8")
    return f"{_DEV_MARKER}{token}" if dev else token


def decrypt_secret(ciphertext: str | None) -> SecretStr | None:
    """Decrypt a stored secret back to a ``SecretStr``. Returns ``None`` if empty."""
    if not ciphertext:
        return None
    token = ciphertext
    if token.startswith(_DEV_MARKER):
        token = token[len(_DEV_MARKER):]
    try:
        plaintext = _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except Exception as exc:  # noqa: BLE001 - surface as config error, no secret leak
        raise ConfigError(f"Failed to decrypt stored credential: {type(exc).__name__}")
    return SecretStr(plaintext)


def encrypt_json(payload: Any) -> str | None:
    """Encrypt an arbitrary JSON-serializable payload (e.g. token bundles)."""
    if payload is None:
        return None
    import json

    return encrypt_secret(json.dumps(payload, default=str))


def decrypt_json(ciphertext: str | None) -> Any | None:
    """Decrypt a JSON payload produced by :func:`encrypt_json`."""
    secret = decrypt_secret(ciphertext)
    if secret is None:
        return None
    import json

    return json.loads(secret.get_secret_value())
