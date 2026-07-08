"""Ad-hoc WordPress connectivity check — run this BEFORE starting the system.

This tiny script proves three things end to end, in order:

1. Configuration loads: ``WP_BASE_URL`` / ``WP_USERNAME`` /
   ``WP_APPLICATION_PASSWORD`` are present in the environment or ``.env``.
2. The WordPress REST API is reachable and HTTP Basic authentication with the
   Application_Password succeeds.
3. The credentials can read pages via ``/wp-json/wp/v2/pages``.

On success it prints the titles of the pages it read and exits ``0``. On any
failure it prints a short, credential-free diagnosis and exits non-zero.

Usage (from the repository root)::

    uv run python scripts/check_wp_connection.py

It deliberately reuses the exact same config loader
(:func:`core.config.load_settings`) and REST client
(:class:`publishing_adapter.WordPressClient`) that the API uses, so a success
here is strong evidence the API will authenticate too. The Application_Password
is held as a :class:`~pydantic.SecretStr` and is never printed.
"""

from __future__ import annotations

import sys

from core.config import load_settings
from core.exceptions import (
    ConfigError,
    PublishingError,
    WPAuthError,
    WPRateLimitError,
)
from publishing_adapter import WordPressClient


def main() -> int:
    # 1. Load configuration. Fails fast, naming any missing key but never a value.
    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"[FAIL] Configuration error: {exc}")
        print(
            "       Set WP_BASE_URL, WP_USERNAME and WP_APPLICATION_PASSWORD in "
            "your .env (see .env.example)."
        )
        return 2

    print(f"[..]  Target site : {settings.wp_base_url}")
    print(f"[..]  Username    : {settings.wp_username}")
    print("[..]  Auth        : Application_Password (HTTP Basic)")
    print("[..]  Calling     : /wp-json/wp/v2/pages ...")

    client = WordPressClient(
        settings.wp_base_url,
        settings.wp_username,
        settings.wp_application_password,
    )

    # 2 + 3. Authenticate and read pages via /wp-json/wp/v2/pages.
    try:
        pages = client.list_pages()
    except WPAuthError as exc:
        print(f"[FAIL] Authentication failed: {exc}")
        print(
            "       Check WP_USERNAME and that WP_APPLICATION_PASSWORD is a "
            "current Application Password for that user."
        )
        return 1
    except WPRateLimitError as exc:
        print(f"[FAIL] Rate limited by WordPress: {exc}")
        return 1
    except PublishingError as exc:
        # Covers WPClientError (network/timeout/other HTTP), WPNotFoundError and
        # MissingCredentialError — all with credential-free messages.
        print(f"[FAIL] Could not reach the WordPress REST API: {exc}")
        print(
            f"       Is {settings.wp_base_url} up and is /wp-json/wp/v2/pages "
            "enabled?"
        )
        return 1
    finally:
        client.close()

    # Success — print the page titles.
    print(f"[OK]  Authenticated and read {len(pages)} page(s):")
    if not pages:
        print("      (the site returned no pages)")
    for page in pages:
        title = (page.title or "").strip() or "(untitled)"
        print(f"      - #{page.id}: {title}")

    print()
    print(
        "[OK]  Connectivity check passed: authentication, REST API and "
        "credentials all work."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
