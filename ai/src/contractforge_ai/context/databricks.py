"""Databricks control-table evidence collectors."""

from __future__ import annotations

from typing import Any, Protocol

from contractforge_ai.context.redaction import redact_secrets


class SparkLike(Protocol):
    """Minimal SparkSession protocol used by the Databricks evidence collector."""

    def sql(self, query: str) -> Any:
        """Run a SQL query and return a Spark-like DataFrame."""


CONTROL_TABLES = {
    "run": "ctrl_ingestion_runs",
    "errors": "ctrl_ingestion_errors",
    "quality": "ctrl_ingestion_quality",
    "streams": "ctrl_ingestion_streams",
}


def collect_databricks_run_evidence(
    *,
    run_id: str,
    catalog: str,
    ctrl_schema: str,
    spark: SparkLike | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Collect ContractForge control-table evidence from Databricks.

    The collector is intentionally small and SQL-based so it can run in notebooks,
    jobs and tests with a mocked SparkSession. Missing optional tables are reported
    in `collection_errors` instead of hiding diagnostics.
    """

    if not run_id.strip():
        raise ValueError("run_id is required.")
    if limit <= 0:
        raise ValueError("limit must be positive.")

    spark_session = spark or _active_spark()
    escaped_run_id = _sql_string(run_id)
    tables = {name: _table_name(catalog, ctrl_schema, table) for name, table in CONTROL_TABLES.items()}

    collection_errors: list[dict[str, str]] = []
    run_rows = _query(
        spark_session,
        f"SELECT * FROM {tables['run']} WHERE run_id = {escaped_run_id} LIMIT 1",
        kind="run",
        collection_errors=collection_errors,
    )
    run = run_rows[0] if run_rows else {"run_id": run_id, "status": "UNKNOWN"}

    errors = _query(
        spark_session,
        f"SELECT * FROM {tables['errors']} WHERE run_id = {escaped_run_id} LIMIT {limit}",
        kind="errors",
        collection_errors=collection_errors,
    )
    quality = _query(
        spark_session,
        f"SELECT * FROM {tables['quality']} WHERE run_id = {escaped_run_id} LIMIT {limit}",
        kind="quality",
        collection_errors=collection_errors,
    )
    streams = _query(
        spark_session,
        f"SELECT * FROM {tables['streams']} WHERE run_id = {escaped_run_id} OR stream_run_id = {escaped_run_id} LIMIT {limit}",
        kind="streams",
        collection_errors=collection_errors,
    )

    payload = {
        "run": run,
        "errors": errors,
        "quality": quality,
        "streams": streams,
        "collection": {
            "source": "databricks_control_tables",
            "catalog": catalog,
            "ctrl_schema": ctrl_schema,
            "tables": tables,
            "limit": limit,
            "collection_errors": collection_errors,
        },
    }
    return redact_secrets(payload)


def _active_spark() -> SparkLike:
    try:
        from databricks.sdk.runtime import spark
    except Exception as exc:  # pragma: no cover - depends on external runtime
        raise RuntimeError(
            "No SparkSession was provided and Databricks runtime spark could not be imported. "
            "Pass spark explicitly or run inside a Databricks notebook/job."
        ) from exc
    return spark


def _query(
    spark: SparkLike,
    query: str,
    *,
    kind: str,
    collection_errors: list[dict[str, str]],
) -> list[dict[str, Any]]:
    try:
        rows = spark.sql(query).collect()
    except Exception as exc:
        collection_errors.append(
            {
                "kind": kind,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            }
        )
        return []
    return [_row_to_dict(row) for row in rows]


def _row_to_dict(row: Any) -> dict[str, Any]:
    if hasattr(row, "asDict"):
        return {key: _jsonable(value) for key, value in row.asDict(recursive=True).items()}
    if isinstance(row, dict):
        return {str(key): _jsonable(value) for key, value in row.items()}
    if hasattr(row, "_asdict"):
        return {str(key): _jsonable(value) for key, value in row._asdict().items()}
    return {"value": _jsonable(row)}


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _table_name(catalog: str, schema: str, table: str) -> str:
    return ".".join(_identifier(part) for part in (catalog, schema, table))


def _identifier(value: str) -> str:
    if not value or value.strip() != value:
        raise ValueError(f"Invalid SQL identifier part: {value!r}.")
    return f"`{value.replace('`', '``')}`"


def _sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"
