"""Spark-backed runtime defaults for Databricks bundle execution."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from contractforge_core.runtime import QueryOne
from contractforge_databricks.runtime.models import DatabricksIngestOptions


def with_spark_runtime_defaults(spark: Any, opts: DatabricksIngestOptions, target: str) -> DatabricksIngestOptions:
    if opts.target_schema is not None or not opts.ensure_table:
        return opts
    target_schema = spark_target_schema(spark, target)
    return replace(opts, target_schema=target_schema) if target_schema is not None else opts


def spark_target_schema(spark: Any, target: str) -> dict[str, str] | None:
    try:
        schema = spark.table(target).schema
    except Exception:
        return None
    return {str(field.name): str(field.dataType.simpleString()).lower() for field in schema.fields}


def spark_query_one(spark: Any) -> QueryOne | None:
    if not callable(getattr(spark, "sql", None)):
        return None

    def query_one(statement: str) -> dict[str, Any] | None:
        rows = spark.sql(statement).limit(1).collect()
        return rows[0].asDict() if rows else None

    return query_one
