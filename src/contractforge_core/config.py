"""Platform-neutral constants and shared type aliases."""

from __future__ import annotations

from typing import Any, Literal, Union

FRAMEWORK_VERSION = "1.0.0"
CTRL_SCHEMA_VERSION = 1

Layer = str

WriteMode = Literal[
    "scd0_append",
    "scd0_overwrite",
    "scd1_upsert",
    "scd1_hash_diff",
    "scd2_historical",
    "snapshot_soft_delete",
    "append",
    "overwrite",
    "upsert",
    "merge_current",
    "hash_diff_upsert",
    "historical",
    "snapshot_reconcile_soft_delete",
]
WriteEngine = Literal[
    "auto",
    "core_managed",
    "native_merge",
    "native_cdc",
]
WriteEngineFallbackPolicy = Literal["fail", "fallback_to_core", "preview_only"]
SchemaPolicy = Literal["permissive", "additive_only", "strict"]
QualityFailAction = Literal["fail", "warn", "quarantine"]
QualityRuleSeverity = Literal["warn", "quarantine", "abort"]
SCD2LateArrivingPolicy = Literal["apply", "ignore", "reject"]
GovernanceFailurePolicy = Literal["fail", "warn", "ignore"]
AccessMode = Literal["apply", "validate_only", "ignore"]
AccessDriftPolicy = Literal["fail", "warn", "reconcile"]
IdempotencyPolicy = Literal["always_run", "skip_if_success", "fail_if_success", "rerun_if_failed"]
Source = Union[str, dict[str, Any]]

CUSTOM_WRITE_MODE_PREFIX = "custom:"

WRITE_MODE_ALIASES = {
    "append": "scd0_append",
    "overwrite": "scd0_overwrite",
    "upsert": "scd1_upsert",
    "merge_current": "scd1_upsert",
    "hash_diff_upsert": "scd1_hash_diff",
    "historical": "scd2_historical",
    "snapshot_reconcile_soft_delete": "snapshot_soft_delete",
}

PUBLIC_WRITE_MODES = tuple(WRITE_MODE_ALIASES)

PUBLIC_WRITE_MODE_BY_CANONICAL = {
    "scd0_append": "append",
    "scd0_overwrite": "overwrite",
    "scd1_upsert": "upsert",
    "scd1_hash_diff": "hash_diff_upsert",
    "scd2_historical": "historical",
    "snapshot_soft_delete": "snapshot_reconcile_soft_delete",
}

VALID_WRITE_MODES = {
    "scd0_append",
    "scd0_overwrite",
    "scd1_upsert",
    "scd1_hash_diff",
    "scd2_historical",
    "snapshot_soft_delete",
}
VALID_WRITE_ENGINES = {"auto", "core_managed", "native_merge", "native_cdc"}
VALID_WRITE_ENGINE_FALLBACK_POLICIES = {"fail", "fallback_to_core", "preview_only"}
VALID_SCHEMA_POLICIES = {"permissive", "additive_only", "strict"}
VALID_QUALITY_FAIL_ACTIONS = {"fail", "warn", "quarantine"}
VALID_QUALITY_RULE_SEVERITIES = {"warn", "quarantine", "abort"}
VALID_SCD2_LATE_ARRIVING_POLICIES = {"apply", "ignore", "reject"}
VALID_GOVERNANCE_FAILURE_POLICIES = {"fail", "warn", "ignore"}
VALID_ACCESS_MODES = {"apply", "validate_only", "ignore"}
VALID_ACCESS_DRIFT_POLICIES = {"fail", "warn", "reconcile"}
VALID_CRITICALITY_LEVELS = {"low", "medium", "high", "critical"}
VALID_EXPECTED_FREQUENCIES = {"hourly", "daily", "weekly", "monthly", "ad_hoc"}
VALID_SENSITIVITY_LEVELS = {"public", "internal", "restricted", "confidential"}
VALID_PII_TYPES = {
    "address",
    "bank_account",
    "birth_date",
    "credit_card",
    "device_id",
    "document",
    "email",
    "financial",
    "health",
    "ip_address",
    "name",
    "national_id",
    "other",
    "phone",
    "ssn",
    "tax_id",
    "unknown",
}
VALID_ACCESS_PRIVILEGES = {
    "ALL PRIVILEGES",
    "APPLY TAG",
    "CREATE",
    "CREATE FUNCTION",
    "CREATE MODEL",
    "CREATE TABLE",
    "CREATE VOLUME",
    "EXECUTE",
    "MANAGE",
    "MODIFY",
    "READ FILES",
    "READ VOLUME",
    "REFRESH",
    "SELECT",
    "USAGE",
    "WRITE FILES",
    "WRITE VOLUME",
}
VALID_IDEMPOTENCY_POLICIES = {"always_run", "skip_if_success", "fail_if_success", "rerun_if_failed"}
VALID_EXPLAIN_FORMATS = {"simple", "extended", "codegen", "cost", "formatted"}

VALID_SOURCE_TYPES = {"connector"}
VALID_SOURCE_CONNECTORS = {
    "adls",
    "avro",
    "azure_blob",
    "bigquery_jdbc",
    "blob",
    "csv",
    "custom_transform",
    "db2",
    "delta",
    "delta_share",
    "delta_table",
    "eventhubs_available_now",
    "eventhubs_bounded",
    "gcs",
    "http_csv",
    "http_file",
    "http_json",
    "http_text",
    "iceberg_table",
    "incremental_files",
    "jdbc",
    "json",
    "kafka_available_now",
    "kafka_bounded",
    "mariadb",
    "mysql",
    "native_passthrough",
    "object_storage",
    "oracle",
    "orc",
    "parquet",
    "postgres",
    "redshift",
    "rest_api",
    "s3",
    "snowflake_jdbc",
    "sql",
    "sqlserver",
    "table",
    "text",
    "view",
    "xml",
}
VALID_OBJECT_STORAGE_PROVIDERS = {"adls", "azure_blob", "gcs", "s3"}
VALID_FILE_CONNECTOR_FORMATS = {"avro", "csv", "delta", "json", "jsonl", "ndjson", "orc", "parquet", "text", "xml"}
VALID_HTTP_FILE_FORMATS = {"csv", "json", "jsonl", "ndjson", "text"}
VALID_SOURCE_TRIGGERS = {"available_now"}
ARRAY_MODES = {"explode", "explode_outer", "first", "keep", "size", "to_json"}
MAX_INLINE_ACCEPTED_VALUES = 1000
CONTROL_COLUMNS = {
    "ingestion_ts_utc",
    "__run_id",
    "row_hash",
    "valid_from",
    "valid_to",
    "is_current",
    "is_active",
    "deleted_at",
    "changed_columns",
}


def canonical_write_mode(value: str) -> str:
    normalized = str(value or "").strip()
    if normalized.startswith(CUSTOM_WRITE_MODE_PREFIX):
        return normalized
    alias_key = normalized.lower().replace("-", "_")
    return WRITE_MODE_ALIASES.get(alias_key, normalized)


def public_write_mode(value: str) -> str:
    canonical = canonical_write_mode(value)
    return PUBLIC_WRITE_MODE_BY_CANONICAL.get(canonical, canonical)


def is_valid_write_mode(value: str) -> bool:
    canonical = canonical_write_mode(value)
    return canonical in VALID_WRITE_MODES or canonical.startswith(CUSTOM_WRITE_MODE_PREFIX)
