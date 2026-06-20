"""Databricks HTTP file source rendering."""

from __future__ import annotations

from typing import Any

from contractforge_core.connectors import (
    http_file_format,
    http_file_headers,
    http_file_reader_options,
    is_http_file_source as is_http_file_source,
)
from contractforge_databricks.security import redact_value


def render_http_file_python(source: dict[str, Any], *, dataframe_name: str = "df") -> str:
    if not is_http_file_source(source):
        raise ValueError("HTTP file rendering requires source.type http_file/http_csv/http_json/http_text")
    request = source.get("request", {})
    url = source.get("url") or request.get("url")
    if not url:
        raise ValueError("HTTP file source requires url or request.url")
    method = str(request.get("method") or "GET").upper()
    if method != "GET":
        raise ValueError("HTTP file source supports only GET")
    file_format = http_file_format(source)
    http_file_headers(source)
    options = http_file_reader_options(source)
    lines = [
        "from contractforge_core.connectors import download_http_file",
        "",
        f"source = {source!r}",
        "local_path = download_http_file(source)",
        f"reader = spark.read.format({file_format!r})",
    ]
    for key, value in sorted(options.items()):
        lines.append(f"reader = reader.option({key!r}, {value!r})")
    lines.extend(
        [
            f"{dataframe_name} = reader.load(local_path)",
            "",
            "# Rendered HTTP source with sensitive values redacted for review:",
            f"http_source_review = {redact_value(source)!r}",
        ]
    )
    return "\n".join(lines) + "\n"
