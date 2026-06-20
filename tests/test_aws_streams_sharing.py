"""AWS bounded stream (Kafka/Event Hubs) and Delta Sharing source rendering."""

from __future__ import annotations

from contractforge_aws import render_aws_contract
from contractforge_aws.sources import can_render_source


def _job(source: dict) -> str:
    c = {"source": source, "target": {"catalog": "lake", "schema": "bronze", "table": "ev"}, "mode": "scd0_append"}
    job = render_aws_contract(c).artifacts["lake_bronze_ev.glue_job.py"]
    compile(job, "glue_job.py", "exec")
    return job


def test_kafka_bounded_renders_batch_reader() -> None:
    job = _job(
        {
            "type": "kafka_bounded",
            "bootstrap_servers": "broker:9092",
            "topic": "events",
            "starting_offsets": "earliest",
            "max_offsets_per_trigger": 1000,
        }
    )
    assert ".format('kafka')" in job
    assert ".option('kafka.bootstrap.servers', 'broker:9092')" in job
    assert ".option('subscribe', 'events')" in job
    assert ".option('startingOffsets', 'earliest')" in job
    assert ".option('maxOffsetsPerTrigger', '1000')" in job
    assert "spark.read" in job


def test_eventhubs_bounded_renders_and_redacts_connection_string() -> None:
    job = _job(
        {
            "type": "eventhubs_bounded",
            "connection_string": "{{ secret:eh/conn }}",
            "event_hub_name": "events",
        }
    )
    assert ".format('eventhubs')" in job
    assert "_cf_resolve_secret('eh', 'conn')" in job
    assert "{{ secret:eh/conn }}" not in job
    # redacted review comment
    assert "***REDACTED***" in job


def test_delta_share_renders_reader() -> None:
    job = _job({"type": "delta_share", "profile_file": "s3://cfg/share.profile", "table": "share.schema.t"})
    assert ".format('deltaSharing')" in job
    assert ".option('table', 'share.schema.t')" in job
    assert ".option('profileFile', 's3://cfg/share.profile')" in job


def test_can_render_source_includes_streams_and_sharing() -> None:
    assert can_render_source({"type": "kafka_bounded", "bootstrap_servers": "b:9092", "topic": "t"}) is True
    assert can_render_source({"type": "eventhubs_bounded", "connection_string": "x", "event_hub_name": "e"}) is True
    assert can_render_source({"type": "delta_share", "profile_file": "p", "table": "t"}) is True
