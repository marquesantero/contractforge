from __future__ import annotations

import json

from contractforge_fabric import plan_fabric_contract, render_fabric_contract


def _contract(**overrides: object) -> dict[str, object]:
    contract: dict[str, object] = {
        "source": {"type": "sql", "query": "SELECT 1 AS id, 'alpha' AS name"},
        "target": {"catalog": "workspace", "schema": "silver", "table": "customers_history"},
        "mode": "historical",
        "merge_keys": ["id"],
        "scd2_change_columns": ["name"],
    }
    contract.update(overrides)
    return contract


def test_fabric_plan_supports_historical_with_runtime_warning() -> None:
    result = plan_fabric_contract(_contract())

    assert result.status == "SUPPORTED_WITH_WARNINGS"
    assert result.plan is not None
    assert not result.blockers


def test_fabric_notebook_renders_historical_scd2_merge() -> None:
    notebook = render_fabric_contract(_contract()).artifacts["workspace_silver_customers_history.fabric.notebook.py"]

    compile(notebook, "workspace_silver_customers_history.fabric.notebook.py", "exec")
    assert "MERGE_KEYS = [\"id\"]" in notebook
    assert "SCD2_CHANGE_COLUMNS = [\"name\"]" in notebook
    assert "ROW_HASH_COLUMN = 'row_hash'" in notebook
    assert "VALID_FROM_COLUMN = 'valid_from'" in notebook
    assert "VALID_TO_COLUMN = 'valid_to'" in notebook
    assert "IS_CURRENT_COLUMN = 'is_current'" in notebook
    assert "CHANGED_COLUMNS_COLUMN = 'changed_columns'" in notebook
    assert "# Stage source rows for SCD2 historical merge." in notebook
    assert "df = df.withColumn(ROW_HASH_COLUMN, F.sha2(F.concat_ws('\\x1f', *scd2_hash_payload), 256))" in notebook
    assert "CREATE OR REPLACE TEMP VIEW {STAGE_VIEW} AS" in notebook
    assert "NULL AS {_cf_quote_identifier(\"__merge_key_\" + key)}" in notebook
    assert "WHEN MATCHED AND target.{_cf_quote_identifier(ROW_HASH_COLUMN)} <> source.{_cf_quote_identifier(ROW_HASH_COLUMN)} THEN UPDATE SET" in notebook
    assert "target.{_cf_quote_identifier(IS_CURRENT_COLUMN)} = false" in notebook
    assert "WHEN NOT MATCHED THEN INSERT ({insert_columns}) VALUES ({insert_values})" in notebook

    schema_pos = notebook.index("    _cf_validate_schema_policy(dataframe=df)")
    scd2_pos = notebook.index("    # Stage source rows for SCD2 historical merge.")
    metric_pos = notebook.index("    _cf_rows_written = df.count()")
    assert schema_pos < scd2_pos < metric_pos


def test_fabric_historical_renders_effective_from_and_late_arriving_reject() -> None:
    notebook = render_fabric_contract(
        _contract(
            source={"type": "sql", "query": "SELECT 1 AS id, 'alpha' AS name, current_timestamp() AS event_ts"},
            scd2_effective_from_column="event_ts",
            scd2_sequence_by="event_ts",
            scd2_late_arriving_policy="reject",
        )
    ).artifacts["workspace_silver_customers_history.fabric.notebook.py"]

    compile(notebook, "workspace_silver_customers_history.fabric.notebook.py", "exec")
    assert "SCD2_EFFECTIVE_FROM_COLUMN = \"event_ts\"" in notebook
    assert "SCD2_SEQUENCE_BY = \"event_ts\"" in notebook
    assert "SCD2_LATE_ARRIVING_POLICY = \"reject\"" in notebook
    assert "df = df.withColumn(VALID_FROM_COLUMN, F.col(SCD2_EFFECTIVE_FROM_COLUMN).cast('timestamp'))" in notebook
    assert "raise ValueError('historical rejected late-arriving rows')" in notebook


def test_fabric_capabilities_report_historical_supported() -> None:
    artifacts = render_fabric_contract(_contract()).artifacts
    capabilities = json.loads(artifacts["workspace_silver_customers_history.fabric.capabilities.json"])

    assert capabilities["supports"]["historical"] is True
    assert "historical" not in capabilities["review_required_semantics"]
