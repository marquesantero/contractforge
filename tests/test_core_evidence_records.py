from datetime import datetime

from contractforge_core.evidence import (
    EVIDENCE_TABLE_COLUMNS,
    EVIDENCE_TABLES,
    STATE_TABLE_COLUMNS,
    STATE_TABLES,
    RunEvidenceRecord,
    SourceMetadataEvidenceRecord,
)


def test_core_run_evidence_record_carries_metrics() -> None:
    record = RunEvidenceRecord(
        run_id="run-1",
        target_table="main.silver.orders",
        mode="scd1_upsert",
        status="SUCCESS",
        started_at_utc=datetime(2026, 1, 1, 12, 0, 0),
        metrics={"rows_written": 10},
    )

    assert record.metrics == {"rows_written": 10}
    assert record.finished_at_utc is None


def test_core_source_metadata_evidence_record() -> None:
    record = SourceMetadataEvidenceRecord(
        run_id="run-1",
        target_table="main.silver.orders",
        source_metadata={"source_type": "jdbc"},
        captured_at_utc=datetime(2026, 1, 1, 12, 0, 0),
    )

    assert record.source_metadata["source_type"] == "jdbc"


def test_core_owns_control_table_contract() -> None:
    assert EVIDENCE_TABLES["runs"] == "ctrl_ingestion_runs"
    assert EVIDENCE_TABLES["metadata"] == "ctrl_ingestion_metadata"
    assert EVIDENCE_TABLES["deployments"] == "ctrl_deployment_versions"
    assert STATE_TABLES["state"] == "ctrl_ingestion_state"
    assert "source_system STRING" in EVIDENCE_TABLE_COLUMNS["runs"]
    assert "error_class STRING" in EVIDENCE_TABLE_COLUMNS["errors"]
    assert "source_metadata_json STRING" in EVIDENCE_TABLE_COLUMNS["metadata"]
    assert "deployment_id STRING NOT NULL" in EVIDENCE_TABLE_COLUMNS["deployments"]
    assert "deployment_hash STRING NOT NULL" in EVIDENCE_TABLE_COLUMNS["deployments"]
    assert "contract_hash STRING" in EVIDENCE_TABLE_COLUMNS["deployments"]
    assert "last_table_version STRING" in STATE_TABLE_COLUMNS["state"]
