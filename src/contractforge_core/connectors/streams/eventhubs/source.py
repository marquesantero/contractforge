"""Azure Event Hubs bounded and available-now source helpers."""

from __future__ import annotations

from typing import Any

EVENTHUBS_BOUNDED_TYPES = frozenset({"eventhubs_bounded"})
EVENTHUBS_AVAILABLE_NOW_TYPES = frozenset({"eventhubs_available_now"})
EVENTHUBS_STREAM_TYPES = EVENTHUBS_BOUNDED_TYPES | EVENTHUBS_AVAILABLE_NOW_TYPES


def is_eventhubs_stream_source(source: dict[str, Any]) -> bool:
    return source.get("type") in EVENTHUBS_STREAM_TYPES


def eventhubs_bounded_options(source: dict[str, Any]) -> dict[str, str]:
    options = {str(key): str(value) for key, value in source.get("options", {}).items()}
    connection_string = source.get("connection_string") or options.get("eventhubs.connectionString")
    event_hub_name = source.get("event_hub_name")
    if connection_string:
        options["eventhubs.connectionString"] = str(connection_string)
    if event_hub_name:
        options["eventhubs.name"] = str(event_hub_name)
    if "eventhubs.connectionString" not in options and "eventhubs.name" not in options:
        raise ValueError("eventhubs_bounded requires connection_string, event_hub_name or equivalent options")
    _copy_option(source, options, "starting_position", "eventhubs.startingPosition")
    _copy_option(source, options, "ending_position", "eventhubs.endingPosition")
    _copy_limit_option(source, options, "max_events_per_trigger", "maxEventsPerTrigger")
    return options


def _copy_option(source: dict[str, Any], options: dict[str, str], source_key: str, option_key: str) -> None:
    if source_key in source:
        options[option_key] = str(source[source_key])


def _copy_limit_option(source: dict[str, Any], options: dict[str, str], source_key: str, option_key: str) -> None:
    limits = source.get("limits") if isinstance(source.get("limits"), dict) else {}
    values = [value for value in (source.get(source_key), limits.get(source_key)) if value not in (None, "")]
    unique = {str(value) for value in values}
    if len(unique) > 1:
        raise ValueError(f"source.{source_key} conflicts with source.limits.{source_key}")
    if values:
        options[option_key] = str(values[0])
