from __future__ import annotations

import pytest

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_databricks.execution import execute_scd1_merge, render_scd1_merge_sql


class FakeRunner:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def sql(self, statement: str) -> None:
        self.statements.append(statement)


def test_render_scd1_merge_sql_quotes_identifiers() -> None:
    statement = render_scd1_merge_sql(
        target_table="main.silver.orders",
        source_view="tmp.orders_src",
        merge_keys=("order_id",),
        source_columns=("order_id", "amount", "updated_at"),
    )

    assert "MERGE INTO `main`.`silver`.`orders` t" in statement
    assert "USING `tmp`.`orders_src` s" in statement
    assert "t.`order_id` <=> s.`order_id`" in statement
    assert "WHEN MATCHED THEN UPDATE SET t.`amount` = s.`amount`, t.`updated_at` = s.`updated_at`" in statement
    assert "WHEN NOT MATCHED THEN INSERT (`order_id`, `amount`, `updated_at`)" in statement


def test_render_scd1_merge_sql_can_scope_target_partitions() -> None:
    statement = render_scd1_merge_sql(
        target_table="main.silver.orders",
        source_view="tmp.orders_src",
        merge_keys=("order_id",),
        source_columns=("order_id", "amount", "dt"),
        target_partition_predicate="t.`dt` IN ('2026-01-01')",
    )

    assert "ON t.`order_id` <=> s.`order_id` AND t.`dt` IN ('2026-01-01')" in statement


def test_execute_scd1_merge_uses_injected_runner() -> None:
    runner = FakeRunner()
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "connector", "connector": "postgres"},
            "target": {"catalog": "main", "schema": "silver", "table": "orders"},
            "mode": "scd1_upsert",
            "merge_keys": ["order_id"],
        }
    )

    outcome = execute_scd1_merge(
        runner=runner,
        contract=contract,
        source_view="tmp.orders_src",
        source_columns=("order_id", "amount"),
    )

    assert outcome.status == "SUCCESS"
    assert outcome.operation == "scd1_sql_merge"
    assert outcome.target == "main.silver.orders"
    assert runner.statements == [outcome.sql]


def test_execute_scd1_merge_rejects_missing_keys() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "connector", "connector": "postgres"},
            "target": {"table": "orders"},
            "mode": "scd1_upsert",
        }
    )

    with pytest.raises(ValueError, match="merge_keys"):
        execute_scd1_merge(
            runner=FakeRunner(),
            contract=contract,
            source_view="orders_src",
            source_columns=("order_id", "amount"),
        )


def test_execute_scd1_merge_rejects_other_modes() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "connector", "connector": "postgres"},
            "target": {"table": "orders"},
            "mode": "scd0_append",
        }
    )

    with pytest.raises(ValueError, match="only supports scd1_upsert"):
        execute_scd1_merge(
            runner=FakeRunner(),
            contract=contract,
            source_view="orders_src",
            source_columns=("order_id", "amount"),
        )
