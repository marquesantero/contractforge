from __future__ import annotations

from datetime import datetime, timezone

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_databricks.runtime.streaming import (
    prefer_child_stream_metrics,
    stream_metrics_from_batches,
    stream_result_payload,
    stream_start_payload,
)


def test_stream_metrics_from_batches_aggregates_child_batch_rows() -> None:
    metrics = stream_metrics_from_batches(
        [
            {"rows_read": 10, "rows_written": 8, "rows_quarantined": 2},
            {"rows_read": 5, "rows_written": 5, "rows_quarantined": 0},
        ]
    )

    assert metrics == {
        "batches_processed": 2,
        "total_rows_read": 15,
        "total_rows_written": 13,
        "total_rows_quarantined": 2,
    }


def test_prefer_child_stream_metrics_when_more_complete() -> None:
    local = {"batches_processed": 1, "total_rows_read": 10, "total_rows_written": 8, "total_rows_quarantined": 2}
    child = {"batches_processed": 2, "total_rows_read": 15, "total_rows_written": 13, "total_rows_quarantined": 2}

    assert prefer_child_stream_metrics(local, child)
    assert not prefer_child_stream_metrics(local, {"batches_processed": 0})


def test_stream_start_payload_from_semantic_contract() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {
                "type": "incremental_files",
                "path": "s3://bucket/landing/orders",
                "progress_location": "s3://bucket/_checkpoints/orders",
            },
            "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
            "idempotency_policy": "skip_if_success",
            "parent_run_id": "parent-1",
            "run_group_id": "group-1",
            "master_job_id": "job-1",
            "master_run_id": "master-1",
        }
    )

    payload = stream_start_payload(
        contract,
        stream_run_id="stream-1",
        started_at_utc=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
        idempotency_key="orders-2026-01-02",
        runtime_metadata={"runtime_type": "serverless", "notebook_name": "orders_ingest"},
    )

    assert payload["stream_run_id"] == "stream-1"
    assert payload["target_table"] == "main.bronze.orders"
    assert payload["target_catalog"] == "main"
    assert payload["notebook_name"] == "orders_ingest"
    assert payload["source_type"] == "incremental_files"
    assert payload["source_path"] == "s3://bucket/landing/orders"
    assert payload["checkpoint_location"] == "s3://bucket/_checkpoints/orders"
    assert payload["started_at_utc"] == "2026-01-02 03:04:05"
    assert payload["idempotency_key"] == "orders-2026-01-02"
    assert payload["idempotency_policy"] == "skip_if_success"
    assert payload["parent_run_id"] == "parent-1"
    assert payload["run_group_id"] == "group-1"
    assert payload["master_job_id"] == "job-1"
    assert payload["master_run_id"] == "master-1"


def test_stream_result_payload_aggregates_batches_and_duration() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "incremental_files", "path": "s3://bucket/landing/orders"},
            "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
        }
    )

    payload = stream_result_payload(
        contract,
        stream_run_id="stream-1",
        status="SUCCESS",
        started_at_utc=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
        batch_results=[{"rows_read": 10, "rows_written": 9, "rows_quarantined": 1}],
        stage_durations={"stream_run": 1.5},
    )

    assert payload["status"] == "SUCCESS"
    assert payload["batches_processed"] == 1
    assert payload["total_rows_read"] == 10
    assert payload["total_rows_written"] == 9
    assert payload["total_rows_quarantined"] == 1
    assert payload["stage_durations"] == {"stream_run": 1.5}
