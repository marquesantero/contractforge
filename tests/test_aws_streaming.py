"""AWS available_now structured-streaming job rendering."""

from __future__ import annotations

from contractforge_aws import render_aws_contract


def _contract(source: dict, *, mode: str = "scd0_append", **extra) -> dict:
    c = {
        "source": source,
        "target": {"catalog": "lake", "schema": "bronze", "table": "events"},
        "mode": mode,
    }
    c.update(extra)
    return c


def _job(source: dict, **extra) -> str:
    job = render_aws_contract(_contract(source, **extra)).artifacts["lake_bronze_events.glue_job.py"]
    compile(job, "glue_job.py", "exec")
    return job


def test_kafka_available_now_renders_streaming_job() -> None:
    job = _job(
        {
            "type": "kafka_available_now",
            "bootstrap_servers": "broker:9092",
            "topic": "events",
            "checkpoint_location": "s3://state/events",
            "limits": {"max_offsets_per_trigger": 1000},
        }
    )
    assert "spark.readStream" in job
    assert ".format('kafka')" in job
    assert "def _process_batch(df, batch_id):" in job
    assert ".trigger(availableNow=True)" in job
    assert ".option('checkpointLocation', 's3://state/events')" in job
    assert ".option('maxOffsetsPerTrigger', '1000')" in job
    assert ".foreachBatch(_process_batch)" in job
    assert "query.awaitTermination()" in job
    assert "job.commit()" in job
    assert "def _cf_persist_stream_batch_evidence(spark, streams_table, row):" in job
    assert "ctrl_ingestion_streams" in job
    assert "_cf_stream_totals['rows_read'] += _cf_batch_rows_read" in job
    assert "_cf_summary.update({" in job
    assert "'contractforge_rows_written': int(_cf_stream_totals.get('rows_written', 0))" in job
    assert "'trigger': 'available_now'," in job
    # the per-batch write runs inside the foreachBatch function (indented)
    assert "    (" in job  # indented append block


def test_bounded_trigger_available_now_also_streams() -> None:
    job = _job(
        {
            "type": "kafka_bounded",
            "bootstrap_servers": "broker:9092",
            "topic": "events",
            "trigger": "available_now",
            "checkpoint_location": "s3://state/events",
        }
    )
    assert "spark.readStream" in job
    assert ".trigger(availableNow=True)" in job


def test_available_now_without_checkpoint_is_review_only() -> None:
    artifacts = render_aws_contract(
        _contract({"type": "kafka_available_now", "bootstrap_servers": "b:9092", "topic": "e"})
    )
    assert "lake_bronze_events.glue_job.py" not in artifacts.artifacts
    assert "lake_bronze_events.glue_job.todo.md" in artifacts.artifacts


def test_available_now_overwrite_is_review_only() -> None:
    artifacts = render_aws_contract(
        _contract(
            {
                "type": "kafka_available_now",
                "bootstrap_servers": "b:9092",
                "topic": "e",
                "checkpoint_location": "s3://c/p",
            },
            mode="scd0_overwrite",
        )
    )
    assert "lake_bronze_events.glue_job.py" not in artifacts.artifacts
