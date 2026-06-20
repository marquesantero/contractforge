from __future__ import annotations

import json

from contractforge_fabric import plan_fabric_contract, render_fabric_contract


def _contract(**overrides: object) -> dict[str, object]:
    contract: dict[str, object] = {
        "source": {
            "type": "sql",
            "query": "SELECT 1 AS id, 'alpha' AS name",
            "read": {"source_complete": True},
        },
        "target": {"catalog": "workspace", "schema": "silver", "table": "customers_snapshot"},
        "mode": "snapshot_reconcile_soft_delete",
        "merge_keys": ["id"],
    }
    contract.update(overrides)
    return contract


def test_fabric_plan_supports_snapshot_soft_delete_when_source_is_complete() -> None:
    result = plan_fabric_contract(_contract())

    assert result.status == "SUPPORTED_WITH_WARNINGS"
    assert result.plan is not None
    assert not result.blockers


def test_fabric_plan_blocks_snapshot_without_complete_source_declaration() -> None:
    contract = _contract(source={"type": "sql", "query": "SELECT 1 AS id, 'alpha' AS name"})

    result = plan_fabric_contract(contract)

    assert result.status == "UNSUPPORTED"
    assert [blocker.code for blocker in result.blockers] == ["SNAPSHOT_SOURCE_COMPLETE_REQUIRED"]


def test_fabric_notebook_renders_snapshot_soft_delete_merge() -> None:
    notebook = render_fabric_contract(_contract()).artifacts["workspace_silver_customers_snapshot.fabric.notebook.py"]

    compile(notebook, "workspace_silver_customers_snapshot.fabric.notebook.py", "exec")
    assert "MERGE_KEYS = [\"id\"]" in notebook
    assert "ROW_HASH_COLUMN = 'row_hash'" in notebook
    assert "IS_ACTIVE_COLUMN = 'is_active'" in notebook
    assert "DELETED_AT_COLUMN = 'deleted_at'" in notebook
    assert "snapshot_hash_input_columns = [column for column in df.columns if column not in snapshot_hash_excluded]" in notebook
    assert "df = df.withColumn(IS_ACTIVE_COLUMN, F.lit(True))" in notebook
    assert "df = df.withColumn(DELETED_AT_COLUMN, F.lit(None).cast('timestamp'))" in notebook
    assert "WHEN NOT MATCHED BY SOURCE AND target.{is_active_identifier} = true THEN UPDATE SET" in notebook
    assert "target.{is_active_identifier} = false" in notebook
    assert "target.{deleted_at_identifier} = current_timestamp()" in notebook
    assert "DELETE FROM" not in notebook

    schema_pos = notebook.index("    _cf_validate_schema_policy(dataframe=df)")
    snapshot_pos = notebook.index("    # Stage a complete source snapshot with soft-delete metadata.")
    metric_pos = notebook.index("    _cf_rows_written = df.count()")
    assert schema_pos < snapshot_pos < metric_pos


def test_fabric_capabilities_report_snapshot_soft_delete_supported() -> None:
    artifacts = render_fabric_contract(_contract()).artifacts
    capabilities = json.loads(artifacts["workspace_silver_customers_snapshot.fabric.capabilities.json"])

    assert capabilities["supports"]["snapshot_reconcile_soft_delete"] is True
    assert "snapshot_reconcile_soft_delete" not in capabilities["review_required_semantics"]
