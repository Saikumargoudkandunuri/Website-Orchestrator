"""Unit tests for Core_Package utilities (Req 15.1).

Example-based pytest coverage for the pure helpers in :mod:`core.utils`:
``registrable_domain`` / ``same_registrable_domain``, ``normalize_url``,
``utc_now``, and ``redact_secrets``.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from core.utils import (
    REDACTION_PLACEHOLDER,
    normalize_url,
    redact_secrets,
    registrable_domain,
    same_registrable_domain,
    utc_now,
)


# ---------------------------------------------------------------------------
# registrable_domain
# ---------------------------------------------------------------------------
class TestRegistrableDomain:
    def test_strips_subdomain(self):
        assert registrable_domain("https://blog.example.com/path") == "example.com"

    def test_multi_label_tld_with_subdomain(self):
        assert (
            registrable_domain("https://blog.example.co.uk/x") == "example.co.uk"
        )

    def test_strips_www(self):
        assert registrable_domain("https://www.example.com") == "example.com"

    def test_deep_subdomain_collapses_to_registrable(self):
        assert (
            registrable_domain("https://a.b.c.example.com") == "example.com"
        )

    def test_bare_host_without_scheme(self):
        assert registrable_domain("blog.example.co.uk") == "example.co.uk"

    def test_lowercases_result(self):
        assert registrable_domain("https://BLOG.EXAMPLE.COM") == "example.com"

    def test_ip_address_fallback(self):
        # An IP has no public suffix; the host is returned as fallback.
        assert registrable_domain("http://127.0.0.1:8080/path") == "127.0.0.1"

    def test_localhost_fallback(self):
        assert registrable_domain("http://localhost:3000") == "localhost"

    def test_empty_string(self):
        assert registrable_domain("") == ""

    def test_whitespace_only(self):
        assert registrable_domain("   ") == ""

    def test_none_input(self):
        assert registrable_domain(None) == ""


# ---------------------------------------------------------------------------
# same_registrable_domain
# ---------------------------------------------------------------------------
class TestSameRegistrableDomain:
    def test_same_across_subdomains(self):
        assert same_registrable_domain(
            "https://blog.example.com", "https://shop.example.com"
        )

    def test_www_and_apex_are_same(self):
        assert same_registrable_domain(
            "https://www.example.com", "https://example.com/page"
        )

    def test_different_tld_is_false(self):
        assert not same_registrable_domain(
            "https://example.com", "https://example.org"
        )

    def test_different_registered_name_is_false(self):
        assert not same_registrable_domain(
            "https://example.com", "https://other.com"
        )

    def test_multi_label_tld_match(self):
        assert same_registrable_domain(
            "https://a.example.co.uk", "https://b.example.co.uk"
        )

    def test_either_empty_is_false(self):
        assert not same_registrable_domain("", "https://example.com")
        assert not same_registrable_domain("https://example.com", "")

    def test_both_empty_is_false(self):
        assert not same_registrable_domain("", "")

    def test_none_inputs_are_false(self):
        assert not same_registrable_domain(None, "https://example.com")


# ---------------------------------------------------------------------------
# normalize_url
# ---------------------------------------------------------------------------
class TestNormalizeUrl:
    def test_lowercases_scheme_and_host(self):
        assert (
            normalize_url("HTTPS://Example.COM/Path")
            == "https://example.com/Path"
        )

    def test_drops_fragment(self):
        assert (
            normalize_url("https://example.com/page#section")
            == "https://example.com/page"
        )

    def test_trims_trailing_slash(self):
        assert (
            normalize_url("https://example.com/path/")
            == "https://example.com/path"
        )

    def test_keeps_root_slash(self):
        assert normalize_url("https://example.com/") == "https://example.com/"

    def test_preserves_query(self):
        assert (
            normalize_url("https://example.com/search?q=Term&x=1")
            == "https://example.com/search?q=Term&x=1"
        )

    def test_preserves_path_case(self):
        assert (
            normalize_url("https://example.com/MixedCase/Path")
            == "https://example.com/MixedCase/Path"
        )

    def test_query_preserved_with_fragment_dropped(self):
        assert (
            normalize_url("https://Example.com/A/?q=1#frag")
            == "https://example.com/A?q=1"
        )

    def test_empty_string(self):
        assert normalize_url("") == ""

    def test_whitespace_only(self):
        assert normalize_url("   ") == ""

    def test_none_input(self):
        assert normalize_url(None) == ""


# ---------------------------------------------------------------------------
# utc_now
# ---------------------------------------------------------------------------
class TestUtcNow:
    def test_returns_datetime(self):
        assert isinstance(utc_now(), datetime)

    def test_is_timezone_aware(self):
        assert utc_now().tzinfo is not None

    def test_tzinfo_is_utc(self):
        now = utc_now()
        assert now.utcoffset() == timezone.utc.utcoffset(None)

    def test_close_to_current_time(self):
        before = datetime.now(timezone.utc)
        value = utc_now()
        after = datetime.now(timezone.utc)
        assert before <= value <= after


# ---------------------------------------------------------------------------
# redact_secrets
# ---------------------------------------------------------------------------
class TestRedactSecrets:
    def test_whole_value_match(self):
        assert redact_secrets("supersecret", ["supersecret"]) == REDACTION_PLACEHOLDER

    def test_substring_within_larger_string(self):
        result = redact_secrets("token=supersecret;end", ["supersecret"])
        assert result == f"token={REDACTION_PLACEHOLDER};end"

    def test_nested_dict(self):
        payload = {"auth": {"key": "supersecret"}, "keep": "value"}
        result = redact_secrets(payload, ["supersecret"])
        assert result == {"auth": {"key": REDACTION_PLACEHOLDER}, "keep": "value"}

    def test_nested_list(self):
        payload = ["safe", "supersecret", "also-safe"]
        result = redact_secrets(payload, ["supersecret"])
        assert result == ["safe", REDACTION_PLACEHOLDER, "also-safe"]

    def test_nested_tuple(self):
        result = redact_secrets(("a", "supersecret"), ["supersecret"])
        assert result == ("a", REDACTION_PLACEHOLDER)
        assert isinstance(result, tuple)

    def test_deeply_nested_mixed_structure(self):
        payload = {"list": [{"inner": ("supersecret", "ok")}]}
        result = redact_secrets(payload, ["supersecret"])
        assert result == {"list": [{"inner": (REDACTION_PLACEHOLDER, "ok")}]}

    def test_multiple_secrets(self):
        payload = {"a": "secret1", "b": "prefix-secret2-suffix"}
        result = redact_secrets(payload, ["secret1", "secret2"])
        assert result == {
            "a": REDACTION_PLACEHOLDER,
            "b": f"prefix-{REDACTION_PLACEHOLDER}-suffix",
        }

    def test_empty_secret_ignored(self):
        payload = {"a": "keep-this"}
        result = redact_secrets(payload, [""])
        assert result == {"a": "keep-this"}

    def test_empty_secret_among_valid_secrets(self):
        result = redact_secrets("has supersecret here", ["", "supersecret"])
        assert result == f"has {REDACTION_PLACEHOLDER} here"

    def test_no_secrets_returns_content_unchanged(self):
        payload = {"a": ["b", "c"]}
        assert redact_secrets(payload, []) == payload

    def test_input_not_mutated(self):
        payload = {"auth": {"key": "supersecret"}, "items": ["supersecret"]}
        original = {"auth": {"key": "supersecret"}, "items": ["supersecret"]}
        redact_secrets(payload, ["supersecret"])
        assert payload == original

    def test_non_string_scalars_passed_through(self):
        payload = {"n": 42, "f": 3.14, "b": True, "none": None}
        result = redact_secrets(payload, ["supersecret"])
        assert result == {"n": 42, "f": 3.14, "b": True, "none": None}

    def test_secret_not_present_leaves_string_untouched(self):
        assert redact_secrets("nothing here", ["supersecret"]) == "nothing here"

    def test_single_string_secret_value(self):
        # secret_values may be a bare string, not just an iterable of strings.
        assert redact_secrets("supersecret", "supersecret") == REDACTION_PLACEHOLDER
