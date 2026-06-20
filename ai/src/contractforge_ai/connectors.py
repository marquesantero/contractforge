"""AI-facing connector awareness backed by the ContractForge Core catalog."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from contractforge_core.connectors.registry import CONNECTOR_CATALOG
from contractforge_core.connectors.metadata import source_connector_details


@dataclass(frozen=True)
class ConnectorIntent:
    """Normalized connector decision for AI planning."""

    connector: str
    original: str
    portability: str
    display_name: str | None = None
    family: str | None = None
    description: str | None = None
    required_fields: tuple[str, ...] = ()
    adapter: str | None = None
    recommendation: str | None = None
    supported_by_core: bool = False

    def to_signal(self) -> str:
        suffix = f" from {self.original!r}" if self.original != self.connector else ""
        return f"connector:{self.connector}{suffix}"

    def to_message(self) -> str:
        """Return a user-facing connector explanation for deterministic reviews."""

        status = "supported" if self.supported_by_core else "unsupported"
        required = f" Required fields: {', '.join(self.required_fields)}." if self.required_fields else ""
        details = f" {self.description}" if self.description else ""
        recommendation = f" {self.recommendation}" if self.recommendation else ""
        return (
            f"{self.display_name or self.connector} resolves to core source type "
            f"`{self.connector}` ({status} by ContractForge Core, portability={self.portability})."
            f"{details}{required}{recommendation}"
        ).strip()


_PORTABLE_FILE_DISCOVERY_MESSAGE = (
    "Auto Loader/cloudFiles is Databricks-specific; use core source type "
    "incremental_files for portable checkpointed file discovery."
)
_BOUNDED_STREAM_MESSAGE = (
    "Use the core bounded stream source for finite replay/catch-up. Continuous "
    "streaming remains adapter-specific until explicitly planned."
)
_AVAILABLE_NOW_MESSAGE = (
    "Use the core available-now stream source only when checkpointed catch-up "
    "is intended and the adapter planner supports it."
)
_NATIVE_PASSTHROUGH_MESSAGE = (
    "This is not a portable built-in connector. Use core source type "
    "native_passthrough so the selected adapter can render a native handoff."
)
_GENERIC_FILES_MESSAGE = (
    "ContractForge Core does not use a vague 'files' connector as the canonical "
    "source type. Choose a concrete file format source such as csv/json/parquet "
    "or a storage source such as s3/adls/gcs/object_storage."
)

_DISPLAY_NAMES: dict[str, str] = {
    "adls": "Azure Data Lake Storage",
    "avro": "Avro files",
    "azure_blob": "Azure Blob Storage",
    "bigquery_jdbc": "BigQuery JDBC",
    "blob": "Generic blob storage",
    "connection": "Shared connection YAML",
    "csv": "CSV files",
    "db2": "IBM Db2 JDBC",
    "delta": "Delta files",
    "delta_share": "Delta Sharing",
    "delta_table": "Delta table",
    "eventhubs_available_now": "Event Hubs available-now stream",
    "eventhubs_bounded": "Event Hubs bounded replay",
    "gcs": "Google Cloud Storage",
    "http_csv": "HTTP CSV file",
    "http_file": "HTTP file",
    "http_json": "HTTP JSON file",
    "http_text": "HTTP text file",
    "iceberg_table": "Iceberg table",
    "incremental_files": "Incremental files",
    "jdbc": "Generic JDBC",
    "json": "JSON files",
    "jsonl": "JSON Lines files",
    "kafka_available_now": "Kafka available-now stream",
    "kafka_bounded": "Kafka bounded replay",
    "mariadb": "MariaDB JDBC",
    "mysql": "MySQL JDBC",
    "native_passthrough": "Native platform connector handoff",
    "ndjson": "Newline-delimited JSON files",
    "object_storage": "Provider-neutral object storage",
    "oracle": "Oracle JDBC",
    "orc": "ORC files",
    "parquet": "Parquet files",
    "postgres": "PostgreSQL JDBC",
    "redshift": "Amazon Redshift JDBC",
    "rest_api": "REST API",
    "s3": "Amazon S3",
    "snowflake_jdbc": "Snowflake JDBC",
    "sql": "SQL query",
    "sqlserver": "Microsoft SQL Server JDBC",
    "table": "Registered table",
    "text": "Text files",
    "view": "Registered view",
    "xml": "XML files",
}

_CONNECTOR_NORMALIZATION: dict[str, tuple[str, str | None, str | None]] = {
    "database_table": ("table", None, "Use core source type table for registered lakehouse tables."),
    "registered_table": ("table", None, "Use core source type table for registered lakehouse tables."),
    "lakehouse_table": ("table", None, "Use core source type table for registered lakehouse tables."),
    "delta_lake": ("delta_table", None, "Use delta_table for registered/path-based Delta tables; use delta for raw path-based Delta files."),
    "iceberg": ("iceberg_table", None, "Use iceberg_table for registered/path-based Apache Iceberg tables."),
    "query": ("sql", None, "Use core source type sql for declarative source queries."),
    "auto_loader": ("incremental_files", "databricks", _PORTABLE_FILE_DISCOVERY_MESSAGE),
    "autoloader": ("incremental_files", "databricks", _PORTABLE_FILE_DISCOVERY_MESSAGE),
    "cloudfiles": ("incremental_files", "databricks", _PORTABLE_FILE_DISCOVERY_MESSAGE),
    "cloud_files": ("incremental_files", "databricks", _PORTABLE_FILE_DISCOVERY_MESSAGE),
    "snowpipe": ("incremental_files", "snowflake", "Snowpipe is Snowflake-specific; use incremental_files for portable new-file discovery intent."),
    "glue_bookmark": ("incremental_files", "aws", "Glue bookmarks are AWS-specific tracking; use incremental_files for portable new-file discovery intent."),
    "file_stream": ("incremental_files", None, "Use core source type incremental_files for portable new-file discovery."),
    "new_files": ("incremental_files", None, "Use core source type incremental_files for portable new-file discovery."),
    "files": ("object_storage", None, _GENERIC_FILES_MESSAGE),
    "file": ("object_storage", None, _GENERIC_FILES_MESSAGE),
    "folder": ("object_storage", None, _GENERIC_FILES_MESSAGE),
    "local_files": ("object_storage", None, _GENERIC_FILES_MESSAGE),
    "s3a": ("s3", "aws", "Use core source type s3 for Amazon S3 paths; s3a is a runtime URI scheme."),
    "aws_s3": ("s3", "aws", "Use core source type s3 for Amazon S3 paths."),
    "amazon_s3": ("s3", "aws", "Use core source type s3 for Amazon S3 paths."),
    "s3_bucket": ("s3", "aws", "Use core source type s3 for Amazon S3 paths."),
    "bucket": ("s3", "aws", "Use core source type s3 when the bucket is Amazon S3."),
    "abfs": ("adls", "azure", "Use core source type adls for Azure Data Lake Storage paths."),
    "abfss": ("adls", "azure", "Use core source type adls for Azure Data Lake Storage paths."),
    "azure_data_lake": ("adls", "azure", "Use core source type adls for Azure Data Lake Storage paths."),
    "azure_data_lake_storage": ("adls", "azure", "Use core source type adls for Azure Data Lake Storage paths."),
    "adlsgen2": ("adls", "azure", "Use core source type adls for Azure Data Lake Storage Gen2."),
    "azure_storage": ("azure_blob", "azure", "Use core source type azure_blob for Azure Blob Storage."),
    "wasbs": ("azure_blob", "azure", "Use core source type azure_blob for Azure Blob Storage paths."),
    "wasb": ("azure_blob", "azure", "Use core source type azure_blob for Azure Blob Storage paths."),
    "gs": ("gcs", "gcp", "Use core source type gcs for Google Cloud Storage paths."),
    "google_cloud_storage": ("gcs", "gcp", "Use core source type gcs for Google Cloud Storage paths."),
    "gcp_bucket": ("gcs", "gcp", "Use core source type gcs for Google Cloud Storage paths."),
    "http_csv_file": ("http_csv", None, "Use http_csv for bounded HTTP(S) CSV file fetches."),
    "http_json_file": ("http_json", None, "Use http_json for bounded HTTP(S) JSON file fetches."),
    "http_text_file": ("http_text", None, "Use http_text for bounded HTTP(S) text file fetches."),
    "http": ("http_file", None, "Use http_file/http_csv/http_json/http_text for bounded HTTP file fetches."),
    "https": ("http_file", None, "Use http_file/http_csv/http_json/http_text for bounded HTTP file fetches."),
    "url": ("http_file", None, "Use http_file/http_csv/http_json/http_text for bounded HTTP file fetches."),
    "api": ("rest_api", None, "Use rest_api for bounded generic REST pulls; use native_passthrough for specialized SaaS APIs."),
    "endpoint": ("rest_api", None, "Use rest_api for bounded generic REST pulls; use native_passthrough for specialized SaaS APIs."),
    "graphql": ("native_passthrough", None, "GraphQL behavior varies by API; use native_passthrough unless the call is a bounded generic REST pull."),
    "postgresql": ("postgres", None, "Use core source type postgres for PostgreSQL JDBC ingestion."),
    "postgres_database": ("postgres", None, "Use core source type postgres for PostgreSQL JDBC ingestion."),
    "rds_postgres": ("postgres", "aws", "Use core source type postgres for PostgreSQL JDBC ingestion; RDS IAM is an auth mode, not a source type."),
    "rds_postgresql": ("postgres", "aws", "Use core source type postgres for PostgreSQL JDBC ingestion; RDS IAM is an auth mode, not a source type."),
    "rds_mysql": ("mysql", "aws", "Use core source type mysql for MySQL JDBC ingestion; RDS is the hosting platform."),
    "sql_server": ("sqlserver", None, "Use core source type sqlserver for Microsoft SQL Server JDBC ingestion."),
    "mssql": ("sqlserver", None, "Use core source type sqlserver for Microsoft SQL Server JDBC ingestion."),
    "microsoft_sql_server": ("sqlserver", None, "Use core source type sqlserver for Microsoft SQL Server JDBC ingestion."),
    "oracle_database": ("oracle", None, "Use core source type oracle; the runtime must provide the Oracle JDBC driver."),
    "snowflake": ("snowflake_jdbc", "snowflake", "Use core source type snowflake_jdbc for JDBC-based Snowflake ingestion."),
    "bigquery": ("bigquery_jdbc", "gcp", "Use core source type bigquery_jdbc for JDBC-based BigQuery ingestion."),
    "big_query": ("bigquery_jdbc", "gcp", "Use core source type bigquery_jdbc for JDBC-based BigQuery ingestion."),
    "kafka": ("kafka_bounded", None, _BOUNDED_STREAM_MESSAGE),
    "kafka_replay": ("kafka_bounded", None, _BOUNDED_STREAM_MESSAGE),
    "kafka_catchup": ("kafka_bounded", None, _BOUNDED_STREAM_MESSAGE),
    "kafka_available_now": ("kafka_available_now", None, _AVAILABLE_NOW_MESSAGE),
    "eventhub": ("eventhubs_bounded", "azure", _BOUNDED_STREAM_MESSAGE),
    "event_hub": ("eventhubs_bounded", "azure", _BOUNDED_STREAM_MESSAGE),
    "eventhubs": ("eventhubs_bounded", "azure", _BOUNDED_STREAM_MESSAGE),
    "event_hubs": ("eventhubs_bounded", "azure", _BOUNDED_STREAM_MESSAGE),
    "eventhubs_available_now": ("eventhubs_available_now", "azure", _AVAILABLE_NOW_MESSAGE),
    "kinesis": ("native_passthrough", "aws", "Kinesis is not a core portable source type yet; use native_passthrough for an AWS-native handoff."),
    "aws_kinesis": ("native_passthrough", "aws", "Kinesis is not a core portable source type yet; use native_passthrough for an AWS-native handoff."),
    "delta_sharing": ("delta_share", None, "Use core source type delta_share for Delta Sharing consumer ingestion."),
    "salesforce": ("native_passthrough", None, _NATIVE_PASSTHROUGH_MESSAGE),
    "hubspot": ("native_passthrough", None, _NATIVE_PASSTHROUGH_MESSAGE),
    "zendesk": ("native_passthrough", None, _NATIVE_PASSTHROUGH_MESSAGE),
    "netsuite": ("native_passthrough", None, _NATIVE_PASSTHROUGH_MESSAGE),
    "servicenow": ("native_passthrough", None, _NATIVE_PASSTHROUGH_MESSAGE),
    "service_now": ("native_passthrough", None, _NATIVE_PASSTHROUGH_MESSAGE),
    "jira": ("native_passthrough", None, _NATIVE_PASSTHROUGH_MESSAGE),
    "workday": ("native_passthrough", None, _NATIVE_PASSTHROUGH_MESSAGE),
    "sap": ("native_passthrough", None, _NATIVE_PASSTHROUGH_MESSAGE),
    "sap_odata": ("native_passthrough", None, _NATIVE_PASSTHROUGH_MESSAGE),
    "odata": ("native_passthrough", None, _NATIVE_PASSTHROUGH_MESSAGE),
    "sharepoint": ("native_passthrough", None, _NATIVE_PASSTHROUGH_MESSAGE),
    "onedrive": ("native_passthrough", None, _NATIVE_PASSTHROUGH_MESSAGE),
    "google_drive": ("native_passthrough", None, _NATIVE_PASSTHROUGH_MESSAGE),
    "stripe": ("native_passthrough", None, _NATIVE_PASSTHROUGH_MESSAGE),
    "oracle_fusion": ("native_passthrough", None, _NATIVE_PASSTHROUGH_MESSAGE),
    "google_analytics": ("native_passthrough", None, _NATIVE_PASSTHROUGH_MESSAGE),
    "ga4": ("native_passthrough", None, _NATIVE_PASSTHROUGH_MESSAGE),
    "appflow": ("native_passthrough", "aws", "AppFlow is AWS-specific; use native_passthrough for adapter-owned native connector handoff."),
    "aws_appflow": ("native_passthrough", "aws", "AppFlow is AWS-specific; use native_passthrough for adapter-owned native connector handoff."),
    "dms": ("native_passthrough", "aws", "AWS DMS is platform-specific replication; use native_passthrough for adapter-owned native handoff."),
    "aws_dms": ("native_passthrough", "aws", "AWS DMS is platform-specific replication; use native_passthrough for adapter-owned native handoff."),
    "lakeflow_connect": ("native_passthrough", "databricks", "Lakeflow Connect is Databricks-specific; use native_passthrough for adapter-owned native connector handoff."),
    "mongodb": ("native_passthrough", None, _NATIVE_PASSTHROUGH_MESSAGE),
    "mongo": ("native_passthrough", None, _NATIVE_PASSTHROUGH_MESSAGE),
    "cosmos": ("native_passthrough", None, _NATIVE_PASSTHROUGH_MESSAGE),
    "cosmosdb": ("native_passthrough", None, _NATIVE_PASSTHROUGH_MESSAGE),
    "elasticsearch": ("native_passthrough", None, _NATIVE_PASSTHROUGH_MESSAGE),
    "elastic": ("native_passthrough", None, _NATIVE_PASSTHROUGH_MESSAGE),
    "sftp": ("native_passthrough", None, _NATIVE_PASSTHROUGH_MESSAGE),
    "ftp": ("native_passthrough", None, _NATIVE_PASSTHROUGH_MESSAGE),
    "imap": ("native_passthrough", None, _NATIVE_PASSTHROUGH_MESSAGE),
}


def connector_intent(name: str) -> ConnectorIntent:
    """Normalize a user-facing connector name to a core source type."""

    original = _normalize_name(name)
    connector, adapter, recommendation = _CONNECTOR_NORMALIZATION.get(original, (original, None, None))
    details = connector_details(connector)
    supported = connector in CONNECTOR_CATALOG
    final_recommendation = _support_recommendation(
        connector=connector,
        details=details,
        supported=supported,
        alias_recommendation=recommendation,
    )
    return ConnectorIntent(
        connector=connector,
        original=original,
        portability=str(details.get("portability") or "UNSUPPORTED"),
        display_name=_DISPLAY_NAMES.get(connector, connector.replace("_", " ").title()),
        family=details.get("family"),
        description=details.get("description"),
        required_fields=tuple(details.get("required") or ()),
        adapter=adapter or details.get("adapter"),
        recommendation=final_recommendation,
        supported_by_core=supported,
    )


def connector_details(name: str) -> dict[str, Any]:
    """Return core connector metadata for AI decisions."""

    return source_connector_details(name)


def supported_connector_names() -> tuple[str, ...]:
    """Return canonical source types supported by the ContractForge Core catalog."""

    return tuple(sorted(CONNECTOR_CATALOG))


def connector_aliases() -> dict[str, str]:
    """Return supported AI connector aliases and their canonical core source type."""

    direct = {name: name for name in CONNECTOR_CATALOG}
    aliases = {alias: target for alias, (target, _, _) in _CONNECTOR_NORMALIZATION.items()}
    return {**direct, **aliases}


def connector_message(name: str) -> str:
    """Return a deterministic user-facing message for a connector name."""

    return connector_intent(name).to_message()


def _support_recommendation(
    *,
    connector: str,
    details: dict[str, Any],
    supported: bool,
    alias_recommendation: str | None,
) -> str:
    support = (
        f"Supported by ContractForge Core as source type `{connector}`."
        if supported
        else "Unsupported by ContractForge Core."
    )
    catalog = _catalog_recommendation(connector, details)
    extras = [item for item in (alias_recommendation, catalog) if item]
    unique_extras = tuple(dict.fromkeys(extras))
    return " ".join((support, *unique_extras)).strip()


def _catalog_recommendation(connector: str, details: dict[str, Any]) -> str:
    if connector not in CONNECTOR_CATALOG:
        return "Unsupported by ContractForge Core; choose a core connector or native_passthrough."
    portability = str(details.get("portability") or "UNKNOWN")
    family = str(details.get("family") or "source")
    if portability == "PORTABLE_BUILTIN":
        return f"Supported by ContractForge Core as a portable {family} source."
    if portability == "BOUNDED_STREAM":
        return "Supported by ContractForge Core as bounded replay/catch-up, not continuous streaming."
    if portability == "AVAILABLE_NOW_STREAM":
        return "Supported by ContractForge Core as checkpointed available-now catch-up when the adapter supports it."
    if portability == "NATIVE_PASSTHROUGH":
        return _NATIVE_PASSTHROUGH_MESSAGE
    return "Unsupported by ContractForge Core; choose a core connector or native_passthrough."


def _normalize_name(name: str) -> str:
    return (
        str(name or "")
        .strip()
        .lower()
        .replace("/", "_")
        .replace(" ", "_")
        .replace("-", "_")
    )
