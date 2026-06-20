"""Snowflake staged-file source rendering."""

from __future__ import annotations

import re
from typing import Any

from contractforge_core.semantic import SemanticContract
from contractforge_snowflake.naming import quote_identifier
from contractforge_snowflake.sources.models import SnowflakeSourcePlan
from contractforge_snowflake.sql import sql_string
from contractforge_snowflake.values import dict_mapping as _mapping

_STAGE_REFERENCE_RE = re.compile(r'^@[A-Za-z0-9_.$/"\-/]+$')
_SUPPORTED_FORMATS = {"csv", "json", "parquet"}


def render_stage_files_source(contract: SemanticContract) -> SnowflakeSourcePlan:
    source = _source(contract)
    stage = _stage_reference(source)
    options = _mapping(source.get("options"))
    source_format = _source_format(source, options)
    columns = _stage_columns(options, source_format=source_format)
    clauses = _stage_clauses(source, options, source_format=source_format)
    stage_table = stage + (f" ({', '.join(clauses)})" if clauses else "")
    metadata = {
        "type": str(source.get("type") or contract.source.kind or "staged_files").lower(),
        "stage": stage,
        "file_format": source.get("file_format") or options.get("file_format"),
        "pattern_present": bool(source.get("pattern") or options.get("pattern")),
    }
    if source_format:
        metadata["format"] = source_format
    return SnowflakeSourcePlan(
        sql=f"SELECT {columns}\nFROM {stage_table} AS _CF_STAGE",
        metadata=metadata,
    )


def _stage_reference(source: dict[str, Any]) -> str:
    value = source.get("stage") or source.get("path") or source.get("location")
    if not value:
        raise ValueError("Snowflake staged file source requires source.stage or source.path")
    text = str(value).strip()
    if not text.startswith("@"):
        text = "@" + text
    if not _STAGE_REFERENCE_RE.match(text) or ".." in text.split("/"):
        raise ValueError(f"Unsafe Snowflake stage reference: {value}")
    return text


def _stage_columns(options: dict[str, Any], *, source_format: str | None) -> str:
    columns = options.get("columns")
    if isinstance(columns, dict) and columns:
        return ", ".join(f"{_stage_column_expression(expr)} AS {quote_identifier(name)}" for name, expr in columns.items())
    if isinstance(columns, (list, tuple)) and columns:
        return ", ".join(f"${index} AS {quote_identifier(str(name))}" for index, name in enumerate(columns, start=1))
    if source_format == "json":
        return '$1 AS "payload"'
    if source_format == "parquet":
        return '$1 AS "payload"'
    return '$1 AS "value"'


def _stage_column_expression(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("Snowflake staged file source column expressions cannot be empty")
    if ";" in text or "--" in text or "/*" in text:
        raise ValueError("Unsafe Snowflake staged file source column expression")
    return text


def _stage_clauses(source: dict[str, Any], options: dict[str, Any], *, source_format: str | None) -> tuple[str, ...]:
    clauses: list[str] = []
    file_format = source.get("file_format") or options.get("file_format")
    pattern = source.get("pattern") or options.get("pattern")
    if file_format:
        clauses.append(f"FILE_FORMAT => {_file_format_clause(file_format)}")
    if pattern:
        clauses.append(f"PATTERN => {sql_string(str(pattern))}")
    return tuple(clauses)


def _source_format(source: dict[str, Any], options: dict[str, Any]) -> str | None:
    value = source.get("format") or options.get("format")
    return _normalize_source_format(value)


def _normalize_source_format(value: object) -> str | None:
    if value is None:
        return None
    source_format = str(value).strip().lower()
    if source_format not in _SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported Snowflake staged file format: {value}")
    return source_format


def _file_format_clause(value: object) -> str:
    if isinstance(value, dict):
        raise ValueError("Snowflake staged SELECT requires a named file_format or a stage default file format")
    return sql_string(str(value))


def _source(contract: SemanticContract) -> dict[str, Any]:
    return contract.source.raw or {}
