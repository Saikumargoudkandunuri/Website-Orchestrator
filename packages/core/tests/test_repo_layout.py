"""Structural / smoke tests for the repository layout (Task 1.3).

These are ordinary pytest tests (not property-based). They assert the
foundational scaffolding created in tasks 1.1 and 1.2 is present and correct:

* ``packages/core`` exists as the dependency-free foundation package
  (Requirement 15.1 — the monorepo is organised into the mandated subsystem
  packages, with Core_Package as the inward hub).
* ``.gitignore`` excludes ``.env`` so secrets are never committed
  (Requirement 14.3).
* ``docker-compose.yml`` defines a PostgreSQL service (Requirement 10.8 — the
  datastore is PostgreSQL from day one).

The repository root is discovered by walking upward from this test file so the
tests do not depend on the pytest invocation directory.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def _find_repo_root() -> Path:
    """Walk upward until we find the workspace root.

    The workspace root is the directory that contains both the root
    ``pyproject.toml`` and ``docker-compose.yml``.
    """
    for candidate in [Path(__file__).resolve(), *Path(__file__).resolve().parents]:
        if (candidate / "pyproject.toml").is_file() and (
            candidate / "docker-compose.yml"
        ).is_file():
            return candidate
    raise AssertionError(
        "Could not locate the workspace root (a directory containing both "
        "pyproject.toml and docker-compose.yml) above this test file."
    )


REPO_ROOT = _find_repo_root()


def test_packages_core_directory_exists() -> None:
    """Requirement 15.1: the Core_Package lives at ``packages/core``."""
    core_dir = REPO_ROOT / "packages" / "core"
    assert core_dir.is_dir(), f"Expected Core_Package directory at {core_dir}"

    # The importable package and its build config should be present too.
    assert (core_dir / "core" / "__init__.py").is_file(), (
        "packages/core should contain the importable `core` package"
    )
    assert (core_dir / "pyproject.toml").is_file(), (
        "packages/core should declare its own pyproject.toml"
    )


def test_gitignore_excludes_env() -> None:
    """Requirement 14.3: ``.gitignore`` must exclude the ``.env`` secrets file."""
    gitignore = REPO_ROOT / ".gitignore"
    assert gitignore.is_file(), f"Expected a .gitignore at {gitignore}"

    patterns = {
        line.strip()
        for line in gitignore.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }

    # `.env` must be ignored; the tracked `.env.example` template must be
    # explicitly re-included so it is NOT ignored.
    assert ".env" in patterns, ".gitignore must exclude the `.env` secrets file"
    assert "!.env.example" in patterns, (
        ".gitignore must re-include the tracked `.env.example` template"
    )


def test_docker_compose_defines_postgres_service() -> None:
    """Requirement 10.8: Docker Compose defines a PostgreSQL service."""
    yaml = pytest.importorskip(
        "yaml", reason="PyYAML is required to parse docker-compose.yml"
    )

    compose_path = REPO_ROOT / "docker-compose.yml"
    assert compose_path.is_file(), f"Expected docker-compose.yml at {compose_path}"

    compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    assert isinstance(compose, dict), "docker-compose.yml must parse to a mapping"

    services = compose.get("services")
    assert isinstance(services, dict) and services, (
        "docker-compose.yml must define at least one service"
    )

    def _uses_postgres(service: dict) -> bool:
        image = service.get("image")
        return isinstance(image, str) and "postgres" in image.lower()

    postgres_services = [
        name for name, svc in services.items() if isinstance(svc, dict) and _uses_postgres(svc)
    ]
    assert postgres_services, (
        "docker-compose.yml must define a service using a postgres image; "
        f"found services: {sorted(services)}"
    )
