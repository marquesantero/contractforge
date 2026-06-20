from __future__ import annotations

import pytest

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_databricks.runtime.available_now import run_available_now_stream


class FakeBatchDF:
    columns = ["id", "value"]

    def __init__(self) -> None:
        self.views = []

    def createOrReplaceTempView(self, name: str) -> None:
        self.views.append(name)

    def count(self) -> int:
        return 3


class FakeQuery:
    def __init__(self) -> None:
        self.awaited = False

    def awaitTermination(self) -> None:
        self.awaited = True


class FakeWriteStream:
    def __init__(self, batch_df: FakeBatchDF) -> None:
        self.batch_df = batch_df
        self.options = {}
        self.trigger_options = {}
        self.query = FakeQuery()

    def foreachBatch(self, callback):
        self.callback = callback
        return self

    def option(self, key: str, value: str):
        self.options[key] = value
        return self

    def trigger(self, **kwargs):
        self.trigger_options.update(kwargs)
        return self

    def start(self):
        self.callback(self.batch_df, 7)
        return self.query


class FakeStreamDF:
    def __init__(self) -> None:
        self.batch_df = FakeBatchDF()
        self.writeStream = FakeWriteStream(self.batch_df)


class FakeReader:
    def __init__(self, stream_df: FakeStreamDF) -> None:
        self.stream_df = stream_df

    def format(self, value: str):
        return self

    def option(self, key: str, value: str):
        return self

    def load(self, path: str):
        return self.stream_df


class FakeSpark:
    def __init__(self) -> None:
        self.stream_df = FakeStreamDF()
        self.readStream = FakeReader(self.stream_df)


class FakeEvidence:
    catalog = "main"
    schema = "ops"

    def __init__(self) -> None:
        self.stream_logs = []
        self.finished = []
        self.errors = []

    def write_stream_log(self, payload):
        self.stream_logs.append(payload)

    def finish_stream_log(self, *, stream_run_id: str, payload):
        self.finished.append((stream_run_id, payload))

    def write_error_log(self, payload):
        self.errors.append(payload)


def test_run_available_now_stream_processes_micro_batch() -> None:
    spark = FakeSpark()
    contract = semantic_contract_from_mapping(
        {
            "source": {
                "type": "incremental_files",
                "path": "s3://bucket/landing/orders",
                "format": "json",
                "progress_location": "s3://bucket/_checkpoints/orders",
            },
            "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
        }
    )
    prepared_seen = []

    result = run_available_now_stream(
        spark,
        contract,
        stream_run_id="stream-1",
        batch_ingestor=lambda prepared, batch_id: prepared_seen.append((prepared, batch_id))
        or {"status": "SUCCESS", "rows_read": prepared.rows_read, "rows_written": 2},
    )

    prepared, batch_id = prepared_seen[0]
    assert batch_id == 7
    assert prepared.source_view == "cf_stream_batch_stream_1_7"
    assert prepared.rows_read == 3
    assert spark.stream_df.writeStream.options["checkpointLocation"] == "s3://bucket/_checkpoints/orders"
    assert spark.stream_df.writeStream.trigger_options == {"availableNow": True}
    assert result["status"] == "SUCCESS"
    assert result["batches_processed"] == 1
    assert result["total_rows_written"] == 2
    assert result["framework_version"]
    assert result["ctrl_schema_version"] == 1


def test_run_available_now_stream_uses_file_stream_state_location_as_checkpoint() -> None:
    spark = FakeSpark()
    contract = semantic_contract_from_mapping(
        {
            "source": {
                "type": "s3",
                "intent": "file_stream",
                "path": "s3://bucket/landing/orders",
                "format": "json",
                "state": {
                    "storage": "external",
                    "location": {"type": "object_storage", "path": "s3://bucket/_checkpoints/orders"},
                },
            },
            "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
            "execution": {"preferred": "available_now", "fallback": "scheduled"},
        }
    )

    result = run_available_now_stream(
        spark,
        contract,
        stream_run_id="stream-1",
        batch_ingestor=lambda prepared, batch_id: {"status": "SUCCESS", "rows_read": prepared.rows_read, "rows_written": 2},
    )

    assert spark.stream_df.writeStream.options["checkpointLocation"] == "s3://bucket/_checkpoints/orders"
    assert result["status"] == "SUCCESS"


def test_run_available_now_stream_requires_checkpoint() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "incremental_files", "path": "s3://bucket/landing/orders", "format": "json"},
            "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
        }
    )

    with pytest.raises(ValueError, match="progress_location"):
        run_available_now_stream(FakeSpark(), contract, stream_run_id="stream-1", batch_ingestor=lambda prepared, batch_id: {})


def test_run_available_now_stream_returns_failed_payload_for_failed_batch() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {
                "type": "incremental_files",
                "path": "s3://bucket/landing/orders",
                "format": "json",
                "progress_location": "s3://bucket/_checkpoints/orders",
            },
            "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
        }
    )

    result = run_available_now_stream(
        FakeSpark(),
        contract,
        stream_run_id="stream-1",
        batch_ingestor=lambda prepared, batch_id: {"status": "FAILED", "error_message": "bad batch"},
    )

    assert result["status"] == "FAILED"
    assert result["error_message"] == "Available-now stream batch 7 failed: bad batch"
    assert result["batches_processed"] == 1


def test_run_available_now_stream_records_stream_evidence_and_prefers_child_metrics() -> None:
    evidence = FakeEvidence()
    queries = []
    contract = semantic_contract_from_mapping(
        {
            "source": {
                "type": "incremental_files",
                "path": "s3://bucket/landing/orders",
                "format": "json",
                "progress_location": "s3://bucket/_checkpoints/orders",
            },
            "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
        }
    )

    def query_one(statement: str):
        queries.append(statement)
        return {
            "batches_processed": 2,
            "total_rows_read": 8,
            "total_rows_written": 6,
            "total_rows_quarantined": 1,
        }

    result = run_available_now_stream(
        FakeSpark(),
        contract,
        stream_run_id="stream-1",
        batch_ingestor=lambda prepared, batch_id: {"status": "SUCCESS", "rows_read": 3, "rows_written": 2},
        evidence=evidence,
        query_one=query_one,
        runtime_metadata={"runtime_type": "serverless"},
    )

    assert evidence.stream_logs[0]["status"] == "RUNNING"
    assert evidence.stream_logs[0]["framework_version"]
    assert evidence.finished[0][0] == "stream-1"
    assert evidence.finished[0][1]["status"] == "SUCCESS"
    assert result["batches_processed"] == 2
    assert result["total_rows_written"] == 6
    assert "ctrl_ingestion_runs" in queries[0]
    assert "parent_run_id = 'stream-1'" in queries[0]


def test_run_available_now_stream_records_error_evidence() -> None:
    evidence = FakeEvidence()
    contract = semantic_contract_from_mapping(
        {
            "source": {
                "type": "incremental_files",
                "path": "s3://bucket/landing/orders",
                "format": "json",
                "progress_location": "s3://bucket/_checkpoints/orders",
            },
            "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
        }
    )

    result = run_available_now_stream(
        FakeSpark(),
        contract,
        stream_run_id="stream-1",
        batch_ingestor=lambda prepared, batch_id: {"status": "FAILED", "error_message": "bad batch"},
        evidence=evidence,
    )

    assert result["status"] == "FAILED"
    assert evidence.finished[0][1]["status"] == "FAILED"
    assert evidence.errors[0]["run_id"] == "stream-1"
    assert evidence.errors[0]["source_table"] == "s3://bucket/landing/orders"
