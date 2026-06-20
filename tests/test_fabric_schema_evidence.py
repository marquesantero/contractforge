from __future__ import annotations

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_fabric.evidence import render_notebook_evidence_setup
from contractforge_fabric import render_fabric_contract


def _contract() -> dict[str, object]:
    return {
        "source": {"type": "sql", "query": "SELECT 1 AS id, 'alpha' AS name"},
        "target": {"catalog": "workspace", "schema": "silver", "table": "orders"},
        "mode": "overwrite",
    }


def test_fabric_notebook_schema_evidence_helper_records_observed_schema() -> None:
    contract = semantic_contract_from_mapping(_contract())
    block = render_notebook_evidence_setup(contract)

    assert "_CF_SCHEMA_POLICY = \"permissive\"" in block
    assert "_CF_ALLOW_TYPE_WIDENING = False" in block
    assert "def _cf_validate_schema_policy(dataframe=None):" in block
    assert "def _cf_schema_diff(source_schema, target_schema):" in block
    assert "def _cf_record_schema_change_evidence(dataframe=None):" in block
    assert "'ctrl_ingestion_schema_changes'" in block
    assert "changes['change_type'] = 'SCHEMA_POLICY'" in block
    assert "'schema_after': schema_after" in block
    assert "'schema_policy': _CF_SCHEMA_POLICY" in block
    assert "'status': 'observed_only'" in block
    assert "'payload_json': json.dumps(_cf_schema_changes, sort_keys=True, separators=(',', ':'))" in block


def test_fabric_notebook_schema_evidence_is_generated_before_run_evidence() -> None:
    notebook = render_fabric_contract(_contract()).artifacts["workspace_silver_orders.fabric.notebook.py"]

    compile(notebook, "workspace_silver_orders.fabric.notebook.py", "exec")
    validate_pos = notebook.index("    _cf_validate_schema_policy(dataframe=df)")
    write_pos = notebook.index('    df.write.format("delta").mode("overwrite").saveAsTable(TARGET_TABLE)')
    schema_pos = notebook.index("    _cf_record_schema_change_evidence(dataframe=df)")
    metadata_pos = notebook.index("    _cf_record_source_metadata_evidence(dataframe=df)")
    run_pos = notebook.index("    _cf_record_run_evidence('SUCCESS')")

    assert validate_pos < write_pos < schema_pos < metadata_pos < run_pos


def test_fabric_schema_policy_renders_strict_and_type_widening_options() -> None:
    notebook = render_fabric_contract(
        {
            **_contract(),
            "schema_policy": "strict",
            "extensions": {"fabric": {"allow_type_widening": True}},
        }
    ).artifacts["workspace_silver_orders.fabric.notebook.py"]

    compile(notebook, "workspace_silver_orders.fabric.notebook.py", "exec")
    assert "_CF_SCHEMA_POLICY = \"strict\"" in notebook
    assert "_CF_ALLOW_TYPE_WIDENING = True" in notebook
    assert "Schema policy strict violation" in notebook
    assert "Schema policy additive_only violation" in notebook
    assert "Schema policy permissive violation" in notebook
    assert "'schema_policy': _CF_SCHEMA_POLICY" in notebook
