from __future__ import annotations

from typing import Any

from contractforge_core.connectors import (
    catalog_source_query,
    catalog_source_table_or_path,
    delta_share_options,
    eventhubs_bounded_options,
    file_reader_options,
    file_source_format,
    is_available_now_stream_source,
    is_bounded_stream_source,
    is_catalog_source,
    is_delta_share_source,
    is_file_source,
    is_http_file_source,
    is_kafka_stream_source,
    is_rest_api_connector,
    jdbc_common_options,
    kafka_bounded_options,
    stream_source_format,
)
from contractforge_core.runtime import PreparedInput
from contractforge_core.runtime import QueryOne
from contractforge_core.semantic import SemanticContract
from contractforge_databricks.preparation import apply_contract_preparation, apply_write_staging
from contractforge_databricks.runtime.file_selection import selected_file_load_path
from contractforge_databricks.runtime.http_file import resolve_http_file_dataframe
from contractforge_databricks.runtime.rest_api import resolve_rest_api_dataframe
from contractforge_databricks.runtime.source_schema import apply_declared_schema
from contractforge_databricks.runtime.source_metadata import (
    schema_types,
    source_metadata,
    source_metadata_with_watermark,
    source_name,
)
from contractforge_databricks.runtime.source_registry import get_source_resolver
from contractforge_databricks.runtime.watermark import collect_previous_watermark
from contractforge_databricks.runtime.storage_auth import configure_object_storage_access
from contractforge_databricks.security import resolve_databricks_secret_placeholders, validate_source_security
from contractforge_databricks.sources.interpret import interpret_incremental_files_source, is_incremental_file_source
from contractforge_databricks.sources.rds_iam_runtime import materialize_rds_iam_options
from contractforge_databricks.sources.table_refs import (
    contract_with_databricks_source_refs,
    databricks_table_ref_resolver,
)

_JDBC_SOURCE_ALIASES = {"jdbc", "postgres", "mysql", "sqlserver", "oracle", "redshift", "db2", "mariadb", "snowflake_jdbc", "bigquery_jdbc"}
_KAFKA_LOGIN_MODULE = "org.apache.kafka.common.security.plain.PlainLoginModule"
_DATABRICKS_SHADED_KAFKA_LOGIN_MODULE = "kafkashaded.org.apache.kafka.common.security.plain.PlainLoginModule"


def resolve_source_dataframe(spark: Any, source: dict[str, Any], *, contract: SemanticContract | None = None) -> Any:
    """Resolve a core source contract into a Databricks DataFrame."""

    validate_source_security(source)
    source = resolve_databricks_secret_placeholders(source)
    source_type = source.get("type")
    custom_resolver = get_source_resolver(str(source.get("connector") or source_type or ""))
    if custom_resolver is not None:
        return custom_resolver.resolve(spark, source)
    if is_catalog_source(source):
        return _resolve_catalog_source(spark, source, contract=contract)
    if is_incremental_file_source(source):
        return _resolve_autoloader_source(spark, source)
    if is_file_source(source):
        options = file_reader_options(source)
        path, options = configure_object_storage_access(spark, source, options)
        source = {**source, "path": path} if path is not None else source
        return _read_source_with_options(
            spark.read,
            file_source_format(source),
            options,
            selected_file_load_path(spark, source, options),
            source,
        )
    if is_http_file_source(source):
        return resolve_http_file_dataframe(spark, source)
    if is_rest_api_connector(source):
        return resolve_rest_api_dataframe(spark, source)
    if source_type in {"jdbc", "connector"} or source.get("connector") in _JDBC_SOURCE_ALIASES:
        jdbc_options = materialize_rds_iam_options(
            jdbc_common_options(source),
            auth=source.get("auth"),
        )
        return _read_with_options(spark.read, "jdbc", jdbc_options, None)
    if is_bounded_stream_source(source) or is_available_now_stream_source(source):
        options = kafka_bounded_options(source) if is_kafka_stream_source(source) else eventhubs_bounded_options(source)
        if is_kafka_stream_source(source):
            options = _databricks_kafka_options(options)
        source_format = stream_source_format(source)
        reader = spark.readStream if is_available_now_stream_source(source) else spark.read
        return _read_with_options(reader, source_format, options, None)
    if is_delta_share_source(source):
        return _read_with_options(spark.read, "deltaSharing", delta_share_options(source), None)
    raise ValueError(f"source.type={source_type!r} cannot be resolved by the Databricks runtime source resolver")


def prepare_source_view(
    spark: Any,
    source: dict[str, Any],
    *,
    view_name: str,
    collect_metrics: bool = False,
) -> PreparedInput:
    """Resolve a source and register it as a temporary view for ingestion."""

    df = resolve_source_dataframe(spark, source)
    df.createOrReplaceTempView(view_name)
    columns = tuple(str(column) for column in getattr(df, "columns", ()) or ())
    rows_read = int(df.count()) if collect_metrics else 0
    return PreparedInput(
        source_view=view_name,
        source_columns=columns,
        source_schema=schema_types(df),
        rows_read=rows_read,
        source_name=source_name(source),
        source_metadata=source_metadata(source),
    )


def prepare_contract_source_view(
    spark: Any,
    contract: SemanticContract,
    *,
    view_name: str,
    collect_metrics: bool = False,
    query_one: QueryOne | None = None,
    evidence_catalog: str = "main",
    evidence_schema: str = "ops",
) -> PreparedInput:
    """Resolve, prepare and register the contract source as a temporary view."""

    if not contract.source.raw:
        raise ValueError("prepare_contract_source_view requires a structured source contract")
    runtime_contract = contract_with_databricks_source_refs(contract)
    df = resolve_source_dataframe(spark, runtime_contract.source.raw or {}, contract=runtime_contract)
    watermark_column, watermark_previous = collect_previous_watermark(
        contract=contract,
        query_one=query_one,
        catalog=evidence_catalog,
        schema=evidence_schema,
    )
    df = apply_contract_preparation(
        df,
        contract,
        watermark_column=watermark_column,
        watermark_previous=watermark_previous,
    )
    df = apply_write_staging(df, contract)
    df.createOrReplaceTempView(view_name)
    columns = tuple(str(column) for column in getattr(df, "columns", ()) or ())
    rows_read = int(df.count()) if collect_metrics else 0
    return PreparedInput(
        source_view=view_name,
        source_columns=columns,
        source_schema=schema_types(df),
        rows_read=rows_read,
        source_name=runtime_contract.source.name,
        source_metadata=source_metadata_with_watermark(runtime_contract.source.raw or {}, watermark_previous),
    )


def _resolve_catalog_source(spark: Any, source: dict[str, Any], *, contract: SemanticContract | None = None) -> Any:
    resolver = databricks_table_ref_resolver(contract) if contract is not None else None
    if source.get("type") == "sql" or source.get("connector") == "sql":
        return spark.sql(catalog_source_query(source, table_ref_resolver=resolver))
    table_or_path = catalog_source_table_or_path(source, table_ref_resolver=resolver)
    if source.get("path") and not source.get("table"):
        source_type = str(source.get("type") or "delta")
        source_format = "delta" if source_type == "delta_table" else source_type.replace("_table", "")
        return _read_with_options(spark.read, source_format, {}, table_or_path)
    return spark.table(str(table_or_path))


def _resolve_autoloader_source(spark: Any, source: dict[str, Any]) -> Any:
    interpreted = interpret_incremental_files_source(source)
    options = {"cloudFiles.format": str(interpreted.get("format") or "json")}
    options.update({str(key): str(value) for key, value in interpreted.get("options", {}).items()})
    if interpreted.get("schema_tracking_location"):
        options["cloudFiles.schemaLocation"] = str(interpreted["schema_tracking_location"])
    if interpreted.get("schema_hints"):
        options["cloudFiles.schemaHints"] = str(interpreted["schema_hints"])
    return _read_with_options(spark.readStream, "cloudFiles", options, interpreted.get("path"))


def _databricks_kafka_options(options: dict[str, str]) -> dict[str, str]:
    normalized = dict(options)
    jaas_config = normalized.get("kafka.sasl.jaas.config")
    if jaas_config:
        normalized["kafka.sasl.jaas.config"] = " ".join(
            str(jaas_config)
            .replace(_KAFKA_LOGIN_MODULE, _DATABRICKS_SHADED_KAFKA_LOGIN_MODULE)
            .splitlines()
        ).strip()
    return normalized


def _read_with_options(reader: Any, source_format: str, options: dict[str, str], path: object | None) -> Any:
    builder = reader.format(source_format)
    for key, value in sorted(options.items()):
        builder = builder.option(key, value)
    return builder.load(path if isinstance(path, list) else str(path)) if path is not None else builder.load()


def _read_source_with_options(
    reader: Any,
    source_format: str,
    options: dict[str, str],
    path: object | None,
    source: dict[str, Any],
) -> Any:
    builder = reader.format(source_format)
    for key, value in sorted(options.items()):
        builder = builder.option(key, value)
    builder = apply_declared_schema(builder, source)
    return builder.load(path if isinstance(path, list) else str(path)) if path is not None else builder.load()
