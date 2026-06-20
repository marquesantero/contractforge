from __future__ import annotations

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_fabric import render_fabric_contract
from contractforge_fabric.evidence import render_notebook_evidence_setup


def _contract() -> dict[str, object]:
    return {
        "source": {"type": "sql", "query": "SELECT 1 AS id, 'alpha' AS name"},
        "target": {"catalog": "workspace", "schema": "silver", "table": "orders"},
        "mode": "overwrite",
    }


def test_fabric_notebook_explain_helper_records_spark_plan() -> None:
    contract = semantic_contract_from_mapping(_contract())
    block = render_notebook_evidence_setup(contract)

    assert "def _cf_record_explain_evidence(dataframe=None):" in block
    assert "'ctrl_ingestion_explain'" in block
    assert "dataframe._jdf.queryExecution().toString()" in block
    assert "'explain_format': 'spark_query_execution'" in block
    assert "'plan_text': plan_text" in block


def test_fabric_notebook_explain_evidence_is_before_lineage() -> None:
    notebook = render_fabric_contract(_contract()).artifacts["workspace_silver_orders.fabric.notebook.py"]

    compile(notebook, "workspace_silver_orders.fabric.notebook.py", "exec")
    explain_pos = notebook.index("    _cf_record_explain_evidence(dataframe=df)")
    lineage_pos = notebook.index("    _cf_record_lineage_evidence(input_dataframe=df, output_dataframe=df, status='SUCCESS')")

    assert explain_pos < lineage_pos
