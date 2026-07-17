"""Unit tests for credential encryption and validators."""

from __future__ import annotations


from onboarding.encryption import decrypt_secret, decrypt_json, encrypt_secret, encrypt_json
from onboarding.validators import ValidationError, validate_non_blank, validate_url


def test_encrypt_decrypt_roundtrip():
    secret = encrypt_secret("my-app-password")
    assert secret != "my-app-password"
    assert decrypt_secret(secret).get_secret_value() == "my-app-password"


def test_encrypt_none_returns_none():
    assert encrypt_secret(None) is None
    assert decrypt_secret(None) is None


def test_encrypt_json_roundtrip():
    blob = encrypt_json({"refresh_token": "abc", "scope": "x"})
    assert blob != '{"refresh_token": "abc"}'
    assert decrypt_json(blob) == {"refresh_token": "abc", "scope": "x"}


def test_validate_non_blank():
    assert validate_non_blank("  hi  ", "x") == "hi"
    try:
        validate_non_blank("", "x")
        assert False, "expected ValidationError"
    except ValidationError:
        pass


def test_validate_url():
    assert validate_url("https://example.com") == "https://example.com"
    try:
        validate_url("ftp://example.com")
        assert False, "expected ValidationError"
    except ValidationError:
        pass
