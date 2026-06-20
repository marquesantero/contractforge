from __future__ import annotations

import pytest

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_databricks.execution import execute_hash_diff_insert, render_hash_diff_insert_sql
from contractforge_databricks.execution.hash_diff_latest import (
    render_hash_diff_duplicate_target_keys_sql,
    render_null_ingestion_ts_ambiguity_sql,
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
            "target": {"catalog": "main", "schema": "silver", "table": "orders_hash"},
            "mode": "scd1_hash_diff",
            "merge_keys": ["order_id"],
            "hash_keys": ["amount", "status"],
        }
    )


def _ordered_contract():
    return semantic_contract_from_mapping(
        {
            "source": {"type": "connector", "connector": "postgres"},
            "target": {"catalog": "main", "schema": "silver", "table": "orders_hash"},
            "mode": "scd1_hash_diff",
            "merge_keys": ["order_id"],
            "hash_keys": ["amount", "status"],
            "transform": {
                "deduplicate": {
                    "keys": ["order_id"],
                    "order_by": "updated_at DESC NULLS LAST, ingestion_ts_utc DESC NULLS LAST",
                }
            },
        }
    )


def test_render_hash_diff_insert_sql() -> None:
    statement = render_hash_diff_insert_sql(
        target_table="main.silver.orders_hash",
        source_view="tmp.hash_stage",
        merge_keys=("order_id",),
        source_columns=("order_id", "amount", "row_hash"),
    )

    assert "INSERT INTO `main`.`silver`.`orders_hash` (`order_id`, `amount`, `row_hash`)" in statement
    assert "LEFT JOIN (" in statement
    assert "NOT (t.`row_hash` <=> s.`row_hash`)" in statement


def test_render_hash_diff_insert_sql_can_compare_target_latest_version() -> None:
    statement = render_hash_diff_insert_sql(
        target_table="main.silver.orders_hash",
        source_view="tmp.hash_stage",
        merge_keys=("order_id",),
        source_columns=("order_id", "amount", "row_hash"),
        latest_order_by="updated_at DESC NULLS LAST",
    )

    assert "row_number() OVER (PARTITION BY `order_id` ORDER BY updated_at DESC NULLS LAST)" in statement
    assert "WHERE __cf_latest_rank = 1" in statement


def test_render_hash_diff_insert_sql_requires_row_hash() -> None:
    with pytest.raises(ValueError, match="missing row_hash"):
        render_hash_diff_insert_sql(
            target_table="main.silver.orders_hash",
            source_view="tmp.hash_stage",
            merge_keys=("order_id",),
            source_columns=("order_id", "amount"),
        )


def test_render_hash_diff_insert_sql_requires_merge_keys_in_source() -> None:
    with pytest.raises(ValueError, match="merge_keys"):
        render_hash_diff_insert_sql(
            target_table="main.silver.orders_hash",
            source_view="tmp.hash_stage",
            merge_keys=("order_id",),
            source_columns=("amount", "row_hash"),
        )


def test_execute_hash_diff_insert_uses_runner() -> None:
    runner = FakeRunner()

    outcome = execute_hash_diff_insert(
        runner=runner,
        contract=_contract(),
        source_view="tmp.hash_stage",
        source_columns=("order_id", "amount", "status", "row_hash"),
    )

    assert outcome.operation == "core_managed_hash_diff_delta"
    assert runner.statements == [outcome.sql]


def test_execute_hash_diff_insert_uses_contract_dedup_order_for_target_latest() -> None:
    runner = FakeRunner()

    outcome = execute_hash_diff_insert(
        runner=runner,
        contract=_ordered_contract(),
        source_view="tmp.hash_stage",
        source_columns=("order_id", "amount", "status", "row_hash"),
    )

    assert outcome.metrics["target_latest_ordered"] is True
    assert "ORDER BY updated_at DESC NULLS LAST, ingestion_ts_utc DESC NULLS LAST" in outcome.sql


def test_execute_hash_diff_insert_uses_ingestion_sequence_target_fallback() -> None:
    runner = FakeRunner()

    outcome = execute_hash_diff_insert(
        runner=runner,
        contract=_contract(),
        source_view="tmp.hash_stage",
        source_columns=("order_id", "amount", "status", "row_hash"),
        target_schema={"order_id": "BIGINT", "row_hash": "STRING", "ingestion_sequence": "BIGINT"},
    )

    assert outcome.metrics["target_latest_reason"] == "ingestion_sequence"
    assert "ORDER BY ingestion_sequence DESC NULLS LAST" in outcome.sql


def test_execute_hash_diff_insert_uses_ingestion_ts_target_fallback() -> None:
    runner = FakeRunner()
    queries: list[str] = []

    def query_one(statement: str):
        queries.append(statement)
        return {"ambiguous_key_count": 0}

    outcome = execute_hash_diff_insert(
        runner=runner,
        contract=_contract(),
        source_view="tmp.hash_stage",
        source_columns=("order_id", "amount", "status", "row_hash"),
        target_schema={
            "order_id": "BIGINT",
            "row_hash": "STRING",
            "ingestion_ts_utc": "TIMESTAMP",
            "__run_id": "STRING",
        },
        query_one=query_one,
    )

    assert outcome.metrics["target_latest_reason"] == "ingestion_ts_utc"
    assert "ORDER BY ingestion_ts_utc DESC NULLS LAST, __run_id DESC NULLS LAST" in outcome.sql
    assert queries == [render_null_ingestion_ts_ambiguity_sql("main.silver.orders_hash", ("order_id",))]


def test_execute_hash_diff_insert_uses_source_loaded_target_fallback() -> None:
    runner = FakeRunner()

    outcome = execute_hash_diff_insert(
        runner=runner,
        contract=_contract(),
        source_view="tmp.hash_stage",
        source_columns=("order_id", "amount", "status", "row_hash", "source_loaded_at_utc"),
        target_schema={
            "order_id": "BIGINT",
            "row_hash": "STRING",
            "source_loaded_at_utc": "TIMESTAMP",
        },
        query_one=lambda statement: {"ambiguous_key_count": 0},
    )

    assert outcome.metrics["target_latest_reason"] == "source_loaded_at_utc"
    assert "ORDER BY source_loaded_at_utc DESC NULLS LAST" in outcome.sql


def test_execute_hash_diff_insert_rejects_ambiguous_null_ingestion_ts_history() -> None:
    with pytest.raises(ValueError, match="multiple target versions per key with null ingestion_ts_utc"):
        execute_hash_diff_insert(
            runner=FakeRunner(),
            contract=_contract(),
            source_view="tmp.hash_stage",
            source_columns=("order_id", "amount", "status", "row_hash"),
            target_schema={"order_id": "BIGINT", "row_hash": "STRING", "ingestion_ts_utc": "TIMESTAMP"},
            query_one=lambda statement: {"ambiguous_key_count": 1},
        )


def test_execute_hash_diff_insert_rejects_duplicate_target_keys_without_order() -> None:
    queries: list[str] = []

    def query_one(statement: str):
        queries.append(statement)
        return {"duplicate_key_count": 1}

    with pytest.raises(ValueError, match="no deterministic ordering exists"):
        execute_hash_diff_insert(
            runner=FakeRunner(),
            contract=_contract(),
            source_view="tmp.hash_stage",
            source_columns=("order_id", "amount", "status", "row_hash"),
            target_schema={"order_id": "BIGINT", "row_hash": "STRING"},
            query_one=query_one,
        )

    assert queries == [render_hash_diff_duplicate_target_keys_sql("main.silver.orders_hash", ("order_id",))]
