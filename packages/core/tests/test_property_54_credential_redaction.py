"""Property 54 — Credentials are redacted from logs while other content is retained.

Feature: website-orchestrator-milestone-0, Property 54: Credentials are redacted
from logs while other content is retained

Validates: Requirements 13.4, 13.5

Requirement 13.4: WHEN a log entry would otherwise include a credential value,
THE Website_Orchestrator SHALL redact that value before the entry is emitted.

Requirement 13.5: WHEN redacting a credential from a log entry, THE
Website_Orchestrator SHALL replace only the secret value with a placeholder and
SHALL retain all other (non-secret) content of the entry.

This property drives :func:`core.logging.configure_logging` with an explicit
``secret_values`` list and logs a payload that contains the secret both as a
whole field value and embedded as a substring inside surrounding non-secret
text. It then parses the emitted JSON line and asserts three things:

* the raw secret value appears NOWHERE in the serialized entry;
* every place the secret occurred is replaced by
  :data:`core.utils.REDACTION_PLACEHOLDER`; and
* all non-secret content (other field values and the message) is retained
  verbatim.
"""

from __future__ import annotations

import io
import json
import string

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from core import logging as wo_logging
from core.utils import REDACTION_PLACEHOLDER

# --- Strategies ---------------------------------------------------------------

# Secret alphabet: uppercase ASCII letters (excluding 'T') plus digits, and each
# secret is required to contain at least one such letter. This guarantees a
# generated secret can NEVER be a coincidental substring of the entry's
# structural text — the ISO-8601 timestamp (whose only uppercase letter is 'T'),
# the lowercase-hex ``trace_id``, or the lowercase JSON keys/level. Any match of
# the secret in the serialized line therefore reflects the real payload, not a
# structural accident. The secret is non-trivial (min length 6).
_SECRET_ALPHABET = string.ascii_uppercase.replace("T", "") + string.digits

_secrets = st.text(alphabet=_SECRET_ALPHABET, min_size=6, max_size=32).filter(
    lambda s: any(c.isalpha() for c in s)
)

# Reserved keys the renderer/pipeline populate themselves, plus our two special
# field names — non-secret field keys must avoid all of these so keys stay
# distinct and assertions are unambiguous.
_SECRET_FULL_KEY = "credential_full"
_SECRET_EMBEDDED_KEY = "credential_embedded"
_RESERVED_KEYS = {
    "event",
    "level",
    "timestamp",
    "logger",
    wo_logging.TRACE_ID_KEY,
    _SECRET_FULL_KEY,
    _SECRET_EMBEDDED_KEY,
}

# Non-secret text: any unicode text. Callers filter out strings containing the
# secret so "non-secret" genuinely holds.
_non_secret_text = st.text(max_size=40)

_field_keys = st.text(min_size=1, max_size=20).filter(lambda k: k not in _RESERVED_KEYS)


@settings(max_examples=200)
@given(
    secret=_secrets,
    message=_non_secret_text,
    non_secret_fields=st.dictionaries(
        keys=_field_keys, values=_non_secret_text, max_size=6
    ),
    prefix=_non_secret_text,
    suffix=_non_secret_text,
)
def test_property_54_credentials_redacted_other_content_retained(
    secret: str,
    message: str,
    non_secret_fields: dict[str, str],
    prefix: str,
    suffix: str,
) -> None:
    """For any secret and surrounding non-secret content, the emitted entry
    contains no raw secret, replaces each secret occurrence with the placeholder,
    and retains all non-secret content.

    Feature: website-orchestrator-milestone-0, Property 54: Credentials are
    redacted from logs while other content is retained

    Validates: Requirements 13.4, 13.5
    """
    # "Non-secret" must genuinely not contain the secret; otherwise these values
    # would legitimately be (partly) redacted and could not be asserted intact.
    assume(secret not in message)
    assume(secret not in prefix)
    assume(secret not in suffix)
    assume(all(secret not in key for key in non_secret_fields))
    assume(all(secret not in value for value in non_secret_fields.values()))
    # The placeholder must not pre-exist in non-secret content, so its presence
    # in the output unambiguously marks a redaction site.
    assume(REDACTION_PLACEHOLDER not in message)
    assume(REDACTION_PLACEHOLDER not in prefix)
    assume(REDACTION_PLACEHOLDER not in suffix)
    assume(all(REDACTION_PLACEHOLDER not in v for v in non_secret_fields.values()))

    # The secret embedded inside surrounding non-secret text. Redaction must
    # replace only the secret slice, leaving the prefix/suffix intact.
    embedded_value = f"{prefix}{secret}{suffix}"
    expected_embedded = f"{prefix}{REDACTION_PLACEHOLDER}{suffix}"

    # Fresh in-memory buffer per example keeps examples independent.
    buffer = io.StringIO()
    wo_logging.configure_logging(secret_values=[secret], stream=buffer)
    log = wo_logging.get_logger("property-54")

    # Compose one entry mixing: the secret as a whole field value, the secret
    # embedded as a substring, and arbitrary non-secret fields — all under a
    # stable, uppercase-free trace id so the secret cannot collide with it.
    fields = dict(non_secret_fields)
    fields[_SECRET_FULL_KEY] = secret
    fields[_SECRET_EMBEDDED_KEY] = embedded_value

    with wo_logging.operation_trace(trace_id="0" * 32):
        log.info(message, **fields)

    raw = buffer.getvalue().strip()

    # A single well-formed JSON object.
    entry = json.loads(raw)
    assert isinstance(entry, dict)

    # (13.4) The raw secret value must not appear anywhere in the emitted line.
    assert secret not in raw

    # (13.5) The whole-value credential is replaced by the placeholder.
    assert entry[_SECRET_FULL_KEY] == REDACTION_PLACEHOLDER

    # (13.5) The embedded credential has only its secret slice replaced; the
    # surrounding non-secret text is retained.
    assert entry[_SECRET_EMBEDDED_KEY] == expected_embedded
    assert REDACTION_PLACEHOLDER in entry[_SECRET_EMBEDDED_KEY]

    # (13.5) All non-secret content is retained verbatim.
    assert entry["event"] == message
    for key, value in non_secret_fields.items():
        assert entry[key] == value
