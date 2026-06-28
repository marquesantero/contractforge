"""Platform-neutral source connector catalog metadata."""

from __future__ import annotations

from typing import Any

FILE_FORMATS = ("avro", "csv", "delta", "json", "jsonl", "ndjson", "orc", "parquet", "text", "xml")
HTTP_FILE_LIMITS = ("timeout_seconds", "retry_attempts", "retry_backoff_seconds", "max_bytes", "max_records")
JDBC_LIMITS = ("read.fetchsize", "read.partition_column", "read.lower_bound", "read.upper_bound", "read.num_partitions")

CONNECTOR_CATALOG: dict[str, dict[str, Any]] = {
    "table": {"family": "catalog", "description": "Registered lakehouse table.", "required_any_of": [["table"], ["path"]]},
    "delta_table": {"family": "catalog", "description": "Registered or path-based Delta table.", "required_any_of": [["table"], ["path"]]},
    "iceberg_table": {"family": "catalog", "description": "Registered Iceberg table.", "required_any_of": [["table"], ["path"]]},
    "view": {"family": "catalog", "description": "Registered lakehouse view.", "required_any_of": [["table"], ["path"]]},
    "sql": {"family": "catalog", "description": "Declarative SQL source query.", "required_any_of": [["query"], ["options.query"]]},
    "csv": {"family": "files", "description": "Batch CSV files.", "required": ["path"], "supported_formats": ["csv"]},
    "json": {"family": "files", "description": "Batch JSON files.", "required": ["path"], "supported_formats": ["json"]},
    "jsonl": {"family": "files", "description": "Batch JSON Lines files.", "required": ["path"], "supported_formats": ["jsonl", "ndjson"]},
    "ndjson": {"family": "files", "description": "Batch newline-delimited JSON files.", "required": ["path"], "supported_formats": ["jsonl", "ndjson"]},
    "parquet": {"family": "files", "description": "Batch Parquet files.", "required": ["path"], "supported_formats": ["parquet"]},
    "delta": {"family": "files", "description": "Path-based Delta files.", "required": ["path"], "supported_formats": ["delta"]},
    "orc": {"family": "files", "description": "Batch ORC files.", "required": ["path"], "supported_formats": ["orc"]},
    "text": {"family": "files", "description": "Batch text files.", "required": ["path"], "supported_formats": ["text"]},
    "avro": {"family": "files", "description": "Batch Avro files.", "required": ["path"], "supported_formats": ["avro"]},
    "xml": {"family": "files", "description": "Batch XML files.", "required": ["path"], "supported_formats": ["xml"], "runtime_notes": ["XML parser options such as row tags are adapter/runtime specific and should be declared in source.options."]},
    "s3": {"family": "object_storage", "description": "Amazon S3 files.", "required": ["format", "path"], "auth_modes": ["runtime_identity", "access_key"], "supported_formats": FILE_FORMATS, "providers": ["aws"]},
    "adls": {"family": "object_storage", "description": "Azure Data Lake Storage files.", "required": ["format", "path"], "auth_modes": ["runtime_identity"], "supported_formats": FILE_FORMATS, "providers": ["azure"]},
    "azure_blob": {
        "family": "object_storage",
        "description": "Azure Blob Storage files.",
        "required": ["format", "path"],
        "auth_modes": ["runtime_identity", "sas_token"],
        "supported_formats": FILE_FORMATS,
        "providers": ["azure"],
        "conditional_required": [{"when": "auth.sas_token with a relative path", "requires": ["account_url", "container"]}],
        "recommended_usage": "Prefer governed external locations/volumes when available; direct SAS is runtime configuration.",
    },
    "gcs": {"family": "object_storage", "description": "Google Cloud Storage files.", "required": ["format", "path"], "auth_modes": ["runtime_identity"], "supported_formats": FILE_FORMATS, "providers": ["gcp"]},
    "blob": {"family": "object_storage", "description": "Generic blob/object storage files.", "required": ["provider", "format", "path"], "supported_formats": FILE_FORMATS, "providers": ["adls", "azure_blob", "gcs", "s3"]},
    "object_storage": {"family": "object_storage", "description": "Provider-neutral object storage files.", "required": ["provider", "format", "path"], "supported_formats": FILE_FORMATS, "providers": ["adls", "azure_blob", "gcs", "s3"]},
    "connection": {"family": "connection_reference", "description": "Reference to an external connection YAML resolved by the bundle loader.", "required": ["connection_path"], "runtime": "Resolved by the core before adapter planning; not a runtime source type."},
    "custom_transform": {
        "family": "custom_transform",
        "description": "Declared custom treatment boundary for complex transformations with named inputs and adapter-native execution.",
        "required": ["inputs"],
        "runtime": "The core validates intent, inputs and downstream contract semantics; adapters render the native execution artifact such as a notebook or task.",
        "recommended_usage": "Use when declarative shape/cast/derive/deduplicate cannot express the treatment and the implementation still needs contract-managed validation and evidence.",
    },
    "incremental_files": {"family": "incremental_files", "description": "Checkpointed new-file discovery intent.", "required": ["path", "format"], "incremental": True, "supported_formats": FILE_FORMATS, "recommended_usage": "Adapters map this to their native incremental new-file discovery mechanism."},
    "http_file": {"family": "http_files", "description": "Bounded HTTP(S) file fetch.", "required": ["request.url", "format"], "runtime": "Adapter-owned bounded HTTP fetch materialized by each platform's native runtime.", "auth_modes": ["none", "bearer_token", "api_key", "basic"], "supported_formats": ["csv", "json", "jsonl", "ndjson", "text"], "limits": HTTP_FILE_LIMITS},
    "http_csv": {"family": "http_files", "description": "Bounded HTTP(S) CSV file fetch.", "required": ["request.url"], "runtime": "Adapter-owned bounded HTTP fetch; format fixed to csv.", "auth_modes": ["none", "bearer_token", "api_key", "basic"], "supported_formats": ["csv"], "limits": HTTP_FILE_LIMITS},
    "http_json": {"family": "http_files", "description": "Bounded HTTP(S) JSON file fetch.", "required": ["request.url"], "runtime": "Adapter-owned bounded HTTP fetch; format fixed to json.", "auth_modes": ["none", "bearer_token", "api_key", "basic"], "supported_formats": ["json"], "limits": HTTP_FILE_LIMITS},
    "http_text": {"family": "http_files", "description": "Bounded HTTP(S) text file fetch.", "required": ["request.url"], "runtime": "Adapter-owned bounded HTTP fetch; format fixed to text.", "auth_modes": ["none", "bearer_token", "api_key", "basic"], "supported_formats": ["text"], "limits": HTTP_FILE_LIMITS},
    "jdbc": {"family": "jdbc", "description": "Generic JDBC batch source.", "required": ["url"], "required_any_of": [["table"], ["query"], ["options.dbtable"], ["options.query"]], "incremental": True, "auth_modes": ["none", "basic", "rds_iam"], "limits": JDBC_LIMITS},
    "postgres": {"family": "jdbc", "description": "PostgreSQL JDBC source.", "required": ["url"], "incremental": True, "auth_modes": ["none", "basic", "rds_iam"], "limits": JDBC_LIMITS},
    "mysql": {"family": "jdbc", "description": "MySQL JDBC source.", "required": ["url"], "incremental": True, "auth_modes": ["none", "basic"], "limits": JDBC_LIMITS},
    "mariadb": {"family": "jdbc", "description": "MariaDB JDBC source.", "required": ["url"], "incremental": True, "auth_modes": ["none", "basic"], "limits": JDBC_LIMITS},
    "sqlserver": {"family": "jdbc", "description": "Microsoft SQL Server JDBC source.", "required": ["url"], "incremental": True, "auth_modes": ["none", "basic"], "limits": JDBC_LIMITS},
    "oracle": {"family": "jdbc", "description": "Oracle JDBC source. The runtime must provide the Oracle JDBC driver.", "required": ["url"], "incremental": True, "auth_modes": ["none", "basic"], "limits": JDBC_LIMITS, "runtime_notes": ["Do not redistribute the Oracle JDBC driver; require users to provide it in the target runtime."]},
    "redshift": {"family": "jdbc", "description": "Amazon Redshift JDBC source.", "required": ["url"], "incremental": True, "auth_modes": ["none", "basic"], "limits": JDBC_LIMITS},
    "db2": {"family": "jdbc", "description": "IBM Db2 JDBC source.", "required": ["url"], "incremental": True, "auth_modes": ["none", "basic"], "limits": JDBC_LIMITS},
    "snowflake_jdbc": {"family": "jdbc", "description": "Snowflake JDBC source.", "required": ["url"], "incremental": True, "auth_modes": ["none", "basic"], "limits": JDBC_LIMITS},
    "bigquery_jdbc": {"family": "jdbc", "description": "BigQuery JDBC source.", "required": ["url"], "incremental": True, "auth_modes": ["none", "basic", "oauth"], "limits": JDBC_LIMITS},
    "kafka_bounded": {"family": "bounded_stream", "description": "Kafka bounded replay source, not continuous streaming.", "required": ["bootstrap_servers", "topic"], "incremental": True, "limits": ["starting_offsets", "ending_offsets", "max_offsets_per_trigger"]},
    "eventhubs_bounded": {"family": "bounded_stream", "description": "Azure Event Hubs bounded replay source, not continuous streaming.", "required": ["connection_string", "event_hub_name"], "incremental": True, "limits": ["starting_position", "ending_position", "max_events_per_trigger"]},
    "kafka_available_now": {"family": "available_now_stream", "description": "Kafka readStream with availableNow trigger and checkpoint-driven progress.", "required": ["bootstrap_servers", "topic", "checkpoint_location"], "incremental": True, "limits": ["starting_offsets", "max_offsets_per_trigger"]},
    "eventhubs_available_now": {"family": "available_now_stream", "description": "Azure Event Hubs readStream with availableNow trigger and checkpoint-driven progress.", "required": ["connection_string", "event_hub_name", "checkpoint_location"], "incremental": True, "limits": ["starting_position", "max_events_per_trigger"]},
    "delta_share": {"family": "sharing", "description": "Delta Sharing consumer source.", "required": ["profile_file", "table"]},
    "rest_api": {"family": "api", "description": "Generic bounded REST API connector for simple JSON pulls.", "required": ["request.url"], "runtime": "Adapter-owned bounded REST client; use native_passthrough for specialized SaaS/vendor APIs.", "incremental": True, "auth_modes": ["none", "basic", "bearer_token", "api_key", "oauth_client_credentials"], "limits": ["page_size", "max_pages", "max_records", "max_page_bytes", "max_total_bytes", "rate_limit_per_minute", "timeout_seconds", "retry_attempts", "retry_backoff_seconds"], "recommended_usage": "Use for bounded generic REST reads. For specialized SaaS or vendor APIs, prefer the platform/vendor native connector, then govern landed data with ContractForge."},
    "native_passthrough": {"family": "native_passthrough", "description": "Adapter-owned native connector handoff for SaaS and platform-specific systems.", "required": ["system"], "runtime": "Adapter-owned native platform connector.", "recommended_usage": "Use when a target platform has a better native connector than a portable core implementation."},
}


def connector_catalog_entry(name: str) -> dict[str, Any]:
    return dict(CONNECTOR_CATALOG.get(str(name or "").strip().lower(), {}))
