from __future__ import annotations

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_fabric import can_render_quality_runtime, has_quality_rules, render_fabric_contract
from contractforge_fabric.quality import render_quality_gate_statement


def _contract() -> dict[str, object]:
    return {
        "source": {"type": "sql", "query": "SELECT 1 AS id, 'alpha' AS name, 10 AS amount"},
        "target": {"catalog": "workspace", "schema": "silver", "table": "orders"},
        "mode": "overwrite",
        "quality_rules": {
            "required_columns": ["id", "name"],
            "not_null": ["id"],
            "unique_key": ["id"],
            "min_rows": 1,
            "max_null_ratio": {"name": 0.2},
            "expressions": [{"name": "positive_amount", "expression": "amount > 0", "severity": "abort"}],
        },
    }


def test_fabric_quality_renderer_declares_supported_rules() -> None:
    semantic = semantic_contract_from_mapping(_contract())

    assert has_quality_rules(semantic) is True
    assert can_render_quality_runtime(semantic) is True

    block = render_quality_gate_statement(semantic)
    assert "_cf_quality_status = 'PASSED'" in block
    assert "_cf_rows_quarantined = 0" in block
    assert "_cf_required_columns = [\"id\", \"name\"]" in block
    assert "_cf_quality_id_not_null_failed_predicate = \"`id` IS NULL\"" in block
    assert "_cf_rows_quarantined += _cf_quality_id_not_null_failed_count" in block
    assert "_cf_quality_unique_key_duplicate_groups = (" in block
    assert "_cf_quality_min_rows_failed_count = 1 if _cf_quality_min_rows_row_count < 1 else 0" in block
    assert "_cf_quality_name_max_null_ratio_ratio" in block
    assert "NOT (amount > 0) OR (amount > 0) IS NULL" in block
    assert "_cf_add_quality_result(\"id_not_null\"" in block
    assert "_cf_record_quarantine_evidence(\"id_not_null\", _cf_quality_id_not_null_failed, _cf_quality_id_not_null_failed_predicate)" in block
    assert "_cf_add_quality_result(\"unique_key\"" in block
    assert "_cf_add_quality_result(\"min_rows\"" in block


def test_fabric_notebook_places_quality_before_write() -> None:
    artifacts = render_fabric_contract(_contract()).artifacts
    notebook = artifacts["workspace_silver_orders.fabric.notebook.py"]

    source_pos = notebook.index('df = spark.sql("SELECT 1 AS id')
    quality_pos = notebook.index("# ContractForge quality gates.")
    write_pos = notebook.index('df.write.format("delta").mode("overwrite").saveAsTable(TARGET_TABLE)')

    assert source_pos < quality_pos < write_pos
    assert "'ctrl_ingestion_quality'" in notebook
    assert "'ctrl_ingestion_quarantine'" in notebook
    assert "_cf_record_quality_evidence()" in notebook


def test_fabric_quality_renderer_handles_no_rules() -> None:
    semantic = semantic_contract_from_mapping(
        {
            "source": {"type": "sql", "query": "SELECT 1 AS id"},
            "target": {"schema": "bronze", "table": "orders"},
            "mode": "append",
        }
    )

    assert has_quality_rules(semantic) is False
    assert "Quality rules: not configured." in render_quality_gate_statement(semantic)
