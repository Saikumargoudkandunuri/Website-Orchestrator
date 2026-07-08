"""Structural tests for the Digital_Twin relational schema (task 4.1).

These verify the deliverables of "Create SQLAlchemy models and migrations":
the six tables exist, each has a non-null ``tenant_id`` (Req 14.4), the ORM
metadata is constructible and can create the schema, and the hand-authored
initial migration stays in lockstep with the models. They are ordinary example
tests; the universal ``tenant_id`` property (Property 56) is covered separately.
"""

from __future__ import annotations

from sqlalchemy import create_engine, inspect

from digital_twin.models import Base

EXPECTED_TABLES = {
    "pages",
    "links",
    "page_metadata",
    "issues",
    "suggested_fixes",
    "audit_trail",
}


def test_metadata_defines_the_six_relational_tables() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_every_table_has_a_non_null_tenant_id() -> None:
    for name, table in Base.metadata.tables.items():
        assert "tenant_id" in table.c, f"{name} is missing tenant_id"
        assert table.c.tenant_id.nullable is False, f"{name}.tenant_id is nullable"


def test_metadata_can_create_all_tables() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    created = set(inspect(engine).get_table_names())
    assert EXPECTED_TABLES <= created


def test_migration_chain_columns_match_models() -> None:
    """Parity guard: the migration chain must define exactly the model columns.

    The migrations were hand-authored (no live PostgreSQL at authoring time), so
    this guards them against the ORM models by static analysis. It reads *every*
    version file and folds each schema op into a per-table column set —
    ``create_table``/``add_column`` add columns and ``drop_column`` removes
    them — then asserts the net result equals the model columns for every table.
    Reading the whole chain (not just the initial migration) keeps the guard
    correct as the schema evolves through additive migrations (e.g. the
    Milestone 1 ``generation_model`` / ``generation_confidence`` columns added in
    ``0002``). The authoritative model/migration sync is additionally proven by
    the autogenerate check in ``test_migration_sync.py``.
    """
    import ast
    from pathlib import Path

    versions_dir = (
        Path(__file__).resolve().parents[1] / "migrations" / "versions"
    )

    def _const(node: ast.AST) -> object | None:
        return node.value if isinstance(node, ast.Constant) else None

    def _column_name(arg: ast.AST) -> str | None:
        """Return the column name from an ``sa.Column("<name>", ...)`` call."""
        if (
            isinstance(arg, ast.Call)
            and isinstance(arg.func, ast.Attribute)
            and arg.func.attr == "Column"
            and arg.args
        ):
            return _const(arg.args[0])  # type: ignore[return-value]
        return None

    created: set[str] = set()
    migration_columns: dict[str, set[str]] = {}

    # Process migrations in filename order so that add/drop apply after create.
    for migration in sorted(versions_dir.glob("*.py")):
        if migration.name.startswith("__"):
            continue
        tree = ast.parse(migration.read_text(encoding="utf-8"))
        # Only consider the forward migration: walking the whole file would let
        # a downgrade()'s drop_column cancel its upgrade()'s add_column.
        upgrade_fn = next(
            (
                n
                for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name == "upgrade"
            ),
            None,
        )
        if upgrade_fn is None:
            continue
        for node in ast.walk(upgrade_fn):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.args
                and isinstance(node.args[0], ast.Constant)
            ):
                continue
            op_name = node.func.attr
            table_name = node.args[0].value

            if op_name == "create_table":
                created.add(table_name)
                cols = migration_columns.setdefault(table_name, set())
                for arg in node.args[1:]:
                    name = _column_name(arg)
                    if name is not None:
                        cols.add(name)
            elif op_name == "add_column" and len(node.args) >= 2:
                name = _column_name(node.args[1])
                if name is not None:
                    migration_columns.setdefault(table_name, set()).add(name)
            elif op_name == "drop_column" and len(node.args) >= 2:
                name = _const(node.args[1])
                if isinstance(name, str):
                    migration_columns.get(table_name, set()).discard(name)

    assert created == EXPECTED_TABLES
    for name, table in Base.metadata.tables.items():
        model_cols = set(table.c.keys())
        assert migration_columns[name] == model_cols, (
            f"{name}: migration {migration_columns[name]} != model {model_cols}"
        )
