"""Databricks bounded stream source rendering."""

from __future__ import annotations

from typing import Any

from contractforge_core.connectors import (
    eventhubs_bounded_options,
    is_bounded_stream_source as is_bounded_stream_source,
    kafka_bounded_options,
)
from contractforge_databricks.security import redact_value


def render_bounded_stream_python(source: dict[str, Any], *, dataframe_name: str = "df") -> str:
    source_type = source.get("type")
    if source_type == "kafka_bounded":
        return render_kafka_bounded_python(source, dataframe_name=dataframe_name)
    if source_type == "eventhubs_bounded":
        return render_eventhubs_bounded_python(source, dataframe_name=dataframe_name)
    raise ValueError("bounded stream rendering requires kafka_bounded or eventhubs_bounded")


def render_kafka_bounded_python(source: dict[str, Any], *, dataframe_name: str = "df") -> str:
    return _render_reader("kafka", kafka_bounded_options(source), dataframe_name, "kafka_bounded_options_review")


def render_eventhubs_bounded_python(source: dict[str, Any], *, dataframe_name: str = "df") -> str:
    return _render_reader("eventhubs", eventhubs_bounded_options(source), dataframe_name, "eventhubs_bounded_options_review")




def _render_reader(source_format: str, options: dict[str, str], dataframe_name: str, review_name: str) -> str:
    lines = [
        "# Bounded replay/catch-up read. This is not a continuous streaming artifact.",
        f"{dataframe_name} = (",
        "    spark.read",
        f"    .format({source_format!r})",
    ]
    for key, value in sorted(options.items()):
        lines.append(f"    .option({key!r}, {value!r})")
    lines.extend(["    .load()", ")", "", f"{review_name} = {redact_value(options)!r}"])
    return "\n".join(lines) + "\n"
