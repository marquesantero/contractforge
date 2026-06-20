"""Facade for the Azure Event Hubs stream connector."""

from contractforge_core.connectors.streams.eventhubs.source import (
    EVENTHUBS_AVAILABLE_NOW_TYPES,
    EVENTHUBS_BOUNDED_TYPES,
    EVENTHUBS_STREAM_TYPES,
    eventhubs_bounded_options,
    is_eventhubs_stream_source,
)

__all__ = [
    "EVENTHUBS_AVAILABLE_NOW_TYPES",
    "EVENTHUBS_BOUNDED_TYPES",
    "EVENTHUBS_STREAM_TYPES",
    "eventhubs_bounded_options",
    "is_eventhubs_stream_source",
]
