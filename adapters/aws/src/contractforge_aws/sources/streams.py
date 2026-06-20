"""Render AWS Glue bounded stream and Delta Sharing sources.

Bounded Kafka / Event Hubs replays and Delta Sharing reads map to a batch
``spark.read.format(...)`` reader, so they fit the same batch write rendering
as files and JDBC. The corresponding Spark connector jar (kafka-sql,
azure-eventhubs-spark, delta-sharing-spark) must be provided to the Glue job.
"""

from __future__ import annotations

from typing import Any

from contractforge_core.connectors import (
    delta_share_options,
    eventhubs_bounded_options,
    is_kafka_stream_source,
    kafka_bounded_options,
    stream_source_format,
)
from contractforge_aws.security import redact_value, render_secret_aware_literal

__all__ = [
    "render_available_now_stream_source",
    "render_bounded_stream_source",
    "render_delta_share_source",
    "stream_options",
]


def stream_options(source: dict[str, Any]) -> dict[str, str]:
    return kafka_bounded_options(source) if is_kafka_stream_source(source) else eventhubs_bounded_options(source)


def render_bounded_stream_source(source: dict[str, Any], *, dataframe_name: str = "df") -> str:
    source_format = stream_source_format(source)
    note = f"# Bounded {source_format} replay; provide the matching Spark connector jar to the Glue job."
    return _render_reader(dataframe_name, source_format, stream_options(source), reader="spark.read", note=note)


def render_available_now_stream_source(source: dict[str, Any], *, dataframe_name: str = "df") -> str:
    source_format = stream_source_format(source)
    note = f"# {source_format} structured stream (trigger availableNow); provide the matching Spark connector jar."
    return _render_reader(dataframe_name, source_format, stream_options(source), reader="spark.readStream", note=note)


def render_delta_share_source(source: dict[str, Any], *, dataframe_name: str = "df") -> str:
    options = delta_share_options(source)
    note = "# Delta Sharing read; provide the delta-sharing-spark connector jar to the Glue job."
    return _render_reader(dataframe_name, "deltaSharing", options, reader="spark.read", note=note)


def _render_reader(
    dataframe_name: str, source_format: str, options: dict[str, str], *, reader: str, note: str
) -> str:
    lines = [note, f"{dataframe_name} = (", f"    {reader}", f"    .format({source_format!r})"]
    for key, value in sorted(options.items()):
        lines.append(f"    .option({key!r}, {render_secret_aware_literal(str(value))})")
    lines.extend(["    .load()", ")"])
    lines.append("# Source options (sensitive values redacted for review):")
    lines.append(f"# {redact_value(options)!r}")
    return "\n".join(lines) + "\n"
