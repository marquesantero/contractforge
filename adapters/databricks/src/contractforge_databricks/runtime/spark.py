"""Databricks/Spark runtime convenience helpers with lazy imports."""

from __future__ import annotations

import json
import logging
import platform
from typing import Any

from contractforge_databricks.capabilities.runtime import is_serverless_conf
from contractforge_databricks.runtime.detection import _collect_spark_conf
from contractforge_databricks.sql import quote_identifier, quote_table_name

logger = logging.getLogger(__name__)
_SERVERLESS_CACHE: dict[int, bool] = {}


def get_active_spark() -> Any:
    """Resolve the active Databricks or PySpark session at call time."""
    try:
        from databricks.sdk.runtime import spark as dbx_spark  # type: ignore

        if dbx_spark is not None:
            return dbx_spark
    except Exception as exc:
        logger.debug("Databricks runtime spark session was not available; falling back to PySpark.", exc_info=exc)
    try:
        from pyspark.sql import SparkSession
    except Exception as exc:
        raise RuntimeError("PySpark is required to resolve an active Spark session.") from exc
    session = SparkSession.getActiveSession() or getattr(SparkSession, "_instantiatedSession", None)
    if session is None:
        raise RuntimeError("No active SparkSession was found.")
    return session


def runtime_info(spark: Any | None = None) -> dict[str, str | None]:
    session = spark or _maybe_active_spark()
    version = getattr(session, "version", None) if session is not None else None
    return {
        "runtime_type": "serverless" if detect_serverless(session) else "classic",
        "spark_version": version,
        "python_version": platform.python_version(),
    }


def detect_serverless(spark: Any | None = None) -> bool:
    session = spark or _maybe_active_spark()
    if session is None:
        return False
    cache_key = id(session)
    if cache_key in _SERVERLESS_CACHE:
        return _SERVERLESS_CACHE[cache_key]
    conf = _collect_spark_conf(session) if session is not None else {}
    detected = is_serverless_conf(conf) or conf.get("spark.databricks.clusterUsageTags.clusterSource") == "JOB_SERVERLESS"
    _SERVERLESS_CACHE[cache_key] = detected
    return detected


def safe_cache(df: Any, *, enabled: bool = True, serverless: bool | None = None) -> Any:
    if not enabled or (detect_serverless() if serverless is None else serverless):
        return df
    try:
        return df.cache()
    except Exception as exc:
        if _is_unsupported_cache_error(exc):
            return df
        raise


def safe_unpersist(df: Any, *, enabled: bool = True, serverless: bool | None = None) -> None:
    if not enabled or (detect_serverless() if serverless is None else serverless):
        return
    try:
        df.unpersist()
    except Exception as exc:
        if not _is_unsupported_cache_error(exc):
            raise


def safe_cache_table(spark: Any, table_name: str, *, enabled: bool = True, serverless: bool | None = None) -> bool:
    if not enabled or (detect_serverless(spark) if serverless is None else serverless):
        return False
    try:
        catalog = getattr(spark, "catalog", None)
        cache_table = getattr(catalog, "cacheTable", None)
        if callable(cache_table):
            cache_table(table_name)
        else:
            spark.sql(f"CACHE TABLE {quote_identifier(table_name)}")
        return True
    except Exception as exc:
        if _is_unsupported_cache_error(exc):
            return False
        raise


def safe_uncache_table(spark: Any, table_name: str, *, enabled: bool = True, serverless: bool | None = None) -> None:
    if not enabled or (detect_serverless(spark) if serverless is None else serverless):
        return
    try:
        catalog = getattr(spark, "catalog", None)
        uncache_table = getattr(catalog, "uncacheTable", None)
        if callable(uncache_table):
            uncache_table(table_name)
        else:
            spark.sql(f"UNCACHE TABLE {quote_identifier(table_name)}")
    except Exception as exc:
        if not _is_unsupported_cache_error(exc):
            raise


def table_exists(full_name: str, *, spark: Any | None = None) -> bool:
    session = spark or get_active_spark()
    try:
        if session.catalog.tableExists(full_name):
            return True
    except Exception as exc:
        logger.debug("Spark catalog tableExists failed for %s; falling back to DESCRIBE TABLE.", full_name, exc_info=exc)
    try:
        session.sql(f"DESCRIBE TABLE {quote_table_name(full_name)}")
        return True
    except Exception as exc:
        logger.debug("Spark DESCRIBE TABLE failed for %s.", full_name, exc_info=exc)
        return False


def schema_signature(df: Any) -> str:
    return json.dumps(
        [(field.name, field.dataType.simpleString(), field.nullable) for field in df.schema.fields],
        ensure_ascii=False,
    )


def fix_encoding(df: Any, *, enabled: bool, encoding: str, columns: tuple[str, ...] = ()) -> Any:
    if not enabled:
        return df
    from pyspark.sql import functions as functions  # type: ignore

    string_cols = [field.name for field in df.schema.fields if field.dataType.typeName() == "string"]
    cols_to_fix = columns or tuple(string_cols)
    for column in cols_to_fix:
        if column in string_cols:
            df = df.withColumn(column, functions.decode(functions.col(column).cast("binary"), encoding))
    return df


def sync_delta_schema(
    *,
    df: Any,
    target_table: str,
    schema_changes: dict[str, Any],
    policy: str,
    spark: Any | None = None,
) -> None:
    session = spark or get_active_spark()
    if policy not in {"permissive", "additive_only"} or not table_exists(target_table, spark=session):
        return
    fields = {field.name: field.dataType.simpleString() for field in df.schema.fields}
    added = [column for column in schema_changes.get("added_columns", ()) if column in fields]
    if added:
        cols_sql = ", ".join(f"{quote_identifier(column)} {fields[column]}" for column in added)
        session.sql(f"ALTER TABLE {quote_table_name(target_table)} ADD COLUMNS ({cols_sql})")
    for change in schema_changes.get("type_changes", ()):
        if not change.get("allowed"):
            continue
        column = str(change["column"])
        source_type = str(change["source"])
        session.sql(f"ALTER TABLE {quote_table_name(target_table)} ALTER COLUMN {quote_identifier(column)} TYPE {source_type}")
        change["applied"] = True


def _maybe_active_spark() -> Any | None:
    try:
        return get_active_spark()
    except Exception as exc:
        logger.debug("No active Spark session could be resolved.", exc_info=exc)
        return None


def _is_unsupported_cache_error(exc: Exception) -> bool:
    text = str(exc).upper()
    return "NOT_SUPPORTED" in text or "SERVERLESS" in text
