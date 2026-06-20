"""Available-now Kafka and Event Hubs stream connector wiring at the core layer."""

from __future__ import annotations

import pytest

from contractforge_core.connectors import (
    AVAILABLE_NOW_STREAM_TYPES,
    BOUNDED_STREAM_TYPES,
    STREAM_SOURCE_TYPES,
    eventhubs_bounded_options,
    is_available_now_stream_source,
    is_bounded_stream_source,
    is_eventhubs_stream_source,
    is_kafka_stream_source,
    kafka_bounded_options,
    stream_source_format,
)
from contractforge_core.connectors.registry import connector_catalog_entry
from contractforge_core.contracts import semantic_contract_from_mapping


def test_available_now_stream_types_are_disjoint_from_bounded() -> None:
    assert AVAILABLE_NOW_STREAM_TYPES == frozenset({"kafka_available_now", "eventhubs_available_now"})
    assert STREAM_SOURCE_TYPES == BOUNDED_STREAM_TYPES | AVAILABLE_NOW_STREAM_TYPES
    assert BOUNDED_STREAM_TYPES.isdisjoint(AVAILABLE_NOW_STREAM_TYPES)


def test_is_available_now_stream_source_and_format_helpers() -> None:
    kafka_an = {"type": "kafka_available_now"}
    eh_an = {"type": "eventhubs_available_now"}
    kafka_b = {"type": "kafka_bounded"}
    eh_b = {"type": "eventhubs_bounded"}

    assert is_available_now_stream_source(kafka_an)
    assert is_available_now_stream_source(eh_an)
    assert not is_available_now_stream_source(kafka_b)
    assert not is_available_now_stream_source(eh_b)

    assert is_kafka_stream_source(kafka_an) and is_kafka_stream_source(kafka_b)
    assert is_eventhubs_stream_source(eh_an) and is_eventhubs_stream_source(eh_b)

    assert is_bounded_stream_source(kafka_b)
    assert not is_bounded_stream_source(kafka_an)

    assert stream_source_format(kafka_an) == "kafka"
    assert stream_source_format(eh_an) == "eventhubs"


def test_stream_source_format_rejects_non_stream_types() -> None:
    with pytest.raises(ValueError, match="not a kafka/eventhubs"):
        stream_source_format({"type": "rest_api"})


def test_kafka_bounded_options_accept_available_now_variant() -> None:
    options = kafka_bounded_options(
        {
            "type": "kafka_available_now",
            "bootstrap_servers": "broker:9092",
            "topic": "orders",
            "starting_offsets": "earliest",
            "max_offsets_per_trigger": 5000,
            "checkpoint_location": "dbfs:/checkpoints/orders-events",
        }
    )

    assert options["kafka.bootstrap.servers"] == "broker:9092"
    assert options["subscribe"] == "orders"
    assert options["startingOffsets"] == "earliest"
    assert options["maxOffsetsPerTrigger"] == "5000"
    # checkpoint_location is consumed by the writer, not the reader options.
    assert "checkpoint_location" not in options
    assert "checkpointLocation" not in options


def test_kafka_stream_limits_feed_reader_options() -> None:
    options = kafka_bounded_options(
        {
            "type": "kafka_available_now",
            "bootstrap_servers": "broker:9092",
            "topic": "orders",
            "limits": {"max_offsets_per_trigger": 2500},
            "checkpoint_location": "dbfs:/checkpoints/orders-events",
        }
    )

    assert options["maxOffsetsPerTrigger"] == "2500"

    with pytest.raises(ValueError, match="conflicts"):
        kafka_bounded_options(
            {
                "type": "kafka_available_now",
                "bootstrap_servers": "broker:9092",
                "topic": "orders",
                "max_offsets_per_trigger": 100,
                "limits": {"max_offsets_per_trigger": 200},
            }
        )


def test_eventhubs_bounded_options_accept_available_now_variant() -> None:
    options = eventhubs_bounded_options(
        {
            "type": "eventhubs_available_now",
            "connection_string": "Endpoint=sb://ns/;SharedAccessKey=secret",
            "event_hub_name": "orders",
            "starting_position": '{"offset":"0"}',
            "checkpoint_location": "dbfs:/checkpoints/orders-events",
        }
    )

    assert options["eventhubs.connectionString"].startswith("Endpoint=sb://")
    assert options["eventhubs.name"] == "orders"
    assert options["eventhubs.startingPosition"] == '{"offset":"0"}'
    assert "checkpoint_location" not in options


def test_eventhubs_stream_limits_feed_reader_options() -> None:
    options = eventhubs_bounded_options(
        {
            "type": "eventhubs_available_now",
            "connection_string": "Endpoint=sb://ns/;SharedAccessKey=secret",
            "event_hub_name": "orders",
            "limits": {"max_events_per_trigger": 1000},
            "checkpoint_location": "dbfs:/checkpoints/orders-events",
        }
    )

    assert options["maxEventsPerTrigger"] == "1000"

    with pytest.raises(ValueError, match="conflicts"):
        eventhubs_bounded_options(
            {
                "type": "eventhubs_available_now",
                "connection_string": "Endpoint=sb://ns/;SharedAccessKey=secret",
                "event_hub_name": "orders",
                "max_events_per_trigger": 100,
                "limits": {"max_events_per_trigger": 200},
            }
        )


def test_kafka_available_now_round_trips_through_semantic_contract() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {
                "type": "kafka_available_now",
                "bootstrap_servers": "broker:9092",
                "topic": "orders",
                "starting_offsets": "earliest",
                "checkpoint_location": "dbfs:/checkpoints/orders-events",
                "options": {"kafka.security.protocol": "SASL_SSL"},
            },
            "target": {"catalog": "main", "schema": "bronze", "table": "b_orders"},
            "mode": "scd0_append",
        }
    )

    raw = contract.source.raw
    assert raw["type"] == "kafka_available_now"
    assert raw["bootstrap_servers"] == "broker:9092"
    assert raw["checkpoint_location"] == "dbfs:/checkpoints/orders-events"
    assert raw["options"]["kafka.security.protocol"] == "SASL_SSL"


def test_connector_catalog_documents_available_now_streams() -> None:
    kafka_entry = connector_catalog_entry("kafka_available_now")
    assert kafka_entry["family"] == "available_now_stream"
    assert "checkpoint_location" in kafka_entry["required"]

    eh_entry = connector_catalog_entry("eventhubs_available_now")
    assert eh_entry["family"] == "available_now_stream"
    assert "checkpoint_location" in eh_entry["required"]
