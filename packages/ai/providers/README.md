Provider adapters live in this folder. Each module should expose a `Provider` class
that implements the BaseProvider interface (importable from ai.provider).

Providers are auto-discovered by ai.registry if they are enabled via environment
variables (see ai.config.is_provider_enabled).
