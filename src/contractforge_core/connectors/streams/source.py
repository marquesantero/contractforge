"""Stream connector family classification helpers."""

from __future__ import annotations

from typing import Any

from contractforge_core.connectors.streams.eventhubs import (
    EVENTHUBS_AVAILABLE_NOW_TYPES,
    EVENTHUBS_BOUNDED_TYPES,
    EVENTHUBS_STREAM_TYPES,
    is_eventhubs_stream_source,
)
from contractforge_core.connectors.streams.kafka import (
    KAFKA_AVAILABLE_NOW_TYPES,
    KAFKA_BOUNDED_TYPES,
    KAFKA_STREAM_TYPES,
    is_kafka_stream_source,
)

BOUNDED_STREAM_TYPES = KAFKA_BOUNDED_TYPES | EVENTHUBS_BOUNDED_TYPES
AVAILABLE_NOW_STREAM_TYPES = KAFKA_AVAILABLE_NOW_TYPES | EVENTHUBS_AVAILABLE_NOW_TYPES
STREAM_SOURCE_TYPES = KAFKA_STREAM_TYPES | EVENTHUBS_STREAM_TYPES


def is_bounded_stream_source(source: dict[str, Any]) -> bool:
    return source.get("type") in BOUNDED_STREAM_TYPES


def is_available_now_stream_source(source: dict[str, Any]) -> bool:
    return source.get("type") in AVAILABLE_NOW_STREAM_TYPES


def stream_source_format(source: dict[str, Any]) -> str:
    """Return the neutral stream-format token (``kafka`` or ``eventhubs``).

    Adapters map this token to their native streaming reader format.
    """

    if is_kafka_stream_source(source):
        return "kafka"
    if is_eventhubs_stream_source(source):
        return "eventhubs"
    raise ValueError(f"source.type={source.get('type')!r} is not a kafka/eventhubs stream source")
