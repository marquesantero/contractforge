from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_databricks_contractforge_parity_tracks_core_capabilities_and_gaps() -> None:
    doc = (ROOT / "docs" / "specs" / "databricks-contractforge-parity.md").read_text(encoding="utf-8")
    required = {
        "current-state Delta MERGE",
        "hash-diff upsert",
        "Historical",
        "Snapshot soft delete",
        "Lakeflow AUTO CDC compatibility",
        "Control/evidence table DDL",
        "Full run ledger logging",
        "State, idempotency and locks",
        "Execution windows/catchup planning",
        "Runtime end-to-end `ingest_plan` equivalent",
        "CLI commands",
        "Template catalog/presets",
        "Dashboard blueprint",
    }

    missing = sorted(item for item in required if item not in doc)

    assert missing == []


def test_databricks_contractforge_parity_has_explicit_non_ported_statuses() -> None:
    doc = (ROOT / "docs" / "specs" / "databricks-contractforge-parity.md").read_text(encoding="utf-8")

    assert "PORT_IN_PROGRESS" in doc
    assert "NOT_PORTED_YET" in doc
    assert "No capability should be silently dropped" in doc


def test_databricks_contractforge_parity_records_source_audit_gaps() -> None:
    doc = (ROOT / "docs" / "specs" / "databricks-contractforge-parity.md").read_text(encoding="utf-8")
    required = {
        "Source Code Audit Against Databricks adapter baseline",
        "CLI validation and project discovery",
        "CLI contract initialization",
        "CLI connector registry/doctor",
        "CLI governance preview/check/apply",
        "Runtime source resolver execution",
        "REST API driver client and pagination execution",
        "Programmatic ingestion hooks",
        "Custom PySpark quality rule registry",
        "Executable shape/transform PySpark parity",
        "Spark utility conveniences",
    }

    missing = sorted(item for item in required if item not in doc)

    assert missing == []


def test_databricks_reference_adr_locks_core_adapter_boundary() -> None:
    doc = (ROOT / "docs" / "adrs" / "ADR-002-databricks-reference-adapter.md").read_text(
        encoding="utf-8"
    )
    required = {
        "semantic contracts for ingestion, annotations, operations, access and environment",
        "abstract execution plans and write strategy records",
        "Delta MERGE, SCD, hash-diff, snapshot, append and overwrite execution helpers",
        "Auto Loader/cloudFiles rendering for portable `incremental_files`",
        "Lakeflow AUTO CDC and Lakeflow Connect compatibility artifacts",
        "Databricks system-table, Delta history and DBU/cost evidence extraction",
        "The core must not import `contractforge_databricks`, Spark, Databricks SDK",
        "Runtime helpers may accept injected SQL/Spark runners",
        "no supported ContractForge write mode may silently degrade to another mode",
    }

    missing = sorted(item for item in required if item not in doc)

    assert missing == []
