from pathlib import Path

from contractforge_databricks.evidence.tables import EVIDENCE_TABLES
from contractforge_databricks.state.tables import STATE_TABLES


ROOT = Path(__file__).resolve().parents[1]


def test_control_table_parity_doc_mentions_adapter_tables() -> None:
    doc = (ROOT / "docs" / "specs" / "control-table-parity.md").read_text(encoding="utf-8")
    tables = set(EVIDENCE_TABLES.values()) | set(STATE_TABLES.values()) | {"ctrl_ingestion_explain"}

    missing = sorted(table for table in tables if table not in doc)

    assert missing == []


def test_control_table_parity_doc_mentions_key_current_columns() -> None:
    doc = (ROOT / "docs" / "specs" / "control-table-parity.md").read_text(encoding="utf-8")
    columns = {
        "write_engine_selected",
        "source_capabilities_json",
        "source_system",
        "source.system",
        "rows_expired",
        "idempotency_key",
        "historical",
        "revoke_unmanaged",
        "freshness_sla_minutes",
        "last_watermark_candidate",
    }

    missing = sorted(column for column in columns if column not in doc)

    assert missing == []
