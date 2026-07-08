"""Structural / smoke tests for cross-subsystem architecture boundaries (Task 14.2).

These are ordinary, example-based pytest tests (not property-based). They parse
the abstract syntax tree of the real subsystem source packages and assert the
platform's structural invariants hold:

1. **Dependency direction** (Req 12.2, 15.3): each leaf subsystem package
   (``crawler``, ``digital_twin``, ``check_engine``, ``fix_generator``,
   ``publishing_adapter``, ``governance``) imports shared symbols only from
   ``core`` and never reaches into another subsystem's internal modules. The
   ``api`` package and ``apps/e2e`` are the composition roots and are exempt —
   they may import the concrete subsystems to wire the loop together.
   Governance specifically must NOT import other subsystem packages; it reaches
   the Digital_Twin and Publishing_Adapter only through Core_Package Protocols.

2. **Publishing_Adapter is the sole write path** (Req 6.1): the WordPress-writing
   method *implementations* (``update_page_content`` / ``update_media_alt_text``)
   live only in ``publishing_adapter`` source. No other subsystem defines those
   write methods, and ``governance`` reaches WordPress only through the injected
   :class:`core.interfaces.PublishingAdapterPort` — its source imports the port
   from ``core.interfaces`` and never imports the ``publishing_adapter`` package.

3. **Storage is relational-only** (Req 3.7): the ``digital_twin`` package uses
   SQLAlchemy relational models and imports no graph-database or embeddings
   library (neo4j, networkx, faiss, chromadb, pinecone, sentence_transformers,
   numpy-as-embeddings, ...).

The repository root is discovered by walking upward from this test file so the
tests do not depend on the pytest invocation directory.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


# --- Repository / package discovery ------------------------------------------


def _find_repo_root() -> Path:
    """Walk upward to the workspace root (holds both pyproject.toml and
    docker-compose.yml)."""
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

#: Top-level import names owned by an orchestrator subsystem.
SUBSYSTEM_TOP_LEVEL = frozenset(
    {
        "crawler",
        "digital_twin",
        "check_engine",
        "fix_generator",
        "publishing_adapter",
        "governance",
        "api",
    }
)

#: Leaf subsystems: each may depend on ``core`` alone (Req 15.3). Maps the
#: importable package name to its source directory ``packages/<name>/<name>``.
LEAF_SUBSYSTEMS: dict[str, Path] = {
    name: REPO_ROOT / "packages" / name / name
    for name in (
        "crawler",
        "digital_twin",
        "check_engine",
        "fix_generator",
        "publishing_adapter",
        "governance",
    )
}


def _source_files(package_dir: Path) -> list[Path]:
    """Every Python source module under a package directory (recursive)."""
    return sorted(
        p for p in package_dir.rglob("*.py") if "__pycache__" not in p.parts
    )


def _top_level_name(dotted: str) -> str:
    """Return the first path segment of a dotted module name (``a.b.c`` -> ``a``)."""
    return dotted.split(".", 1)[0]


def _parse(module_path: Path) -> ast.AST:
    return ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))


def _imported_top_level(tree: ast.AST) -> list[tuple[str, str | None]]:
    """Extract absolute-import targets as (top_level_name, raw_module) tuples.

    Relative imports (``from . import x``) stay inside the owning package and are
    ignored here.
    """
    targets: list[tuple[str, str | None]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                targets.append((_top_level_name(alias.name), alias.name))
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue  # relative import — internal to the package
            if node.module:
                targets.append((_top_level_name(node.module), node.module))
    return targets


# --- Guards ------------------------------------------------------------------


def test_leaf_subsystem_source_dirs_exist() -> None:
    """Guard: every leaf subsystem source directory is present and non-empty."""
    for name, package_dir in LEAF_SUBSYSTEMS.items():
        assert package_dir.is_dir(), f"Missing source dir for '{name}': {package_dir}"
        assert _source_files(package_dir), f"No source modules found for '{name}'"


# --- 1. Dependency direction (Req 12.2, 15.3) --------------------------------


@pytest.mark.parametrize("subsystem", sorted(LEAF_SUBSYSTEMS))
def test_leaf_subsystem_imports_only_core_not_other_subsystems(subsystem: str) -> None:
    """Each leaf subsystem imports shared symbols only from ``core`` and never
    references another subsystem's internal modules (Req 12.2, 15.3).

    A subsystem may import its *own* top-level package (self-imports such as
    ``from crawler.robots import ...``); it may import ``core`` and any
    stdlib/third-party package. It may NOT import any *other* subsystem's
    top-level package.
    """
    package_dir = LEAF_SUBSYSTEMS[subsystem]
    forbidden = SUBSYSTEM_TOP_LEVEL - {subsystem}

    offenders: list[str] = []
    for module_path in _source_files(package_dir):
        for top_level, raw in _imported_top_level(_parse(module_path)):
            if top_level in forbidden:
                offenders.append(
                    f"{module_path.relative_to(REPO_ROOT)} imports '{raw}'"
                )

    assert not offenders, (
        f"Subsystem '{subsystem}' must depend on 'core' only, not on other "
        f"subsystems (Req 12.2, 15.3). Offending imports:\n  "
        + "\n  ".join(offenders)
    )


def test_governance_does_not_import_other_subsystems() -> None:
    """Governance reaches other subsystems only via Core Protocols, so its source
    imports no other subsystem package — including publishing_adapter (Req 12.2)."""
    package_dir = LEAF_SUBSYSTEMS["governance"]
    forbidden = SUBSYSTEM_TOP_LEVEL - {"governance"}

    offenders: list[str] = []
    for module_path in _source_files(package_dir):
        for top_level, raw in _imported_top_level(_parse(module_path)):
            if top_level in forbidden:
                offenders.append(
                    f"{module_path.relative_to(REPO_ROOT)} imports '{raw}'"
                )

    assert not offenders, (
        "Governance_Layer must not import any concrete subsystem; it uses Core "
        f"Protocols only (Req 12.2). Offending imports:\n  "
        + "\n  ".join(offenders)
    )


# --- 2. Publishing_Adapter is the sole write path (Req 6.1) ------------------

#: The WordPress-writing operations. Their concrete *implementations* must live
#: only in publishing_adapter source (Req 6.1, 6.2).
WP_WRITE_METHODS = frozenset({"update_page_content", "update_media_alt_text"})


def _defined_function_names(tree: ast.AST) -> set[str]:
    """Names of every function/method *defined* (implemented) in a module."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
    return names


def test_wp_write_methods_are_implemented_only_in_publishing_adapter() -> None:
    """The WordPress write methods are *implemented* only in publishing_adapter
    source; no other leaf subsystem defines them (Req 6.1).

    Governance calls these methods through the injected port (an attribute call),
    but must never define its own implementation — that would be a second write
    path. This asserts the write-method definitions live solely in
    publishing_adapter.
    """
    definers: dict[str, list[str]] = {method: [] for method in WP_WRITE_METHODS}
    for name, package_dir in LEAF_SUBSYSTEMS.items():
        for module_path in _source_files(package_dir):
            defined = _defined_function_names(_parse(module_path))
            for method in WP_WRITE_METHODS & defined:
                definers[method].append(name)

    for method, subsystems in definers.items():
        assert subsystems == ["publishing_adapter"], (
            f"WordPress write method '{method}' must be implemented only in "
            f"publishing_adapter (Req 6.1), but was defined in: "
            f"{sorted(set(subsystems))}"
        )


def test_publishing_adapter_owns_the_httpx_write_client() -> None:
    """The Publishing_Adapter source imports ``httpx`` — it is the concrete WP
    REST write client (Req 6.1). This anchors the sole-write-path claim to a real
    HTTP client living in publishing_adapter."""
    package_dir = LEAF_SUBSYSTEMS["publishing_adapter"]
    imports_httpx = any(
        top_level == "httpx"
        for module_path in _source_files(package_dir)
        for top_level, _raw in _imported_top_level(_parse(module_path))
    )
    assert imports_httpx, (
        "publishing_adapter must import httpx as the WordPress REST write client "
        "(Req 6.1)."
    )


def test_governance_reaches_wordpress_only_through_the_core_port() -> None:
    """Governance imports :class:`PublishingAdapterPort` from ``core.interfaces``
    and never imports the ``publishing_adapter`` package (Req 6.1, 12.2).

    This proves governance reaches the live site solely through the injected Core
    Protocol, so the Publishing_Adapter remains the only write path.
    """
    service = LEAF_SUBSYSTEMS["governance"].parent / "governance" / "service.py"
    assert service.is_file(), f"Expected governance service at {service}"
    tree = _parse(service)

    imports_port_from_core = False
    imports_publishing_adapter = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "core.interfaces" and any(
                alias.name == "PublishingAdapterPort" for alias in node.names
            ):
                imports_port_from_core = True
            if _top_level_name(node.module) == "publishing_adapter":
                imports_publishing_adapter = True
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if _top_level_name(alias.name) == "publishing_adapter":
                    imports_publishing_adapter = True

    assert imports_port_from_core, (
        "governance.service must import PublishingAdapterPort from core.interfaces "
        "(Req 6.1, 12.2)."
    )
    assert not imports_publishing_adapter, (
        "governance.service must NOT import the publishing_adapter package; it "
        "reaches WordPress only through the injected Core Protocol (Req 6.1, 12.2)."
    )


# --- 3. Storage is relational-only (Req 3.7) ---------------------------------

#: Graph-database and embeddings/vector-store libraries that must never appear in
#: the Digital_Twin — Milestone 0 storage is relational-only (Req 3.7).
RELATIONAL_ONLY_DENYLIST = frozenset(
    {
        # Graph databases / graph engines
        "neo4j",
        "py2neo",
        "networkx",
        "igraph",
        "graph_tool",
        "redisgraph",
        "gremlin_python",
        "gremlinpython",
        "arango",
        "pyArango",
        # Vector stores / embeddings / ML frameworks used for embeddings
        "faiss",
        "chromadb",
        "pinecone",
        "weaviate",
        "qdrant_client",
        "qdrant",
        "pgvector",
        "annoy",
        "hnswlib",
        "milvus",
        "pymilvus",
        "gensim",
        "sentence_transformers",
        "transformers",
        "torch",
        "tensorflow",
        "sklearn",
        "scikit_learn",
        "numpy",
        "scipy",
        "openai",
        "cohere",
    }
)


def test_digital_twin_imports_no_graph_db_or_embeddings() -> None:
    """The Digital_Twin imports no graph-database or embeddings library (Req 3.7)."""
    package_dir = LEAF_SUBSYSTEMS["digital_twin"]
    offenders: list[str] = []
    for module_path in _source_files(package_dir):
        for top_level, raw in _imported_top_level(_parse(module_path)):
            if top_level in RELATIONAL_ONLY_DENYLIST:
                offenders.append(
                    f"{module_path.relative_to(REPO_ROOT)} imports '{raw}'"
                )

    assert not offenders, (
        "Digital_Twin storage must be relational-only — no graph DB or embeddings "
        f"(Req 3.7). Offending imports:\n  " + "\n  ".join(offenders)
    )


def test_digital_twin_uses_sqlalchemy_relational_models() -> None:
    """The Digital_Twin uses SQLAlchemy for its relational models (Req 3.1, 3.7)."""
    package_dir = LEAF_SUBSYSTEMS["digital_twin"]
    imports_sqlalchemy = any(
        top_level == "sqlalchemy"
        for module_path in _source_files(package_dir)
        for top_level, _raw in _imported_top_level(_parse(module_path))
    )
    assert imports_sqlalchemy, (
        "Digital_Twin must use SQLAlchemy relational models (Req 3.1, 3.7)."
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
