"""Kafka bounded and available-now source helpers."""

from __future__ import annotations

from typing import Any

KAFKA_BOUNDED_TYPES = frozenset({"kafka_bounded"})
KAFKA_AVAILABLE_NOW_TYPES = frozenset({"kafka_available_now"})
KAFKA_STREAM_TYPES = KAFKA_BOUNDED_TYPES | KAFKA_AVAILABLE_NOW_TYPES


def is_kafka_stream_source(source: dict[str, Any]) -> bool:
    return source.get("type") in KAFKA_STREAM_TYPES


def kafka_bounded_options(source: dict[str, Any]) -> dict[str, str]:
    options = {str(key): str(value) for key, value in source.get("options", {}).items()}
    bootstrap_servers = source.get("bootstrap_servers") or options.get("kafka.bootstrap.servers")
    if not bootstrap_servers:
        raise ValueError("kafka_bounded requires bootstrap_servers or options.kafka.bootstrap.servers")
    options["kafka.bootstrap.servers"] = str(bootstrap_servers)
    topic = source.get("topic")
    topics = source.get("topics")
    assign = source.get("assign")
    if topic:
        options["subscribe"] = str(topic)
    elif topics:
        options["subscribe"] = ",".join(str(item) for item in topics)
    elif assign:
        options["assign"] = str(assign)
    else:
        raise ValueError("kafka_bounded requires topic, topics or assign")
    _copy_option(source, options, "starting_offsets", "startingOffsets")
    _copy_option(source, options, "ending_offsets", "endingOffsets")
    _copy_option(source, options, "starting_timestamp", "startingTimestamp")
    _copy_option(source, options, "ending_timestamp", "endingTimestamp")
    _copy_limit_option(source, options, "max_offsets_per_trigger", "maxOffsetsPerTrigger")
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
