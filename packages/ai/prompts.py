"""Prompt template utilities."""
from __future__ import annotations

from string import Template
from typing import Mapping


def render(template: str, ctx: Mapping[str, str]) -> str:
	return Template(template).safe_substitute(**ctx)
