"""Databricks Spark file and catalog source rendering."""

from __future__ import annotations

from typing import Any

from contractforge_core.connectors import (
    TableRefResolver,
    catalog_source_query,
    catalog_source_table_or_path,
    file_reader_options,
    file_source_format,
    is_catalog_source as is_catalog_source,
    is_file_source as is_file_source,
)


def render_file_source_python(source: dict[str, Any], *, dataframe_name: str = "df") -> str:
    file_format = file_source_format(source)
    path = source.get("path")
    if not path:
        raise ValueError("file source requires path")
    options = file_reader_options(source)
    lines = [
        f"{dataframe_name} = (",
        "    spark.read",
        f"    .format({file_format!r})",
    ]
    for key, value in sorted(options.items()):
        lines.append(f"    .option({key!r}, {value!r})")
    lines.extend([f"    .load({path!r})", ")"])
    return "\n".join(lines) + "\n"


def render_catalog_source_python(
    source: dict[str, Any],
    *,
    dataframe_name: str = "df",
    table_ref_resolver: TableRefResolver | None = None,
) -> str:
    source_type = source.get("type")
    if source_type == "sql":
        return f"{dataframe_name} = spark.sql({catalog_source_query(source, table_ref_resolver=table_ref_resolver)!r})\n"
    table = catalog_source_table_or_path(source, table_ref_resolver=table_ref_resolver)
    if source.get("path") and not source.get("table"):
        file_format = "delta" if source_type == "delta_table" else source_type.replace("_table", "")
        return f"{dataframe_name} = spark.read.format({file_format!r}).load({str(table)!r})\n"
    return f"{dataframe_name} = spark.table({str(table)!r})\n"
