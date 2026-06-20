"""Render Fabric notebook stream source readers."""

from __future__ import annotations

from typing import Any

from contractforge_core.connectors import is_available_now_stream_source, is_kafka_stream_source, kafka_bounded_options, stream_source_format
from contractforge_core.security import redact_value
from contractforge_fabric.security import render_secret_aware_literal


def is_fabric_bounded_stream_source(source: dict[str, Any]) -> bool:
    return str(source.get("type") or "").strip().lower() == "kafka_bounded"


def is_fabric_available_now_stream_source(source: dict[str, Any]) -> bool:
    return str(source.get("type") or "").strip().lower() == "kafka_available_now"


def render_bounded_stream_source(source: dict[str, Any], *, dataframe_name: str = "df") -> str:
    if not is_kafka_stream_source(source):
        raise ValueError("Fabric notebook bounded stream rendering currently supports only kafka_bounded")
    source_format = stream_source_format(source)
    options = kafka_bounded_options(source)
    lines = [
        "# Bounded Kafka replay through Spark batch read.",
        f"{dataframe_name} = (",
        "    spark.read",
        f"    .format({source_format!r})",
    ]
    for key, value in sorted(options.items()):
        lines.append(f"    .option({key!r}, {render_secret_aware_literal(str(value))})")
    lines.extend(["    .load()", ")"])
    lines.append("# Source options (sensitive values redacted for review):")
    lines.append(f"# {redact_value(options)!r}")
    return "\n".join(lines)


def render_available_now_stream_source(source: dict[str, Any], *, dataframe_name: str = "df") -> str:
    if not is_available_now_stream_source(source) or not is_kafka_stream_source(source):
        raise ValueError("Fabric notebook available-now stream rendering currently supports only kafka_available_now")
    checkpoint = _checkpoint_location(source)
    if not checkpoint:
        raise ValueError("Fabric notebook available-now stream rendering requires source.checkpoint_location")
    source_format = stream_source_format(source)
    options = kafka_bounded_options(source)
    materialized_path = _materialized_delta_path(source, checkpoint)
    lines = [
        "# Checkpointed Kafka available-now catch-up through Spark Structured Streaming.",
        f"_cf_available_now_checkpoint = {render_secret_aware_literal(checkpoint)}",
        f"_cf_available_now_materialized_path = {render_secret_aware_literal(materialized_path)}",
        "try:",
        "    notebookutils.fs.rm(_cf_available_now_materialized_path, True)",
        "except Exception:",
        "    pass",
        "_cf_source_stream = (",
        "    spark.readStream",
        f"    .format({source_format!r})",
    ]
    for key, value in sorted(options.items()):
        lines.append(f"    .option({key!r}, {render_secret_aware_literal(str(value))})")
    lines.extend(
        [
            "    .load()",
            ")",
            "_cf_available_now_query = (",
            "    _cf_source_stream.writeStream",
            "    .format('delta')",
            "    .outputMode('append')",
            "    .option('checkpointLocation', _cf_available_now_checkpoint)",
            "    .option('path', _cf_available_now_materialized_path)",
            "    .trigger(availableNow=True)",
            "    .start()",
            ")",
            "_cf_available_now_query.awaitTermination()",
            "try:",
            f"    {dataframe_name} = spark.read.format('delta').load(_cf_available_now_materialized_path)",
            "except Exception:",
            f"    {dataframe_name} = spark.createDataFrame([], _cf_source_stream.schema)",
            "globals()['_cf_available_now_checkpoint'] = _cf_available_now_checkpoint",
            "globals()['_cf_available_now_materialized_path'] = _cf_available_now_materialized_path",
            "# Source options (sensitive values redacted for review):",
            f"# {redact_value(options)!r}",
        ]
    )
    return "\n".join(lines)


def _checkpoint_location(source: dict[str, Any]) -> str:
    options = source.get("options") if isinstance(source.get("options"), dict) else {}
    return str(source.get("checkpoint_location") or options.get("checkpointLocation") or "").strip()


def _materialized_delta_path(source: dict[str, Any], checkpoint: str) -> str:
    extensions = source.get("extensions") if isinstance(source.get("extensions"), dict) else {}
    fabric = extensions.get("fabric") if isinstance(extensions.get("fabric"), dict) else {}
    configured = fabric.get("available_now_materialized_path") or fabric.get("available_now_staging_path")
    if configured:
        return str(configured)
    return checkpoint.rstrip("/") + "/_contractforge_available_now_delta"


__all__ = [
    "is_fabric_available_now_stream_source",
    "is_fabric_bounded_stream_source",
    "render_available_now_stream_source",
    "render_bounded_stream_source",
]
