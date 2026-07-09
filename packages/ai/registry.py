"""Auto-discover and register provider adapters in providers/ directory."""
from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from typing import Dict

from .provider import BaseProvider
from . import config


PROVIDERS_PKG = "ai.providers"


def discover_providers() -> Dict[str, BaseProvider]:
	providers: Dict[str, BaseProvider] = {}
	pkg = importlib.import_module(PROVIDERS_PKG)
	pkgpath = Path(pkg.__file__).parent
	for finder, name, ispkg in pkgutil.iter_modules([str(pkgpath)]):
		module_name = f"{PROVIDERS_PKG}.{name}"
		try:
			mod = importlib.import_module(module_name)
		except Exception:
			continue
		# Expect adapter to expose `Provider` class
		cls = getattr(mod, "Provider", None)
		if cls is None:
			continue
		try:
			instance: BaseProvider = cls()
		except Exception:
			continue
		# provider enabled check based on config
		if not config.is_provider_enabled(instance.name):
			# skip disabled providers
			continue
		providers[instance.name.lower()] = instance
	return providers


_cached_providers: Dict[str, BaseProvider] | None = None


def get_registry() -> Dict[str, BaseProvider]:
	global _cached_providers
	if _cached_providers is None:
		_cached_providers = discover_providers()
	return _cached_providers
