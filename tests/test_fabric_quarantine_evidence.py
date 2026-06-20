from __future__ import annotations

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_fabric.evidence import render_notebook_evidence_setup
from contractforge_fabric.quality import render_quality_gate_statement
from contractforge_fabric import render_fabric_contract


def _contract() -> dict[str, object]:
    return {
        "source": {"type": "sql", "query": "SELECT 1 AS id, NULL AS name"},
        "target": {"catalog": "workspace", "schema": "silver", "table": "orders"},
        "mode": "overwrite",
        "quality_rules": {"not_null": ["name"]},
    }


def test_fabric_quarantine_evidence_helper_writes_failed_row_payloads() -> None:
    contract = semantic_contract_from_mapping(_contract())
    block = render_notebook_evidence_setup(contract)

    assert "def _cf_record_quarantine_evidence(rule_name, failed_dataframe, reason):" in block
    assert "'ctrl_ingestion_quarantine'" in block
    assert "for row in failed_dataframe.toJSON().collect():" in block
    assert "'record_payload': row" in block
    assert "'quarantined_at_utc': quarantined_at" in block


def test_fabric_quarantine_rule_records_before_filtering_rows() -> None:
    contract = semantic_contract_from_mapping(_contract())
    block = render_quality_gate_statement(contract)

    record_pos = block.index("_cf_record_quarantine_evidence(\"name_not_null\", _cf_quality_name_not_null_failed")
    filter_pos = block.index("df = df.filter('NOT (' + _cf_quality_name_not_null_failed_predicate + ')')")

    assert record_pos < filter_pos


def test_fabric_generated_notebook_compiles_with_quarantine_evidence() -> None:
    notebook = render_fabric_contract(_contract()).artifacts["workspace_silver_orders.fabric.notebook.py"]

    compile(notebook, "workspace_silver_orders.fabric.notebook.py", "exec")
    assert "_cf_record_quarantine_evidence(\"name_not_null\", _cf_quality_name_not_null_failed" in notebook
