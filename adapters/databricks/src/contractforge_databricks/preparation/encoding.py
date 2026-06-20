"""Databricks preparation helpers for adapter-owned encoding fixes."""

from __future__ import annotations

import importlib
from typing import Any

from contractforge_databricks.contract_extensions import databricks_extensions


def apply_encoding_fix(df: Any, contract: Any) -> Any:
    extensions = databricks_extensions(contract)
    if not extensions.get("fix_encoding"):
        return df
    functions = importlib.import_module("pyspark.sql").functions
    encoding = str(extensions.get("encoding") or "utf-8")
    string_columns = _string_columns(df)
    for column in _string_tuple(extensions.get("encoding_columns")) or string_columns:
        if column in string_columns:
            df = df.withColumn(column, functions.decode(functions.col(column).cast("binary"), encoding))
    return df


def _string_columns(df: Any) -> tuple[str, ...]:
    return tuple(
        field.name
        for field in getattr(getattr(df, "schema", None), "fields", ()) or ()
        if field.dataType.typeName() == "string"
    )


def _string_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return tuple(part.strip() for part in value.split(",") if part.strip())
    return tuple(str(part) for part in value or ())
