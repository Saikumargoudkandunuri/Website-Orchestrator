"""Core_Package constants — system-wide default thresholds and limits.

These are the canonical defaults referenced across subsystems (Req 15.1).
Runtime configuration (see ``config.py``) may override a subset of these via
environment variables, but the values here are the authoritative fallbacks.
"""

from __future__ import annotations

# --- Crawler timing / rate limiting -------------------------------------------

#: Minimum delay between requests to a single host, in milliseconds. This is a
#: hard floor that is never reduced for the sake of speed (Req 1.9, 1.10).
DEFAULT_RATE_LIMIT_MS: int = 1000

#: Observed response-time threshold, in milliseconds, above which the crawler
#: doubles its per-host delay as a degradation backoff (Req 1.11).
DEGRADATION_THRESHOLD_MS: int = 2000

#: Per-request timeout, in seconds, after which a page fetch is abandoned
#: (Req 1.12).
REQUEST_TIMEOUT_S: int = 30

#: Default timeout, in seconds, for a link-status probe (Req 2.3).
LINK_TIMEOUT_S: int = 10

# --- Redirect handling --------------------------------------------------------

#: Maximum number of redirect hops recorded before a chain is marked truncated
#: (Req 2.2).
REDIRECT_HARD_CAP: int = 10

# --- Check_Engine thresholds --------------------------------------------------

#: Pages with fewer than this many words are flagged as thin content (Req 4.3).
THIN_CONTENT_MIN_WORDS: int = 300

#: A redirect chain with at least this many hops is flagged as an issue
#: (Req 4.6).
REDIRECT_CHAIN_THRESHOLD: int = 3

# --- Fix_Generator limits -----------------------------------------------------

#: Maximum length, in characters, of generated alt text (Req 5.4).
MAX_ALT_TEXT_LEN: int = 125
