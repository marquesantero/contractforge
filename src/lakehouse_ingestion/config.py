"""Configuração global e tipos compartilhados."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Union

from pyspark.sql import DataFrame

Layer = Literal["bronze", "silver", "gold"]
WriteMode = Literal[
    "scd0_append",
    "scd0_overwrite",
    "scd1_upsert",
    "scd1_hash_diff",
    "scd2_historical",
    "snapshot_soft_delete",
]
MergeStrategy = Literal["delta", "delta_by_partition", "replace_partitions"]
SchemaPolicy = Literal["permissive", "additive_only", "strict"]
QualityFailAction = Literal["fail", "warn", "quarantine"]
Source = Union[str, DataFrame]

VALID_WRITE_MODES = {
    "scd0_append",
    "scd0_overwrite",
    "scd1_upsert",
    "scd1_hash_diff",
    "scd2_historical",
    "snapshot_soft_delete",
}

CONTROL_COLUMNS = {
    "ingestion_date",
    "source_system",
    "__run_id",
    "row_hash",
    "valid_from",
    "valid_to",
    "is_current",
    "is_active",
    "deleted_at",
    "changed_columns",
}


@dataclass(frozen=True)
class FrameworkConfig:
    """Configuração global do framework."""

    default_catalog: str = "main"
    default_source_system: str = "default"
    default_partition_col: str = "ingestion_date"
    ctrl_schema: str = "ops"
    ctrl_table_runs: str = "ctrl_ingestion_runs"
    ctrl_table_state: str = "ctrl_ingestion_state"
    ctrl_table_quality: str = "ctrl_ingestion_quality"
    ctrl_table_quarantine: str = "ctrl_ingestion_quarantine"
    ctrl_table_locks: str = "ctrl_ingestion_locks"
    ctrl_table_explain: str = "ctrl_ingestion_explain"
    ctrl_table_lineage: str = "ctrl_ingestion_lineage"
    max_error_len: int = 8000
    default_lock_ttl_minutes: int = 120
    default_retry_attempts: int = 3
    default_retry_backoff_seconds: int = 5
    max_inline_accepted_values: int = 1000
    max_partition_predicate_values: int = 1000


CONFIG = FrameworkConfig()
