from __future__ import annotations

import pytest

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_databricks.execution import (
    execute_scd2_merge,
    render_scd2_delete_merge_sql,
    render_scd2_merge_sql,
    render_scd2_stage_sql,
)


class FakeRunner:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def sql(self, statement: str) -> None:
        self.statements.append(statement)


def _contract():
    return semantic_contract_from_mapping(
        {
            "source": {"type": "connector", "connector": "postgres"},
            "target": {"catalog": "main", "schema": "silver", "table": "orders_history"},
            "mode": "scd2_historical",
            "merge_keys": ["order_id"],
        }
    )


def _delete_contract():
    return semantic_contract_from_mapping(
        {
            "source": {"type": "connector", "connector": "postgres"},
            "target": {"catalog": "main", "schema": "silver", "table": "orders_history"},
            "mode": "scd2_historical",
            "merge_keys": ["order_id"],
            "scd2_sequence_by": "event_ts",
            "scd2_apply_as_deletes": "operation = 'DELETE'",
        }
    )


def test_render_scd2_merge_sql_requires_prepared_columns() -> None:
    with pytest.raises(ValueError, match="missing merge key staging columns"):
        render_scd2_merge_sql(
            target_table="main.silver.orders_history",
            source_view="tmp.scd2_stage",
            merge_keys=("order_id",),
            insert_columns=("order_id", "amount"),
        )


def test_render_scd2_merge_sql() -> None:
    statement = render_scd2_merge_sql(
        target_table="main.silver.orders_history",
        source_view="tmp.scd2_stage",
        merge_keys=("order_id",),
        insert_columns=(
            "order_id",
            "amount",
            "__merge_key_order_id",
            "valid_from",
            "valid_to",
            "is_current",
            "row_hash",
            "changed_columns",
        ),
    )

    assert "MERGE INTO `main`.`silver`.`orders_history` t" in statement
    assert "USING `tmp`.`scd2_stage` s" in statement
    assert "t.`order_id` <=> s.`__merge_key_order_id`" in statement
    assert "WHEN MATCHED AND t.`row_hash` <> s.`row_hash` THEN UPDATE SET" in statement
    assert "WHEN NOT MATCHED THEN INSERT (`order_id`, `amount`, `valid_from`, `valid_to`, `is_current`, `row_hash`, `changed_columns`)" in statement


def test_render_scd2_stage_sql_builds_changed_insert_and_update_rows() -> None:
    statement = render_scd2_stage_sql(
        target_table="main.silver.orders_history",
        source_view="prepared_orders",
        stage_view="__cf_scd2_stage",
        merge_keys=("order_id",),
        source_columns=(
            "order_id",
            "amount",
            "__merge_key_order_id",
            "valid_from",
            "valid_to",
            "is_current",
            "row_hash",
            "changed_columns",
        ),
    )

    assert "CREATE OR REPLACE TEMP VIEW `__cf_scd2_stage` AS" in statement
    assert "LEFT JOIN target_current t ON t.`order_id` <=> s.`order_id`" in statement
    assert "SELECT * FROM joined" in statement
    assert "AND (`__tgt_row_hash` IS NULL OR NOT (`row_hash` <=> `__tgt_row_hash`))" in statement
    assert "NULL AS `__merge_key_order_id`" in statement
    assert "`order_id` AS `__merge_key_order_id`" in statement
    assert "UNION ALL" in statement


def test_render_scd2_stage_sql_ignores_late_arriving_events() -> None:
    statement = render_scd2_stage_sql(
        target_table="main.silver.orders_history",
        source_view="prepared_orders",
        stage_view="__cf_scd2_stage",
        merge_keys=("order_id",),
        source_columns=(
            "order_id",
            "event_ts",
            "valid_from",
            "valid_to",
            "is_current",
            "row_hash",
            "changed_columns",
        ),
        sequence_by="event_ts",
        late_arriving_policy="ignore",
    )

    assert "`event_ts` AS `__tgt_sequence`" in statement
    assert "NOT (`__tgt_sequence` IS NOT NULL AND (`event_ts` IS NULL OR `event_ts` <= `__tgt_sequence`))" in statement


def test_render_scd2_stage_sql_rejects_late_arriving_events() -> None:
    statement = render_scd2_stage_sql(
        target_table="main.silver.orders_history",
        source_view="prepared_orders",
        stage_view="__cf_scd2_stage",
        merge_keys=("order_id",),
        source_columns=(
            "order_id",
            "event_ts",
            "valid_from",
            "valid_to",
            "is_current",
            "row_hash",
            "changed_columns",
        ),
        sequence_by="event_ts",
        late_arriving_policy="reject",
    )

    assert "late_arriving AS" in statement
    assert "CASE WHEN late_count > 0 THEN 1 / 0 ELSE 0 END" in statement


def test_render_scd2_stage_sql_excludes_delete_rows_from_upsert_stage() -> None:
    statement = render_scd2_stage_sql(
        target_table="main.silver.orders_history",
        source_view="prepared_orders",
        stage_view="__cf_scd2_stage",
        merge_keys=("order_id",),
        source_columns=(
            "order_id",
            "operation",
            "valid_from",
            "valid_to",
            "is_current",
            "row_hash",
            "changed_columns",
        ),
        apply_as_deletes="operation = 'DELETE'",
    )

    assert "WHERE NOT coalesce(CAST((operation = 'DELETE') AS BOOLEAN), false)" in statement


def test_render_scd2_delete_merge_sql_expires_current_rows() -> None:
    statement = render_scd2_delete_merge_sql(
        target_table="main.silver.orders_history",
        source_view="prepared_orders",
        merge_keys=("order_id",),
        apply_as_deletes="operation = 'DELETE'",
        sequence_by="event_ts",
        late_arriving_policy="ignore",
    )

    assert "MERGE INTO `main`.`silver`.`orders_history` t" in statement
    assert "WHERE coalesce(CAST((operation = 'DELETE') AS BOOLEAN), false)" in statement
    assert "NOT (`__tgt_sequence` IS NOT NULL AND (`event_ts` IS NULL OR `event_ts` <= `__tgt_sequence`))" in statement
    assert "t.`changed_columns` = 'DELETE'" in statement


def test_execute_scd2_merge_uses_runner() -> None:
    runner = FakeRunner()

    outcome = execute_scd2_merge(
        runner=runner,
        contract=_contract(),
        source_view="tmp.scd2_stage",
        insert_columns=(
            "order_id",
            "amount",
            "__merge_key_order_id",
            "valid_from",
            "valid_to",
            "is_current",
            "row_hash",
            "changed_columns",
        ),
    )

    assert outcome.operation == "core_managed_scd2_delta_merge"
    assert runner.statements[0].startswith("CREATE OR REPLACE TEMP VIEW")
    assert runner.statements[1] == outcome.sql
    assert runner.statements[2].startswith("DROP VIEW IF EXISTS")


def test_execute_scd2_merge_runs_delete_merge_before_upsert_stage() -> None:
    runner = FakeRunner()

    execute_scd2_merge(
        runner=runner,
        contract=_delete_contract(),
        source_view="tmp.scd2_stage",
        insert_columns=(
            "order_id",
            "event_ts",
            "operation",
            "__merge_key_order_id",
            "valid_from",
            "valid_to",
            "is_current",
            "row_hash",
            "changed_columns",
        ),
    )

    assert runner.statements[0].startswith("MERGE INTO `main`.`silver`.`orders_history`")
    assert "changed_columns` = 'DELETE'" in runner.statements[0]
    assert runner.statements[1].startswith("CREATE OR REPLACE TEMP VIEW")
    assert "NOT coalesce(CAST((operation = 'DELETE') AS BOOLEAN), false)" in runner.statements[1]
