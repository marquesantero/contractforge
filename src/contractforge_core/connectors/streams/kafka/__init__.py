"""Facade for the Kafka stream connector."""

from contractforge_core.connectors.streams.kafka.source import (
    KAFKA_AVAILABLE_NOW_TYPES,
    KAFKA_BOUNDED_TYPES,
    KAFKA_STREAM_TYPES,
    is_kafka_stream_source,
    kafka_bounded_options,
)

__all__ = [
    "KAFKA_AVAILABLE_NOW_TYPES",
    "KAFKA_BOUNDED_TYPES",
    "KAFKA_STREAM_TYPES",
    "is_kafka_stream_source",
    "kafka_bounded_options",
]
