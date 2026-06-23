"""Platform-neutral source contract validation helpers."""

from __future__ import annotations

import re
from typing import Any

from contractforge_core.connectors.registry import connector_catalog_entry
from contractforge_core.connectors.files import FILE_SOURCE_TYPES, OBJECT_STORAGE_TYPES
from contractforge_core.connectors.databases import JDBC_CONNECTORS

HTTP_FILE_TYPES = {"http_file", "http_csv", "http_json", "http_text"}
CATALOG_TYPES = {"table", "delta_table", "iceberg_table", "view"}
VALID_FILE_FORMATS = {"avro", "csv", "delta", "json", "jsonl", "ndjson", "orc", "parquet", "text", "xml"}
_SIMPLE_COLUMN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def validate_source_semantics(data: dict[str, Any]) -> None:
    connector = str(data.get("connector") or data.get("type") or "").strip().lower()
    _validate_limit_values(data)
    if connector in JDBC_CONNECTORS:
        _validate_jdbc(data, connector)
    elif connector in FILE_SOURCE_TYPES:
        _require(data, "path", f"source.path is required for connector={connector}")
    elif connector in OBJECT_STORAGE_TYPES:
        _validate_object_storage(data, connector)
    elif connector in HTTP_FILE_TYPES:
        _validate_http_file(data, connector)
    elif connector == "rest_api":
        _validate_rest_api(data)
    elif connector == "custom_transform":
        _validate_custom_transform(data)
    elif connector == "incremental_files":
        _validate_incremental_files(data)
    elif connector in CATALOG_TYPES:
        if not _value(data, "table") and not _value(data, "path") and not _value(data, "ref"):
            raise ValueError("source.table, source.path or source.ref is required for catalog sources")
    elif connector == "sql" and not _value(data, "query"):
        raise ValueError("source.query is required for connector=sql")
    elif connector == "native_passthrough":
        _require(data, "system", "source.system is required for native_passthrough")
    elif connector == "connection":
        _require(data, "connection_path", "source.connection_path is required when source.type='connection'")
    elif connector in {"kafka_bounded", "kafka_available_now"}:
        _require(data, "bootstrap_servers", f"source.bootstrap_servers is required for {connector}")
        if not (_value(data, "topic") or _value(data, "topics") or _value(data, "assign")):
            raise ValueError(f"{connector} requires source.topic, source.topics or source.assign")
        if connector == "kafka_available_now":
            _require(data, "checkpoint_location", "source.checkpoint_location is required for kafka_available_now")
    elif connector in {"eventhubs_bounded", "eventhubs_available_now"}:
        _require(data, "connection_string", f"source.connection_string is required for {connector}")
        _require(data, "event_hub_name", f"source.event_hub_name is required for {connector}")
        if connector == "eventhubs_available_now":
            _require(data, "checkpoint_location", "source.checkpoint_location is required for eventhubs_available_now")
    elif connector == "delta_share":
        _require(data, "profile_file", "source.profile_file is required for delta_share")
        _require(data, "table", "source.table is required for delta_share")


def _validate_jdbc(data: dict[str, Any], connector: str) -> None:
    options = _mapping(data.get("options"))
    table = _value(data, "table") or _value(options, "dbtable")
    query = _value(data, "query") or _value(options, "query")
    if table and query:
        raise ValueError("JDBC connector accepts source.table or source.query, not both")
    if not _value(data, "url") and not _value(options, "url"):
        raise ValueError(f"source.url or source.options.url is required for connector={connector}")
    if not table and not query:
        raise ValueError(f"connector={connector} requires source.table, source.query, source.options.dbtable or source.options.query")
    read = _mapping(data.get("read"))
    partition_fields = {"partition_column", "lower_bound", "upper_bound", "num_partitions"}
    provided = {field for field in partition_fields if read.get(field) not in (None, "")}
    if provided and provided != partition_fields:
        raise ValueError("JDBC partitioning requires source.read.partition_column, source.read.lower_bound, source.read.upper_bound and source.read.num_partitions together")


def _validate_object_storage(data: dict[str, Any], connector: str) -> None:
    provider = str(data.get("provider") or "").strip()
    expected = {"s3": "s3", "adls": "adls", "azure_blob": "azure_blob", "gcs": "gcs"}.get(connector)
    if provider and expected and provider != expected:
        raise ValueError(f"source.provider={provider!r} conflicts with connector={connector!r}")
    fmt = _value(data, "format")
    if not fmt:
        raise ValueError("source.format is required for object storage sources")
    if fmt not in VALID_FILE_FORMATS:
        raise ValueError(f"source.format={fmt!r} is not supported")
    _require(data, "path", f"source.path is required for connector={connector}")


def _validate_http_file(data: dict[str, Any], connector: str) -> None:
    request = _mapping(data.get("request"))
    if not _value(data, "path") and not _value(request, "url") and not _value(data, "url"):
        raise ValueError(f"source.path, source.url or source.request.url is required for connector={connector}")
    fmt = str(data.get("format") or _mapping(data.get("response")).get("format") or {"http_csv": "csv", "http_json": "json", "http_text": "text"}.get(connector, "")).strip()
    if not fmt:
        raise ValueError("source.format is required for connector=http_file")
    if fmt not in {"csv", "json", "jsonl", "ndjson", "text"}:
        raise ValueError(f"source.format={fmt!r} is not supported")
    if str(request.get("method") or "GET").upper() != "GET":
        raise ValueError(f"connector={connector} supports only HTTP GET")
    auth = _mapping(data.get("auth"))
    auth_type = str(auth.get("type") or "none").strip().lower()
    if auth_type not in {"none", "bearer_token", "api_key", "basic"}:
        raise ValueError(f"auth.type={auth_type!r} is not supported for connector={connector}")


def _validate_rest_api(data: dict[str, Any]) -> None:
    request = _mapping(data.get("request"))
    if not _value(request, "url") and not _value(data, "url") and not _value(data, "path"):
        raise ValueError("source.request.url or source.url is required for connector=rest_api")
    if str(request.get("method") or "GET").upper() not in {"GET", "POST"}:
        raise ValueError("connector=rest_api supports only GET and POST")
    auth_type = str(_mapping(data.get("auth")).get("type") or "none").strip().lower()
    if auth_type not in {"none", "bearer_token", "api_key", "basic", "oauth_client_credentials"}:
        raise ValueError(f"auth.type={auth_type!r} is not supported for connector=rest_api")
    page_type = str(_mapping(data.get("pagination")).get("type") or "none").strip().lower()
    if page_type not in {"none", "page", "offset", "cursor", "link_header"}:
        raise ValueError(f"pagination.type={page_type!r} is not supported")
    if page_type == "cursor" and not _mapping(data.get("pagination")).get("next_cursor_path"):
        raise ValueError("pagination.next_cursor_path is required when pagination.type=cursor")
    response = _mapping(data.get("response"))
    response_mode = str(response.get("mode") or "records").strip().lower()
    if response_mode not in {"records", "raw"}:
        raise ValueError("source.response.mode must be 'records' or 'raw'")
    if response_mode == "raw":
        raw_column = str(response.get("raw_column") or "raw_response").strip()
        if not raw_column:
            raise ValueError("source.response.raw_column cannot be empty when response.mode=raw")
        if not _SIMPLE_COLUMN_RE.match(raw_column):
            raise ValueError("source.response.raw_column must be a simple column name")
        if response.get("records_path"):
            raise ValueError("source.response.records_path must not be used when response.mode=raw")
    if _mapping(data.get("incremental")).get("watermark_body_field") and "json" not in request:
        raise ValueError("source.incremental.watermark_body_field requires source.request.json")


def _validate_incremental_files(data: dict[str, Any]) -> None:
    _require(data, "path", "source.path is required for incremental_files")
    _require(data, "format", "source.format is required for incremental_files")
    fmt = str(data.get("format") or "").strip().lower()
    if fmt not in VALID_FILE_FORMATS:
        raise ValueError(f"source.format={fmt!r} is not supported")


def _validate_custom_transform(data: dict[str, Any]) -> None:
    inputs = data.get("inputs")
    if not isinstance(inputs, list) or not inputs:
        raise ValueError("source.inputs is required for connector=custom_transform")
    aliases: set[str] = set()
    for index, item in enumerate(inputs):
        if not isinstance(item, dict):
            raise ValueError(f"source.inputs[{index}] must be an object")
        alias = str(item.get("alias") or "").strip()
        if not alias:
            raise ValueError(f"source.inputs[{index}].alias is required")
        if alias in aliases:
            raise ValueError(f"source.inputs alias {alias!r} is duplicated")
        aliases.add(alias)
        if not (
            _value(item, "ref")
            or _value(item, "table")
            or _value(item, "table_ref")
            or _value(item, "path")
            or _value(item, "query")
        ):
            raise ValueError(
                f"source.inputs[{index}] must declare one of ref, table, table_ref, path or query"
            )


def _validate_limit_values(data: dict[str, Any]) -> None:
    limits = _mapping(data.get("limits"))
    _validate_supported_limits(data, limits)
    for name in (
        "timeout_seconds",
        "retry_attempts",
        "max_files",
        "max_pages",
        "page_size",
        "max_records",
        "max_offsets_per_trigger",
        "max_events_per_trigger",
    ):
        _positive_int(limits.get(name), f"source.limits.{name}")
    for name in ("max_bytes", "max_page_bytes", "max_total_bytes", "rate_limit_per_minute"):
        _non_negative_int(limits.get(name), f"source.limits.{name}")
    _non_negative_float(limits.get("retry_backoff_seconds"), "source.limits.retry_backoff_seconds")
    read = _mapping(data.get("read"))
    for name in ("fetchsize", "num_partitions", "max_files_per_trigger", "file_regex_max_listed"):
        _positive_int(read.get(name), f"source.read.{name}")


def _validate_supported_limits(data: dict[str, Any], limits: dict[str, Any]) -> None:
    if not limits:
        return
    connector = str(data.get("connector") or data.get("type") or "").strip().lower()
    entry = connector_catalog_entry(connector)
    supported = set(entry.get("limits") or ())
    supported = {item.removeprefix("source.limits.") for item in supported if "." not in item or item.startswith("source.limits.")}
    unsupported = sorted(set(limits) - supported)
    if unsupported:
        if supported:
            raise ValueError(
                f"connector={connector} does not support "
                f"{', '.join(f'source.limits.{name}' for name in unsupported)}. "
                f"Supported limit fields: {', '.join(f'source.limits.{name}' for name in sorted(supported))}"
            )
        raise ValueError(
            f"connector={connector} does not support source.limits. "
            "Use source.options/read for connector-specific runtime options."
        )


def _require(data: dict[str, Any], key: str, message: str) -> None:
    if not _value(data, key):
        raise ValueError(message)


def _value(data: dict[str, Any], key: str) -> Any:
    value = data.get(key)
    return value if value not in (None, "") else None


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _positive_int(value: Any, field: str) -> None:
    if value in (None, ""):
        return
    try:
        parsed = int(value)
    except Exception as exc:
        raise ValueError(f"{field} must be a positive integer") from exc
    if parsed <= 0:
        raise ValueError(f"{field} must be a positive integer")


def _non_negative_int(value: Any, field: str) -> None:
    if value in (None, ""):
        return
    try:
        parsed = int(value)
    except Exception as exc:
        raise ValueError(f"{field} must be a non-negative integer") from exc
    if parsed < 0:
        raise ValueError(f"{field} must be a non-negative integer")


def _non_negative_float(value: Any, field: str) -> None:
    if value in (None, ""):
        return
    try:
        parsed = float(value)
    except Exception as exc:
        raise ValueError(f"{field} must be a non-negative number") from exc
    if parsed < 0:
        raise ValueError(f"{field} must be a non-negative number")
