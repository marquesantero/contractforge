from __future__ import annotations

import pytest

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_databricks.execution import execute_snapshot_soft_delete, render_snapshot_soft_delete_sql


class FakeRunner:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def sql(self, statement: str) -> None:
        self.statements.append(statement)


def _contract():
    return semantic_contract_from_mapping(
        {
            "source": {"type": "connector", "connector": "postgres"},
            "target": {"catalog": "main", "schema": "silver", "table": "orders_snapshot"},
            "mode": "snapshot_soft_delete",
            "merge_keys": ["order_id"],
        }
    )


def test_render_snapshot_soft_delete_sql_preserves_soft_delete_semantics() -> None:
    statement = render_snapshot_soft_delete_sql(
        target_table="main.silver.orders_snapshot",
        source_view="tmp.snapshot_stage",
        merge_keys=("order_id",),
        source_columns=("order_id", "amount", "is_active", "deleted_at", "row_hash"),
    )

    assert "WHEN NOT MATCHED BY SOURCE AND t.`is_active` = true THEN UPDATE SET" in statement
    assert "t.`is_active` = false" in statement
    assert "t.`deleted_at` = current_timestamp()" in statement
    assert "DELETE FROM" not in statement


def test_render_snapshot_soft_delete_sql_requires_prepared_columns() -> None:
    with pytest.raises(ValueError, match="missing required columns"):
        render_snapshot_soft_delete_sql(
            target_table="main.silver.orders_snapshot",
            source_view="tmp.snapshot_stage",
            merge_keys=("order_id",),
            source_columns=("order_id", "amount"),
        )


def test_render_snapshot_soft_delete_sql_requires_merge_keys_in_source() -> None:
    with pytest.raises(ValueError, match="merge_keys"):
        render_snapshot_soft_delete_sql(
            target_table="main.silver.orders_snapshot",
            source_view="tmp.snapshot_stage",
            merge_keys=("order_id",),
            source_columns=("amount", "is_active", "deleted_at", "row_hash"),
        )


def test_execute_snapshot_soft_delete_uses_runner() -> None:
    runner = FakeRunner()

    outcome = execute_snapshot_soft_delete(
        runner=runner,
        contract=_contract(),
        source_view="tmp.snapshot_stage",
        source_columns=("order_id", "amount", "is_active", "deleted_at", "row_hash"),
    )

    assert outcome.operation == "core_managed_snapshot_soft_delete_delta_merge"
    assert runner.statements == [outcome.sql]
