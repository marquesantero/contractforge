"""Facade for stream connector helpers."""

from contractforge_core.connectors.streams.eventhubs import eventhubs_bounded_options, is_eventhubs_stream_source
from contractforge_core.connectors.streams.kafka import is_kafka_stream_source, kafka_bounded_options
from contractforge_core.connectors.streams.source import (
    AVAILABLE_NOW_STREAM_TYPES,
    BOUNDED_STREAM_TYPES,
    STREAM_SOURCE_TYPES,
    is_available_now_stream_source,
    is_bounded_stream_source,
    stream_source_format,
)

__all__ = [
    "AVAILABLE_NOW_STREAM_TYPES",
    "BOUNDED_STREAM_TYPES",
    "STREAM_SOURCE_TYPES",
    "eventhubs_bounded_options",
    "is_available_now_stream_source",
    "is_bounded_stream_source",
    "is_eventhubs_stream_source",
    "is_kafka_stream_source",
    "kafka_bounded_options",
    "stream_source_format",
]
