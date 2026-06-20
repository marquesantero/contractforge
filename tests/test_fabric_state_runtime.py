from __future__ import annotations

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_fabric import render_fabric_contract
from contractforge_fabric.evidence import render_notebook_evidence_setup
from contractforge_fabric.state import notebook_state_lock_options, notebook_state_watermark_column


def _contract(source: dict[str, object] | None = None) -> dict[str, object]:
    return {
        "source": source or {"type": "sql", "query": "SELECT 1 AS id"},
        "target": {"catalog": "workspace", "schema": "silver", "table": "orders"},
        "mode": "overwrite",
    }


def test_fabric_state_watermark_column_comes_from_source_incremental() -> None:
    contract = semantic_contract_from_mapping(
        _contract({"type": "parquet", "path": "Files/orders", "incremental": {"watermark_column": "updated_at"}})
    )

    assert notebook_state_watermark_column(contract) == "updated_at"


def test_fabric_state_watermark_column_accepts_source_watermark_alias() -> None:
    contract = semantic_contract_from_mapping(
        _contract({"type": "parquet", "path": "Files/orders", "watermark": {"column": "event_ts"}})
    )

    assert notebook_state_watermark_column(contract) == "event_ts"


def test_fabric_state_lock_options_are_adapter_owned_extensions() -> None:
    contract = semantic_contract_from_mapping(
        {
            **_contract(),
            "extensions": {
                "fabric": {
                    "lock_enabled": True,
                    "lock_owner": "pipeline-a",
                    "lock_ttl_minutes": 15,
                }
            },
        }
    )

    assert notebook_state_lock_options(contract) == {
        "enabled": True,
        "owner": "pipeline-a",
        "ttl_minutes": 15,
    }


def test_fabric_notebook_renders_state_evidence_helpers() -> None:
    notebook = render_fabric_contract(
        _contract({"type": "parquet", "path": "Files/orders", "incremental": {"watermark_column": "updated_at"}})
    ).artifacts["workspace_silver_orders.fabric.notebook.py"]

    compile(notebook, "workspace_silver_orders.fabric.notebook.py", "exec")
    assert "_CF_STATE_WATERMARK_COLUMN = 'updated_at'" in notebook
    assert "'ctrl_ingestion_state'" in notebook
    assert "def _cf_state_watermark_candidate(dataframe):" in notebook
    assert "dataframe.selectExpr(f'max({_cf_sql_identifier(_CF_STATE_WATERMARK_COLUMN)}) AS watermark_value').collect()" in notebook
    assert "'last_run_id': RUN_ID" in notebook
    assert "'last_watermark_candidate': watermark_value" in notebook


def test_fabric_notebook_renders_lock_helpers_as_noop_by_default() -> None:
    notebook = render_fabric_contract(_contract()).artifacts["workspace_silver_orders.fabric.notebook.py"]

    compile(notebook, "workspace_silver_orders.fabric.notebook.py", "exec")
    assert "_CF_LOCK_ENABLED = False" in notebook
    assert "_cf_lock_acquired = False" in notebook
    assert "def _cf_acquire_lock():" in notebook
    assert "def _cf_release_lock():" in notebook
    assert "    _cf_acquire_lock()" in notebook
    assert "finally:" in notebook
    assert "    _cf_release_lock()" in notebook


def test_fabric_notebook_renders_opt_in_lock_sql() -> None:
    notebook = render_fabric_contract(
        {
            **_contract(),
            "extensions": {"fabric": {"lock_enabled": "true", "lock_owner": "job-1", "lock_ttl_minutes": "30"}},
        }
    ).artifacts["workspace_silver_orders.fabric.notebook.py"]

    compile(notebook, "workspace_silver_orders.fabric.notebook.py", "exec")
    assert "_CF_LOCK_ENABLED = True" in notebook
    assert "_CF_LOCK_OWNER = 'job-1'" in notebook
    assert "_CF_LOCK_TTL_MINUTES = 30" in notebook
    assert "MERGE INTO {lock_table} AS target" in notebook
    assert "current_timestamp() + INTERVAL {_CF_LOCK_TTL_MINUTES} MINUTES AS expires_at_utc" in notebook
    assert "WHEN MATCHED AND (target.status <> 'ACTIVE' OR target.expires_at_utc < current_timestamp())" in notebook
    assert "Fabric lock is busy for {TARGET_TABLE}; owner={owner}" in notebook
    assert "SET status = 'RELEASED', released_at_utc = current_timestamp()" in notebook


def test_fabric_state_update_is_after_write_and_before_run_evidence() -> None:
    notebook = render_fabric_contract(_contract()).artifacts["workspace_silver_orders.fabric.notebook.py"]

    lock_pos = notebook.index("    _cf_acquire_lock()")
    source_pos = notebook.index("    df = spark.sql")
    write_metric_pos = notebook.index("    _cf_rows_written = df.count()")
    lineage_pos = notebook.index("    _cf_record_lineage_evidence(input_dataframe=df, output_dataframe=df, status='SUCCESS')")
    state_pos = notebook.index("    _cf_record_state_evidence(dataframe=df)")
    success_pos = notebook.index("    _cf_record_run_evidence('SUCCESS')")
    release_pos = notebook.index("    _cf_release_lock()")

    assert lock_pos < source_pos < write_metric_pos < lineage_pos < state_pos < success_pos < release_pos


def test_fabric_notebook_state_setup_defaults_to_no_watermark() -> None:
    contract = semantic_contract_from_mapping(_contract())
    block = render_notebook_evidence_setup(contract)

    assert "_CF_STATE_WATERMARK_COLUMN = None" in block
    assert "_CF_LOCK_ENABLED = False" in block
    assert "'watermark_value': watermark_value" in block
