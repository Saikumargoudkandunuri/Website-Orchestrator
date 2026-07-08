"""Stable, addressable identifier scheme (§1.4, §4.1).

Agents and fixes must reference precise targets (a page, an image, a heading, a
link, a schema block) without re-parsing HTML on every operation. These helpers
produce deterministic, stable identifiers:

* :func:`page_id_for` — a stable id for a page from its tenant + normalized URL.
  (Milestone 1's Digital_Twin generates internal ``Page.id`` values that are not
  exposed by URL/id lookup, so the intelligence layer derives its own stable,
  URL-addressable page id. See ``MILESTONE_2.md`` for this reconciliation.)
* :func:`element_id_for` — a stable id for a sub-entity of a page, from the
  page id + element type + a content/positional fingerprint.

Both are pure functions of their inputs, so the same page/element always maps to
the same id across crawls — which is what lets a versioned KnowledgeObject track
the *same* element's change over time.
"""

from __future__ import annotations

import hashlib

from core.utils import normalize_url

__all__ = ["page_id_for", "element_id_for"]


def page_id_for(tenant_id: str, url: str) -> str:
    """Return a stable page id for ``(tenant_id, normalized url)``."""
    key = f"{tenant_id}\x00{normalize_url(url)}"
    return "page_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]


def element_id_for(page_id: str, element_type: str, fingerprint: str) -> str:
    """Return a stable element id within ``page_id``.

    ``element_type`` is e.g. ``"image"``/``"heading"``/``"link"``/``"schema"``
    and ``fingerprint`` is a stable content/positional signature (e.g. an image
    URL, a heading's ``level:text``, a link href).
    """
    key = f"{page_id}\x00{element_type}\x00{fingerprint}"
    return f"{element_type}_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]
