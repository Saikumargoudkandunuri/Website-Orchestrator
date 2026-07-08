"""Property 56 — Every Digital_Twin table has a non-null ``tenant_id`` column.

Feature: website-orchestrator-milestone-0, Property 56: Every table has a
non-null tenant_id

Validates: Requirements 14.4

Requirement 14.4: Multi-tenancy is designed in from day one — every table in the
Digital_Twin relational schema SHALL carry a **non-null** ``tenant_id`` column so
all reads and writes can be scoped to a single tenant.

This property inspects the SQLAlchemy schema metadata directly
(:data:`digital_twin.models.Base.metadata`). For every table registered on the
declarative ``Base`` there must be a column literally named ``tenant_id`` and
that column must be ``NOT NULL`` (``nullable is False``).

The Hypothesis check samples over the set of registered tables across at least
100 examples and asserts the invariant on each sampled table. A separate plain
assertion iterates over *all* tables so coverage is total regardless of which
tables Hypothesis happens to draw.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import Table

from digital_twin.models import Base

# The registered tables. Guard that the schema is non-empty so the property is
# not vacuously true (a sampled_from over an empty sequence is invalid anyway).
_TABLES: list[Table] = list(Base.metadata.tables.values())
assert _TABLES, "Base.metadata must register at least one table"


def _has_non_null_tenant_id(table: Table) -> bool:
    """True iff ``table`` has a column named ``tenant_id`` that is NOT NULL."""
    if "tenant_id" not in table.columns:
        return False
    return table.columns["tenant_id"].nullable is False


@settings(max_examples=100)
@given(table=st.sampled_from(_TABLES))
def test_property_56_sampled_table_has_non_null_tenant_id(table: Table) -> None:
    """Any table sampled from the Digital_Twin schema has a non-null
    ``tenant_id`` column.

    Feature: website-orchestrator-milestone-0, Property 56: Every table has a
    non-null tenant_id

    Validates: Requirements 14.4
    """
    assert "tenant_id" in table.columns, (
        f"table {table.name!r} is missing a tenant_id column (Req 14.4)"
    )
    tenant_col = table.columns["tenant_id"]
    assert tenant_col.nullable is False, (
        f"table {table.name!r} has a nullable tenant_id column (Req 14.4)"
    )


def test_property_56_all_tables_have_non_null_tenant_id() -> None:
    """Total coverage: every registered table has a non-null ``tenant_id``.

    Feature: website-orchestrator-milestone-0, Property 56: Every table has a
    non-null tenant_id

    Validates: Requirements 14.4
    """
    assert _TABLES, "expected at least one table in Base.metadata"
    offenders = [t.name for t in _TABLES if not _has_non_null_tenant_id(t)]
    assert not offenders, (
        f"tables missing a non-null tenant_id column (Req 14.4): {offenders}"
    )
