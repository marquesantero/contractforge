"""Snowflake evidence helpers."""

from contractforge_snowflake.evidence.ddl import render_create_evidence_tables_sql, render_create_state_tables_sql
from contractforge_snowflake.evidence.deployment import render_deployment_ledger_insert_sql
from contractforge_snowflake.evidence.writer import (
    SnowflakeEvidenceResult,
    bootstrap_evidence_tables,
    record_access_evidence,
    record_annotation_evidence,
    record_error_evidence,
    record_explain_evidence,
    record_lineage_evidence,
    record_operations_evidence,
    record_quality_evidence,
    record_quarantine_evidence,
    record_schema_change_evidence,
    record_run_evidence,
)

__all__ = [
    "SnowflakeEvidenceResult",
    "bootstrap_evidence_tables",
    "record_access_evidence",
    "record_annotation_evidence",
    "record_error_evidence",
    "record_explain_evidence",
    "record_lineage_evidence",
    "record_operations_evidence",
    "record_quality_evidence",
    "record_quarantine_evidence",
    "record_schema_change_evidence",
    "record_run_evidence",
    "render_create_evidence_tables_sql",
    "render_create_state_tables_sql",
    "render_deployment_ledger_insert_sql",
]
