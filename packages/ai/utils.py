"""Shared helper utilities for AI gateway."""
from __future__ import annotations

import hashlib
from typing import Any


def fingerprint(value: Any) -> str:
	s = str(value).encode("utf-8")
	return hashlib.sha256(s).hexdigest()
