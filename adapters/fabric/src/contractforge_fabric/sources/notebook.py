"""Render Fabric notebook source readers for bounded HTTP/REST sources."""

from __future__ import annotations

from typing import Any

from contractforge_core.connectors import is_http_file_source, is_rest_api_connector
from contractforge_fabric.security import render_secret_aware_literal


def source_requires_http_helpers(source: dict[str, Any]) -> bool:
    return is_http_file_source(source) or is_rest_api_connector(source)


def render_http_source_helpers() -> str:
    return "\n".join(
        [
            "def _cf_rest_dataframe(spark, source):",
            "    import json as _json",
            "    from contractforge_core.connectors import read_rest_api_records",
            "    records = read_rest_api_records(source)",
            "    if not records:",
            "        return spark.createDataFrame([], 'cf_empty_response string')",
            "    rdd = spark.sparkContext.parallelize([_json.dumps(record) for record in records])",
            "    return spark.read.json(rdd)",
            "",
            "def _cf_http_file_dataframe(spark, source):",
            "    from contractforge_core.connectors import http_file_format, http_file_reader_options, read_http_file_payload",
            "    payload = read_http_file_payload(source)",
            "    text = payload.decode('utf-8')",
            "    fmt = http_file_format(source)",
            "    options = http_file_reader_options(source)",
            "    multiline = str(options.get('multiLine', options.get('multiline', 'false'))).lower() == 'true'",
            "    records = [text] if multiline else (text.splitlines() or [''])",
            "    rdd = spark.sparkContext.parallelize(records)",
            "    reader = spark.read",
            "    for key, value in sorted(options.items()):",
            "        reader = reader.option(key, value)",
            "    if fmt == 'csv':",
            "        return reader.csv(rdd)",
            "    if fmt == 'text':",
            "        return rdd.map(lambda value: (value,)).toDF(['value'])",
            "    return reader.json(rdd)",
            "",
        ]
    )


def render_http_source_statement(source: dict[str, Any], *, dataframe_name: str = "df") -> str:
    if is_rest_api_connector(source):
        return "\n".join(
            [
                f"_cf_rest_source = {_render_value(source)}",
                f"{dataframe_name} = _cf_rest_dataframe(spark, _cf_rest_source)",
            ]
        )
    if is_http_file_source(source):
        return "\n".join(
            [
                f"_cf_http_source = {_render_value(source)}",
                f"{dataframe_name} = _cf_http_file_dataframe(spark, _cf_http_source)",
            ]
        )
    raise ValueError("Fabric HTTP source rendering requires rest_api or http_file/http_json/http_csv/http_text")


def _render_value(value: Any) -> str:
    if isinstance(value, dict):
        body = ", ".join(f"{key!r}: {_render_value(item)}" for key, item in value.items())
        return "{" + body + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_render_value(item) for item in value) + "]"
    if isinstance(value, str):
        return render_secret_aware_literal(value)
    return repr(value)


__all__ = ["render_http_source_helpers", "render_http_source_statement", "source_requires_http_helpers"]
