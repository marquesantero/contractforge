"""Databricks SQL review rendering for core shape intent."""

from __future__ import annotations

from typing import Any

from contractforge_core.semantic import SemanticContract
from contractforge_databricks.sql import quote_identifier, quote_table_name


def render_shape_sql(
    contract: SemanticContract,
    *,
    source_view: str = "${source_view}",
    output_view: str = "${shaped_view}",
) -> str:
    if not contract.shape:
        return "-- No shape declared.\n"
    shape = contract.shape.raw
    lines = [
        "-- Shape SQL review artifact.",
        "-- Databricks runtime may execute equivalent PySpark preparation for complex nested schemas.",
        f"CREATE OR REPLACE TEMP VIEW {quote_table_name(output_view)} AS",
        "SELECT",
        ",\n".join(f"  {item}" for item in _select_items(shape)),
        f"FROM {_from_clause(shape, source_view)}",
    ]
    return "\n".join(lines) + ";\n" + _review_notes(shape)


def _select_items(shape: dict[str, Any]) -> list[str]:
    items: list[str] = ["*"]
    for config in shape.get("parse_json", ()):
        column = str(config["column"])
        schema = config.get("schema") or f"${{schema:{config.get('schema_ref')}}}"
        alias = str(config.get("alias") or column)
        cast_input = str(config.get("cast_input") or "").strip().upper()
        source_expr = _path_expr(column)
        if cast_input == "STRING":
            source_expr = f"CAST({source_expr} AS STRING)"
        items.append(f"from_json({source_expr}, '{schema}') AS {quote_identifier(alias)}")
    for config in shape.get("zip_arrays", ()):
        columns = ", ".join(_path_expr(path) for path in config.get("columns", {}))
        items.append(f"arrays_zip({columns}) AS {quote_identifier(str(config['alias']))}")
    for config in shape.get("arrays", ()):
        rendered = _array_item(config)
        if rendered:
            items.append(rendered)
    if shape.get("columns"):
        return _projection_items(shape["columns"])
    return items


def _projection_items(columns: dict[str, Any]) -> list[str]:
    items = []
    for path, config in columns.items():
        if isinstance(config, str):
            alias = config
            expr = _path_expr(path)
        else:
            alias = str(config.get("alias") or _default_alias(path))
            expr = str(config["expression"]) if config.get("expression") else _path_expr(path)
            if config.get("cast"):
                expr = f"CAST({expr} AS {config['cast']})"
        items.append(f"{expr} AS {quote_identifier(alias)}")
    return items


def _array_item(config: dict[str, Any]) -> str | None:
    path = str(config["path"])
    alias = str(config.get("alias") or _default_alias(path))
    mode = str(config.get("mode", "keep"))
    expr = _path_expr(path)
    if mode == "keep":
        return None
    if mode == "to_json":
        return f"to_json({expr}) AS {quote_identifier(alias)}"
    if mode == "size":
        return f"size({expr}) AS {quote_identifier(alias)}"
    if mode == "first":
        return f"element_at({expr}, 1) AS {quote_identifier(alias)}"
    if mode == "explode":
        return f"explode({expr}) AS {quote_identifier(alias)}"
    if mode == "explode_outer":
        return f"explode_outer({expr}) AS {quote_identifier(alias)}"
    return None


def _from_clause(shape: dict[str, Any], source_view: str) -> str:
    if _flatten_enabled(shape):
        return f"{quote_table_name(source_view)} -- flatten requires schema-aware expansion"
    return quote_table_name(source_view)


def _review_notes(shape: dict[str, Any]) -> str:
    notes = []
    if _flatten_enabled(shape):
        flatten = shape.get("flatten")
        separator = flatten.get("separator", "_") if isinstance(flatten, dict) else "_"
        notes.append(f"-- flatten: enabled with separator {separator!r}; runtime must expand struct leaves.")
    changing = [
        config["path"]
        for config in shape.get("arrays", ())
        if config.get("mode") in {"explode", "explode_outer"}
    ]
    if changing and not shape.get("allow_cardinality_change_on_bronze", False):
        notes.append("-- cardinality review: explode/explode_outer changes row counts and may require layer policy review.")
    return ("\n".join(notes) + "\n") if notes else ""


def _flatten_enabled(shape: dict[str, Any]) -> bool:
    flatten = shape.get("flatten")
    if isinstance(flatten, bool):
        return flatten
    return isinstance(flatten, dict) and bool(flatten.get("enabled"))


def _path_expr(path: str) -> str:
    return ".".join(quote_identifier(part) for part in str(path).split("."))


def _default_alias(path: str) -> str:
    return str(path).replace(".", "_")
