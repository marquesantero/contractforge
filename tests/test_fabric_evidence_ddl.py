from __future__ import annotations

import pytest

from contractforge_fabric.evidence import (
    evidence_table_names,
    render_create_evidence_tables_sql,
    render_evidence_table_notes,
)
from contractforge_fabric.state import render_create_state_tables_sql, state_table_names


def test_fabric_evidence_ddl_renders_core_delta_tables() -> None:
    sql = render_create_evidence_tables_sql(schema="contractforge")

    assert "CREATE SCHEMA IF NOT EXISTS `contractforge`;" in sql
    assert "CREATE TABLE IF NOT EXISTS `contractforge`.`ctrl_ingestion_runs`" in sql
    assert "`run_id` STRING" in sql
    assert "`rows_written` BIGINT" in sql
    assert "USING DELTA PARTITIONED BY (`run_date`);" in sql
    assert "CREATE TABLE IF NOT EXISTS `contractforge`.`ctrl_ingestion_quality`" in sql
    assert "CREATE TABLE IF NOT EXISTS `contractforge`.`ctrl_ingestion_lineage`" in sql
    assert "CREATE TABLE IF NOT EXISTS `contractforge`.`ctrl_ingestion_access`" in sql


def test_fabric_state_ddl_renders_state_and_lock_tables() -> None:
    sql = render_create_state_tables_sql(schema="contractforge")

    assert "CREATE SCHEMA IF NOT EXISTS `contractforge`;" in sql
    assert "CREATE TABLE IF NOT EXISTS `contractforge`.`ctrl_ingestion_state`" in sql
    assert "`target_table` STRING NOT NULL" in sql
    assert "CREATE TABLE IF NOT EXISTS `contractforge`.`ctrl_ingestion_locks`" in sql
    assert "`expires_at_utc` TIMESTAMP" in sql


def test_fabric_evidence_table_names_are_schema_scoped() -> None:
    assert evidence_table_names("ops")["runs"] == "ops.ctrl_ingestion_runs"
    assert state_table_names("ops")["locks"] == "ops.ctrl_ingestion_locks"


def test_fabric_evidence_notes_include_lakehouse_and_state_tables() -> None:
    notes = render_evidence_table_notes(lakehouse="contractforge_lh", schema="ops")

    assert "-- Lakehouse/schema target: contractforge_lh.ops" in notes
    assert "-- runs: ops.ctrl_ingestion_runs" in notes
    assert "-- locks: ops.ctrl_ingestion_locks" in notes


def test_fabric_evidence_ddl_rejects_empty_schema() -> None:
    with pytest.raises(ValueError, match="identifier must not be empty"):
        render_create_evidence_tables_sql(schema="")
