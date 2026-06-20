from __future__ import annotations

import json

from contractforge_fabric import plan_fabric_contract, render_fabric_contract


def _contract(**overrides: object) -> dict[str, object]:
    contract: dict[str, object] = {
        "source": {"type": "sql", "query": "SELECT 1 AS id, 'alpha' AS name, 'a@example.com' AS email"},
        "target": {"catalog": "workspace", "schema": "silver", "table": "customers"},
        "mode": "hash_diff_upsert",
        "merge_keys": ["id"],
        "hash_keys": ["name", "email"],
    }
    contract.update(overrides)
    return contract


def test_fabric_plan_supports_hash_diff_with_runtime_warning() -> None:
    result = plan_fabric_contract(_contract())

    assert result.status == "SUPPORTED_WITH_WARNINGS"
    assert result.plan is not None
    assert not result.blockers


def test_fabric_notebook_renders_hash_diff_merge() -> None:
    notebook = render_fabric_contract(_contract()).artifacts["workspace_silver_customers.fabric.notebook.py"]

    compile(notebook, "workspace_silver_customers.fabric.notebook.py", "exec")
    assert "MERGE_KEYS = [\"id\"]" in notebook
    assert "HASH_STRATEGY = \"explicit\"" in notebook
    assert "DECLARED_HASH_KEYS = [\"name\", \"email\"]" in notebook
    assert "ROW_HASH_COLUMN = 'row_hash'" in notebook
    assert "hash_payload = [F.coalesce(F.col(column).cast('string'), F.lit('\\x00')) for column in hash_input_columns]" in notebook
    assert "df = df.withColumn(ROW_HASH_COLUMN, F.sha2(F.concat_ws('\\x1f', *hash_payload), 256))" in notebook
    assert "missing_hash_columns = [column for column in hash_keys if column not in df.columns]" in notebook
    assert "hash_input_columns = [column for column in hash_keys if column not in hash_excluded]" in notebook
    assert "target_hash.{row_hash_identifier} <> source.{row_hash_identifier}" in notebook
    assert "WHEN MATCHED AND (target.{row_hash_identifier} IS NULL OR target.{row_hash_identifier} <> source.{row_hash_identifier}) THEN UPDATE SET {assignments}" in notebook

    schema_pos = notebook.index("    _cf_validate_schema_policy(dataframe=df)")
    hash_pos = notebook.index("    # Compute a deterministic content row_hash")
    metric_pos = notebook.index("    _cf_rows_written = df.count()")
    assert schema_pos < hash_pos < metric_pos


def test_fabric_hash_diff_supports_all_columns_except_strategy() -> None:
    notebook = render_fabric_contract(
        _contract(hash_keys=[], hash_strategy="all_columns_except", hash_exclude_columns=["email"])
    ).artifacts["workspace_silver_customers.fabric.notebook.py"]

    compile(notebook, "workspace_silver_customers.fabric.notebook.py", "exec")
    assert "HASH_STRATEGY = \"all_columns_except\"" in notebook
    assert "DECLARED_HASH_KEYS = []" in notebook
    assert "hash_keys = df.columns if HASH_STRATEGY == 'all_columns_except' else DECLARED_HASH_KEYS" in notebook
    assert '"email"' in notebook


def test_fabric_capabilities_report_hash_diff_supported() -> None:
    artifacts = render_fabric_contract(_contract()).artifacts
    capabilities = json.loads(artifacts["workspace_silver_customers.fabric.capabilities.json"])

    assert capabilities["supports"]["hash_diff_upsert"] is True
    assert "hash_diff_upsert" not in capabilities["review_required_semantics"]
