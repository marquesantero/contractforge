"""BigQuery SQL and load-job rendering."""

from __future__ import annotations

import json
from typing import Any

from contractforge_core.connectors import http_file_format

from contractforge_core.semantic import SemanticContract
from contractforge_gcp.environment import GCPEnvironment
from contractforge_gcp.rendering.names import (
    identifier,
    public_mode,
    quote_table_ref,
    staging_table,
    target_table,
    target_table_id,
)
from contractforge_gcp.write_modes import render_bigquery_advanced_write_sql

_BQ_SOURCE_FORMATS = {
    "avro": "AVRO",
    "csv": "CSV",
    "json": "NEWLINE_DELIMITED_JSON",
    "jsonl": "NEWLINE_DELIMITED_JSON",
    "ndjson": "NEWLINE_DELIMITED_JSON",
    "orc": "ORC",
    "parquet": "PARQUET",
}


def render_bigquery_write_sql(contract: SemanticContract, env: GCPEnvironment) -> str:
    target = target_table(contract, env)
    source_sql = _source_sql(contract, env)
    mode = contract.write.mode
    if mode == "scd0_append":
        return f"INSERT INTO {target}\n{source_sql};\n"
    if mode == "scd0_overwrite":
        return f"CREATE OR REPLACE TABLE {target} AS\n{source_sql};\n"
    if mode == "scd1_upsert":
        return _merge_sql(contract, env, source_sql=source_sql)
    advanced_sql = render_bigquery_advanced_write_sql(contract, env)
    if advanced_sql:
        return advanced_sql
    return f"-- Write mode `{public_mode(mode)}` is review-required for the GCP BigQuery adapter.\n"


def render_bigquery_load_job_config(contract: SemanticContract, env: GCPEnvironment) -> str:
    source = contract.source.raw or {}
    source_type = str(source.get("type") or source.get("connector") or "").strip().lower()
    fmt = str(source.get("format") or source.get("file_format") or source_type).strip().lower()
    path = str(source.get("path") or "").strip()
    if fmt not in _BQ_SOURCE_FORMATS or not path.startswith("gs://"):
        return ""
    options = source.get("options") if isinstance(source.get("options"), dict) else {}
    payload: dict[str, Any] = {
        "source_uris": [path],
        "destination_table": target_table_id(contract, env),
        "source_format": _BQ_SOURCE_FORMATS[fmt],
        "write_disposition": "WRITE_TRUNCATE" if contract.write.mode == "scd0_overwrite" else "WRITE_APPEND",
    }
    if fmt == "csv":
        payload["skip_leading_rows"] = int(options.get("skip_leading_rows", options.get("skipLeadingRows", 1)))
        payload["autodetect"] = bool(options.get("autodetect", True))
    if fmt in {"json", "jsonl", "ndjson"}:
        payload["autodetect"] = bool(options.get("autodetect", True))
    schema_fields = _source_schema_fields(contract)
    if schema_fields:
        payload["schema_fields"] = schema_fields
        payload.pop("autodetect", None)
    return json.dumps(payload, indent=2, sort_keys=True)


def render_bigquery_source_materialization_plan(contract: SemanticContract, env: GCPEnvironment) -> str:
    source = contract.source.raw or {}
    source_type = str(source.get("connector") or source.get("type") or "").strip().lower()
    if source_type not in {"rest_api", "api", "http_api", "http_json", "http_csv", "http_text", "http_file"}:
        return ""
    http_format = _http_source_format(source)
    if source_type == "http_file" and http_format not in {"avro", "csv", "json", "jsonl", "ndjson", "orc", "parquet", "text"}:
        return ""
    if source_type in {"rest_api", "api", "http_api", "http_json", "http_text"} or (
        source_type == "http_file" and http_format in {"json", "jsonl", "ndjson", "text"}
    ):
        source_format = "NEWLINE_DELIMITED_JSON"
        local_format = "ndjson"
        reader = "contractforge_core.connectors.read_rest_api_records" if source_type in {"rest_api", "api", "http_api"} else "contractforge_core.connectors.read_http_file_payload"
    elif source_type == "http_csv" or (source_type == "http_file" and http_format == "csv"):
        source_format = "CSV"
        local_format = "csv"
        reader = "contractforge_core.connectors.read_http_file_payload"
    else:
        source_format = _BQ_SOURCE_FORMATS[http_format]
        local_format = http_format
        reader = "contractforge_core.connectors.read_http_file_payload"
    payload: dict[str, Any] = {
        "kind": "contractforge.gcp.bigquery_source_materialization.v1",
        "source_type": source_type,
        "reader": reader,
        "local_format": local_format,
        "destination_table": target_table_id(contract, env),
        "source_format": source_format,
        "write_disposition": "WRITE_TRUNCATE" if contract.write.mode == "scd0_overwrite" else "WRITE_APPEND",
        "runtime": "temporary local file loaded with BigQuery load job",
        "evidence": "same run and lineage evidence path as GCS load jobs",
    }
    options = source.get("options") if isinstance(source.get("options"), dict) else {}
    if source_type == "http_csv" or (source_type == "http_file" and http_format == "csv"):
        payload["skip_leading_rows"] = int(options.get("skip_leading_rows", options.get("skipLeadingRows", 1)))
        payload["autodetect"] = bool(options.get("autodetect", True))
    if source_type in {"rest_api", "api", "http_api", "http_json", "http_text"} or (
        source_type == "http_file" and http_format in {"json", "jsonl", "ndjson", "text"}
    ):
        payload["autodetect"] = bool(options.get("autodetect", True))
    schema_fields = _source_schema_fields(contract)
    if (source_type == "http_text" or (source_type == "http_file" and http_format == "text")) and not schema_fields:
        schema_fields = [{"name": _http_text_column(source), "type": "STRING"}]
    if schema_fields:
        payload["schema_fields"] = schema_fields
        payload.pop("autodetect", None)
    return json.dumps(payload, indent=2, sort_keys=True)


def render_bigquery_quality_sql(contract: SemanticContract, env: GCPEnvironment) -> str:
    if not contract.quality:
        return ""
    source = target_table(contract, env)
    statements: list[str] = []
    for quality in contract.quality:
        if quality.rule == "not_null" and quality.columns:
            predicate = " OR ".join(f"{identifier(column)} IS NULL" for column in quality.columns)
            statements.append(_quality_count_sql(quality.name, quality.rule, source, predicate))
        elif quality.rule == "unique_key" and quality.columns:
            keys = ", ".join(identifier(column) for column in quality.columns)
            statements.append(
                "\n".join(
                    [
                        f"-- {quality.name}: unique key",
                        "SELECT COUNT(*) AS failed_rows",
                        "FROM (",
                        f"  SELECT {keys}, COUNT(*) AS row_count",
                        f"  FROM {source}",
                        f"  GROUP BY {keys}",
                        "  HAVING COUNT(*) > 1",
                        ");",
                    ]
                )
            )
        elif quality.rule == "expression" and quality.value:
            statements.append(_quality_count_sql(quality.name, quality.rule, source, f"NOT ({quality.value})"))
        else:
            statements.append(f"-- {quality.name}: `{quality.rule}` requires adapter review.")
    return "\n\n".join(statements) + "\n"


def _quality_count_sql(name: str, rule: str, table: str, predicate: str) -> str:
    return "\n".join([f"-- {name}: {rule}", "SELECT COUNT(*) AS failed_rows", f"FROM {table}", f"WHERE {predicate};"])


def _source_sql(contract: SemanticContract, env: GCPEnvironment) -> str:
    source = contract.source.raw or {}
    source_type = str(source.get("type") or source.get("connector") or "").strip().lower()
    if source_type == "sql":
        options = source.get("options") if isinstance(source.get("options"), dict) else {}
        return str(source.get("query") or options.get("query") or "SELECT * FROM source_query")
    if source_type in {"table", "view", "iceberg_table"}:
        table = source.get("table") or source.get("table_ref") or source.get("ref") or contract.source.location
        return f"SELECT * FROM {quote_table_ref(str(table), env)}"
    return f"SELECT * FROM {staging_table(contract, env)}"


def _merge_sql(contract: SemanticContract, env: GCPEnvironment, *, source_sql: str) -> str:
    if not contract.write.merge_keys:
        return "-- upsert requires merge_keys.\n"
    columns = _merge_columns(contract)
    if not columns:
        return (
            "-- upsert requires explicit source columns for executable BigQuery MERGE rendering. "
            "Declare top-level select_columns or source.read.columns.\n"
        )
    target = target_table(contract, env)
    on_clause = " AND ".join(f"T.{identifier(key)} = S.{identifier(key)}" for key in contract.write.merge_keys)
    update_columns = [column for column in columns if column not in set(contract.write.merge_keys)]
    insert_columns = ", ".join(identifier(column) for column in columns)
    insert_values = ", ".join(f"S.{identifier(column)}" for column in columns)
    matched_clause = []
    if update_columns:
        matched_clause = [
            "WHEN MATCHED THEN",
            "  UPDATE SET " + ", ".join(f"{identifier(column)} = S.{identifier(column)}" for column in update_columns),
        ]
    return "\n".join(
        [
            f"MERGE {target} AS T",
            f"USING ({source_sql}) AS S",
            f"ON {on_clause}",
            *matched_clause,
            "WHEN NOT MATCHED THEN",
            f"  INSERT ({insert_columns}) VALUES ({insert_values});",
            "",
        ]
    )


def _merge_columns(contract: SemanticContract) -> list[str]:
    metadata = contract.operations.metadata if contract.operations and isinstance(contract.operations.metadata, dict) else {}
    for value in (
        metadata.get("select_columns"),
        _source_read(contract).get("columns"),
        _source_read(contract).get("select_columns"),
    ):
        columns = _column_list(value)
        if columns:
            return columns
    return []


def _source_read(contract: SemanticContract) -> dict[str, Any]:
    source = contract.source.raw or {}
    read = source.get("read") if isinstance(source.get("read"), dict) else {}
    return read


def _source_schema_fields(contract: SemanticContract) -> list[dict[str, str]]:
    source = contract.source.raw or {}
    read = _source_read(contract)
    for value in (read.get("schema"), read.get("columns"), source.get("schema"), source.get("columns")):
        fields = _schema_fields(value)
        if fields:
            return fields
    return []


def _http_text_column(source: dict[str, Any]) -> str:
    response = source.get("response") if isinstance(source.get("response"), dict) else {}
    raw_column = str(response.get("raw_column") or "").strip()
    if raw_column:
        return raw_column
    read = source.get("read") if isinstance(source.get("read"), dict) else {}
    for field in _schema_fields(read.get("columns")):
        if field["name"]:
            return field["name"]
    return "value"


def _http_source_format(source: dict[str, Any]) -> str:
    try:
        return str(http_file_format(source)).strip().lower()
    except Exception:
        response = source.get("response") if isinstance(source.get("response"), dict) else {}
        return str(source.get("format") or response.get("format") or "").strip().lower()


def _schema_fields(value: Any) -> list[dict[str, str]]:
    if isinstance(value, dict):
        return [
            {"name": str(name).strip(), "type": _normalize_bigquery_type(str(data_type or "STRING"))}
            for name, data_type in value.items()
            if str(name).strip()
        ]
    if isinstance(value, (list, tuple)):
        fields: list[dict[str, str]] = []
        for item in value:
            if isinstance(item, str):
                name = item.strip()
                if name:
                    fields.append({"name": name, "type": "STRING"})
            elif isinstance(item, dict):
                name = str(item.get("name") or item.get("column") or item.get("field") or "").strip()
                if name:
                    fields.append({"name": name, "type": _normalize_bigquery_type(str(item.get("type") or item.get("data_type") or "STRING"))})
        return fields
    return []


def _column_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, (list, tuple)):
        columns: list[str] = []
        for item in value:
            if isinstance(item, dict):
                name = str(item.get("name") or item.get("column") or item.get("field") or "").strip()
                if name:
                    columns.append(name)
            else:
                name = str(item).strip()
                if name:
                    columns.append(name)
        return columns
    return []


def _normalize_bigquery_type(value: str) -> str:
    aliases = {
        "BOOL": "BOOLEAN",
        "FLOAT": "FLOAT64",
        "INTEGER": "INT64",
    }
    text = value.strip().upper()
    return aliases.get(text, text)
