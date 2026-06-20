from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_databricks.metrics import (
    extract_delta_row_metrics,
    latest_operation_metrics_from_history_row,
    logical_row_metrics,
    normalize_rows_written,
    render_delta_history_query,
    resolve_write_metrics,
)


def _contract(mode: str):
    payload = {
        "source": {"type": "connector", "connector": "postgres"},
        "target": {"catalog": "main", "schema": "silver", "table": "orders"},
        "mode": mode,
    }
    if mode in {"scd1_upsert", "scd2_historical"}:
        payload["merge_keys"] = ["id"]
    return semantic_contract_from_mapping(payload)


def test_extract_delta_row_metrics_maps_operation_metrics() -> None:
    metrics = extract_delta_row_metrics(
        {"operationMetrics": {"numTargetRowsInserted": "2", "numTargetRowsUpdated": "3", "numTargetRowsDeleted": "1"}}
    )

    assert metrics == {
        "rows_inserted": 2,
        "rows_updated": 3,
        "rows_deleted": 1,
        "rows_expired": 0,
    }


def test_logical_row_metrics_for_append_like_modes() -> None:
    metrics = logical_row_metrics(_contract("scd1_hash_diff"), 7)

    assert metrics["rows_inserted"] == 7
    assert metrics["rows_affected"] == 7


def test_databricks_logical_row_metrics_for_replace_partitions_are_insert_like() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "connector", "connector": "postgres"},
            "target": {"catalog": "main", "schema": "silver", "table": "orders"},
            "mode": "scd1_upsert",
            "merge_keys": ["id"],
            "extensions": {"databricks": {"merge_strategy": "replace_partitions"}},
        }
    )

    metrics = logical_row_metrics(contract, 7)

    assert metrics["rows_inserted"] == 7
    assert metrics["rows_affected"] == 7


def test_resolve_write_metrics_preserves_delta_metrics_and_adds_logical_metrics() -> None:
    row_metrics, operation_metrics, source = resolve_write_metrics(
        _contract("scd1_upsert"),
        5,
        {"version": 12, "operationMetrics": {"numTargetRowsInserted": "2", "numTargetRowsUpdated": "3"}},
    )

    assert source == "mixed"
    assert row_metrics["rows_inserted"] == 2
    assert row_metrics["rows_updated"] == 3
    assert row_metrics["rows_affected"] == 5
    assert operation_metrics["logicalMetrics"]["rows_affected"] == 5
    assert operation_metrics["normalizedRowMetrics"]["rows_affected"] == 5


def test_resolve_write_metrics_marks_scd2_updates_as_expired() -> None:
    row_metrics, operation_metrics, source = resolve_write_metrics(
        _contract("scd2_historical"),
        6,
        {"operationMetrics": {"numTargetRowsInserted": "4", "numTargetRowsUpdated": "2"}},
    )

    assert source == "mixed"
    assert row_metrics["rows_expired"] == 2
    assert operation_metrics["normalizedRowMetrics"]["rows_expired"] == 2


def test_normalize_rows_written_uses_rows_affected() -> None:
    assert normalize_rows_written(0, {"rows_affected": 250000}) == 250000


def test_render_delta_history_query() -> None:
    assert render_delta_history_query(target_table="main.silver.orders") == (
        "DESCRIBE HISTORY `main`.`silver`.`orders` LIMIT 1"
    )


def test_latest_operation_metrics_from_history_row() -> None:
    metrics = latest_operation_metrics_from_history_row(
        {
            "version": 12,
            "operation": "MERGE",
            "operationMetrics": {"numTargetRowsInserted": "2"},
            "ignored": "value",
        }
    )

    assert metrics == {
        "version": 12,
        "operation": "MERGE",
        "operationMetrics": {"numTargetRowsInserted": "2"},
    }
