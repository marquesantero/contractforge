"""Platform-neutral JDBC source helpers."""

from __future__ import annotations

import re
from typing import Any

from contractforge_core.connectors.databases.jdbc.rds_iam import rds_iam_review_options
from contractforge_core.watermark import extract_watermark_field_value

JDBC_CONNECTORS = frozenset(
    {
        "jdbc",
        "postgres",
        "mysql",
        "mariadb",
        "sqlserver",
        "oracle",
        "redshift",
        "db2",
        "snowflake_jdbc",
        "bigquery_jdbc",
    }
)
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def validate_jdbc_source(source: dict[str, Any]) -> None:
    connector = source.get("connector") or source.get("type")
    if connector not in JDBC_CONNECTORS and source.get("type") != "jdbc":
        raise ValueError("JDBC source requires a JDBC connector")
    if source.get("table") and source.get("query"):
        raise ValueError("JDBC source accepts table/dbtable or query, not both")


def jdbc_common_options(source: dict[str, Any]) -> dict[str, str]:
    validate_jdbc_source(source)
    options = {str(key): str(value) for key, value in source.get("options", {}).items()}
    url = source.get("url") or options.get("url")
    if not url:
        raise ValueError("JDBC source requires url or options.url")
    options["url"] = str(url)
    table = source.get("table") or options.get("dbtable")
    query = source.get("query") or options.get("query")
    if table and query:
        raise ValueError("JDBC source accepts table/dbtable or query, not both")
    if table:
        options["dbtable"] = str(table)
    elif query:
        options["query"] = str(query)
    else:
        raise ValueError("JDBC source requires table/dbtable or query")
    _apply_auth(options, source.get("auth", {}))
    _apply_incremental(options, source)
    _apply_read(options, source.get("read", {}))
    return options


def _apply_auth(options: dict[str, str], auth: dict[str, Any]) -> None:
    auth_type = str(auth.get("type") or ("basic" if auth else "none")).lower()
    if auth_type in {"", "none"}:
        return
    if auth_type == "basic":
        user = auth.get("username")
        password = auth.get("password")
        if user:
            options["user"] = str(user)
        if password:
            options["password"] = str(password)
        if not user and not password:
            raise ValueError("JDBC basic auth requires auth.username or auth.password")
        return
    if auth_type == "rds_iam":
        options.update(rds_iam_review_options(options["url"], auth=auth, username=options.get("user")))
        return
    raise ValueError("JDBC auth.type must be one of: none, basic, rds_iam")


def _apply_read(options: dict[str, str], read: dict[str, Any]) -> None:
    partition = {
        "partition_column": "partitionColumn",
        "lower_bound": "lowerBound",
        "upper_bound": "upperBound",
        "num_partitions": "numPartitions",
    }
    provided = {key for key in partition if read.get(key) not in (None, "")}
    if provided and provided != set(partition):
        raise ValueError(
            "JDBC partitioning requires source.read.partition_column, source.read.lower_bound, "
            "source.read.upper_bound and source.read.num_partitions together"
        )
    for src_key, option_key in partition.items():
        if src_key in provided:
            options[option_key] = str(read[src_key])
    if read.get("fetchsize") not in (None, ""):
        options["fetchsize"] = str(read["fetchsize"])


def _apply_incremental(options: dict[str, str], source: dict[str, Any]) -> None:
    incremental = source.get("incremental", {}) or {}
    if not isinstance(incremental, dict):
        raise ValueError("JDBC source.incremental must be an object")
    watermark_value = _incremental_watermark_value(source, incremental)
    if watermark_value in (None, ""):
        return
    predicate = _incremental_predicate(incremental, watermark_value)
    if not predicate:
        return
    alias = str(incremental.get("alias") or "cf_src")
    if "query" in options:
        query = options.pop("query")
        options["dbtable"] = f"(SELECT * FROM ({query}) {alias} WHERE {predicate}) {alias}"
        return
    dbtable = options["dbtable"]
    options["dbtable"] = f"(SELECT * FROM {dbtable} WHERE {predicate}) {alias}"


def _incremental_watermark_value(source: dict[str, Any], incremental: dict[str, Any]) -> str | None:
    read = source.get("read", {}) or {}
    runtime = source.get("runtime", {}) or {}
    raw = (
        incremental.get("watermark_value")
        or runtime.get("watermark_value")
        or read.get("_contractforge_watermark_previous")
        or incremental.get("initial_value")
    )
    if raw in (None, ""):
        return None
    column = incremental.get("watermark_column")
    return extract_watermark_field_value(str(raw), None if column in (None, "") else str(column))


def _incremental_predicate(incremental: dict[str, Any], watermark_value: str) -> str:
    template = incremental.get("predicate")
    if template not in (None, ""):
        return str(template).format(
            watermark_previous=_sql_literal_value(watermark_value),
            watermark=_sql_literal_value(watermark_value),
            value=_sql_literal_value(watermark_value),
        )
    column = incremental.get("watermark_column")
    if column in (None, ""):
        return ""
    return f"{_validated_identifier_path(str(column))} > '{_escape_sql_string(watermark_value)}'"


def _sql_literal_value(value: str) -> str:
    return _escape_sql_string(value)


def _escape_sql_string(value: str) -> str:
    return str(value).replace("'", "''")


def _validated_identifier_path(value: str) -> str:
    parts = [part.strip() for part in value.split(".")]
    if not parts or any(not part for part in parts):
        raise ValueError("JDBC source.incremental.watermark_column must be a simple identifier")
    if not all(_IDENTIFIER_RE.match(part) for part in parts):
        raise ValueError("JDBC source.incremental.watermark_column must be a simple identifier")
    return ".".join(parts)
