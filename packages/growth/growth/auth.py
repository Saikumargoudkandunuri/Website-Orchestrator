"""Growth authentication and request identity providers."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from typing import Callable, Protocol, runtime_checkable

from fastapi import Request

from growth.errors import GrowthAuthenticationError

__all__ = [
    "GrowthIdentity",
    "AuthProvider",
    "ConfiguredAuthProvider",
    "create_hs256_jwt",
]


@dataclass(frozen=True)
class GrowthIdentity:
    """Authenticated principal resolved for a Growth request."""

    tenant_id: str
    principal_id: str
    credential_type: str
    roles: tuple[str, ...] = field(default_factory=tuple)
    permissions: tuple[str, ...] = field(default_factory=tuple)
    api_key_id: str | None = None
    service_account_id: str | None = None


@runtime_checkable
class AuthProvider(Protocol):
    """Swappable Growth authentication provider."""

    def authenticate(self, request: Request) -> GrowthIdentity:
        """Validate request credentials and return a request-scoped identity."""
        ...


class ConfiguredAuthProvider:
    """Validate HS256 JWTs, API keys, and service-account credentials."""

    def __init__(
        self,
        *,
        jwt_secret: str | None = None,
        api_keys: dict[str, GrowthIdentity] | None = None,
        service_accounts: dict[str, tuple[str, GrowthIdentity]] | None = None,
        now: Callable[[], float] | None = None,
    ) -> None:
        self._jwt_secret = jwt_secret
        self._api_keys = api_keys or {}
        self._service_accounts = service_accounts or {}
        self._now = now or time.time

    @classmethod
    def for_test_tenant(cls, tenant_id: str) -> "ConfiguredAuthProvider":
        """Return a deterministic provider used by Growth API tests."""
        return cls(
            jwt_secret="test-growth-jwt-secret",
            api_keys={
                "test-api-key": GrowthIdentity(
                    tenant_id=tenant_id,
                    principal_id="api-key-user",
                    credential_type="api_key",
                    roles=("owner",),
                    permissions=("admin", "read", "write", "approve", "publish"),
                    api_key_id="test-api-key",
                )
            },
            service_accounts={
                "scheduler": (
                    "service-token",
                    GrowthIdentity(
                        tenant_id=tenant_id,
                        principal_id="scheduler",
                        credential_type="service_account",
                        roles=("owner",),
                        permissions=("admin", "read", "write", "approve", "publish"),
                        service_account_id="scheduler",
                    ),
                )
            },
        )

    def authenticate(self, request: Request) -> GrowthIdentity:
        identity = self._authenticate_api_key(request)
        if identity is not None:
            return identity

        identity = self._authenticate_service_account(request)
        if identity is not None:
            return identity

        identity = self._authenticate_bearer_jwt(request)
        if identity is not None:
            return identity

        raise GrowthAuthenticationError("Missing or invalid Growth credentials.")

    def _authenticate_api_key(self, request: Request) -> GrowthIdentity | None:
        key = request.headers.get("x-api-key")
        if not key:
            return None
        identity = self._api_keys.get(key)
        if identity is None:
            raise GrowthAuthenticationError("Invalid API key.")
        return identity

    def _authenticate_service_account(self, request: Request) -> GrowthIdentity | None:
        account_id = request.headers.get("x-service-account")
        token = request.headers.get("x-service-token")
        if not account_id and not token:
            return None
        configured = self._service_accounts.get(account_id or "")
        if configured is None or not hmac.compare_digest(configured[0], token or ""):
            raise GrowthAuthenticationError("Invalid service-account credentials.")
        return configured[1]

    def _authenticate_bearer_jwt(self, request: Request) -> GrowthIdentity | None:
        auth = request.headers.get("authorization", "")
        if not auth.lower().startswith("bearer "):
            return None
        if not self._jwt_secret:
            raise GrowthAuthenticationError("JWT authentication is not configured.")
        token = auth.split(" ", 1)[1].strip()
        payload = _decode_hs256_jwt(token, self._jwt_secret)
        exp = payload.get("exp")
        if exp is not None and float(exp) < float(self._now()):
            raise GrowthAuthenticationError("JWT has expired.")
        tenant_id = str(payload.get("tenant_id") or "").strip()
        principal_id = str(payload.get("sub") or "").strip()
        if not tenant_id or not principal_id:
            raise GrowthAuthenticationError("JWT is missing required identity claims.")
        return GrowthIdentity(
            tenant_id=tenant_id,
            principal_id=principal_id,
            credential_type="jwt",
            roles=tuple(str(v) for v in payload.get("roles", [])),
            permissions=tuple(str(v) for v in payload.get("permissions", [])),
        )


def create_hs256_jwt(payload: dict, secret: str) -> str:
    """Create a compact HS256 JWT for tests and service-to-service callers."""
    header = {"alg": "HS256", "typ": "JWT"}
    signing_input = (
        _b64url_json(header) + "." + _b64url_json(payload)
    ).encode("ascii")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return signing_input.decode("ascii") + "." + _b64url(signature)


def _decode_hs256_jwt(token: str, secret: str) -> dict:
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
    except ValueError as exc:
        raise GrowthAuthenticationError("Malformed JWT.") from exc
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    expected = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    actual = _b64url_decode(signature_b64)
    if not hmac.compare_digest(expected, actual):
        raise GrowthAuthenticationError("Invalid JWT signature.")
    header = json.loads(_b64url_decode(header_b64))
    if header.get("alg") != "HS256":
        raise GrowthAuthenticationError("Unsupported JWT algorithm.")
    return json.loads(_b64url_decode(payload_b64))


def _b64url_json(value: dict) -> str:
    return _b64url(json.dumps(value, separators=(",", ":")).encode("utf-8"))


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))
