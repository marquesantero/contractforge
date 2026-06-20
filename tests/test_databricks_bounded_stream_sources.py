import pytest

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_databricks import DatabricksAdapter
from contractforge_databricks.sources import (
    eventhubs_bounded_options,
    kafka_bounded_options,
    render_bounded_stream_python,
)


def test_kafka_bounded_options_require_topic_or_assign() -> None:
    with pytest.raises(ValueError, match="topic"):
        kafka_bounded_options({"type": "kafka_bounded", "bootstrap_servers": "broker:9092"})


def test_render_kafka_bounded_python() -> None:
    code = render_bounded_stream_python(
        {
            "type": "kafka_bounded",
            "bootstrap_servers": "broker:9092",
            "topic": "orders",
            "starting_offsets": "earliest",
            "ending_offsets": "latest",
            "max_offsets_per_trigger": 1000,
        }
    )

    assert ".format('kafka')" in code
    assert ".option('kafka.bootstrap.servers', 'broker:9092')" in code
    assert ".option('startingOffsets', 'earliest')" in code
    assert ".option('maxOffsetsPerTrigger', '1000')" in code
    assert "not a continuous streaming artifact" in code


def test_eventhubs_bounded_options_redacted_review() -> None:
    options = eventhubs_bounded_options(
        {
            "type": "eventhubs_bounded",
            "connection_string": "Endpoint=sb://ns/;SharedAccessKey=raw-secret",
            "starting_position": '{"offset":"0"}',
            "ending_position": '{"offset":"100"}',
        }
    )
    code = render_bounded_stream_python(
        {
            "type": "eventhubs_bounded",
            "connection_string": "Endpoint=sb://ns/;SharedAccessKey=raw-secret",
        }
    )

    assert options["eventhubs.connectionString"].startswith("Endpoint=sb://")
    assert ".format('eventhubs')" in code
    assert "raw-secret" not in code.split("eventhubs_bounded_options_review", 1)[1]
    assert "***REDACTED***" in code


def test_databricks_bundle_renders_bounded_stream_artifact() -> None:
    adapter = DatabricksAdapter.from_evidence(
        target_table="main.bronze.orders",
        runtime_type="serverless",
        spark_conf={"spark.databricks.serverless.enabled": "true"},
    )
    contract = semantic_contract_from_mapping(
        {
            "source": {
                "type": "kafka_bounded",
                "bootstrap_servers": "broker:9092",
                "topic": "orders",
                "starting_offsets": "earliest",
                "ending_offsets": "latest",
            },
            "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
        }
    )

    artifacts = adapter.render_contract(contract)

    assert "main_bronze_orders.source_bounded_stream.py" in artifacts.artifacts
