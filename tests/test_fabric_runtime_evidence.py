from __future__ import annotations

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_fabric import render_fabric_contract
from contractforge_fabric.evidence import render_notebook_evidence_setup


def _contract() -> dict[str, object]:
    return {
        "source": {"type": "sql", "query": "SELECT 1 AS id, 'alpha' AS name"},
        "target": {"catalog": "workspace", "schema": "silver", "table": "orders"},
        "mode": "overwrite",
        "quality_rules": {"required_columns": ["id"], "not_null": ["id"]},
        "operations": {
            "criticality": "high",
            "expected_frequency": "daily",
            "freshness_sla_minutes": 120,
            "owners": ["data-platform"],
            "tags": {"domain": "sales"},
        },
        "annotations": {"table": {"description": "Curated orders"}},
        "access": {"grants": [{"principal": "fabric-analysts", "privileges": ["select"]}]},
    }


def test_fabric_notebook_renders_run_and_error_evidence_helpers() -> None:
    notebook = render_fabric_contract(_contract()).artifacts["workspace_silver_orders.fabric.notebook.py"]

    compile(notebook, "workspace_silver_orders.fabric.notebook.py", "exec")
    assert "RUN_ID = str(uuid.uuid4())" in notebook
    assert "_cf_record_run_evidence(status, error_message=None)" in notebook
    assert "_cf_record_error_evidence(error)" in notebook
    assert "'ctrl_ingestion_runs'" in notebook
    assert "'ctrl_ingestion_errors'" in notebook
    assert "'ctrl_ingestion_quality'" in notebook
    assert "'ctrl_ingestion_quarantine'" in notebook
    assert "'ctrl_ingestion_lineage'" in notebook
    assert "'ctrl_ingestion_metadata'" in notebook
    assert "'ctrl_ingestion_schema_changes'" in notebook
    assert "'ctrl_ingestion_explain'" in notebook
    assert "'ctrl_ingestion_operations'" in notebook
    assert "'ctrl_ingestion_annotations'" in notebook
    assert "'ctrl_ingestion_access'" in notebook
    assert "_CF_OPERATIONS_PAYLOAD = json.loads(" in notebook
    assert "_CF_ANNOTATION_STEPS = json.loads(" in notebook
    assert "_CF_ACCESS_STEPS = json.loads(" in notebook
    assert "_CF_EVIDENCE_BOOTSTRAP_ENABLED = True" in notebook
    assert "_CF_EVIDENCE_BOOTSTRAP_SQL = json.loads(" in notebook
    assert "CREATE TABLE IF NOT EXISTS `__CF_EVIDENCE_SCHEMA__`.`ctrl_ingestion_runs`" in notebook
    assert "CREATE TABLE IF NOT EXISTS `__CF_EVIDENCE_SCHEMA__`.`ctrl_ingestion_state`" in notebook
    assert "statement.replace('`__CF_EVIDENCE_SCHEMA__`', _cf_sql_identifier(EVIDENCE_SCHEMA))" in notebook
    assert "_cf_record_quality_evidence()" in notebook
    assert "def _cf_record_quarantine_evidence(rule_name, failed_dataframe, reason):" in notebook
    assert "_cf_record_explain_evidence(dataframe=df)" in notebook
    assert "_cf_record_lineage_evidence(input_dataframe=df, output_dataframe=df, status='SUCCESS')" in notebook
    assert "_cf_record_schema_change_evidence(dataframe=df)" in notebook
    assert "_cf_record_source_metadata_evidence(dataframe=df)" in notebook
    assert "_cf_record_operations_evidence()" in notebook
    assert "_cf_record_annotations_evidence()" in notebook
    assert "_cf_record_access_evidence()" in notebook
    assert "'framework_version': 'contractforge-fabric'" in notebook
    assert "'runtime_type': 'fabric_notebook'" in notebook


def test_fabric_notebook_wraps_contract_execution_and_records_outcomes() -> None:
    notebook = render_fabric_contract(_contract()).artifacts["workspace_silver_orders.fabric.notebook.py"]

    source_pos = notebook.index('    df = spark.sql("SELECT 1 AS id')
    bootstrap_pos = notebook.index("_cf_bootstrap_evidence_tables()")
    lock_pos = notebook.index("    _cf_acquire_lock()")
    read_metric_pos = notebook.index("    _cf_rows_read = df.count()")
    quality_pos = notebook.index("    # ContractForge quality gates.")
    write_pos = notebook.index('    df.write.format("delta").mode("overwrite").saveAsTable(TARGET_TABLE)')
    write_metric_pos = notebook.index("    _cf_rows_written = df.count()")
    explain_pos = notebook.index("    _cf_record_explain_evidence(dataframe=df)")
    lineage_pos = notebook.index("    _cf_record_lineage_evidence(input_dataframe=df, output_dataframe=df, status='SUCCESS')")
    schema_pos = notebook.index("    _cf_record_schema_change_evidence(dataframe=df)")
    metadata_pos = notebook.index("    _cf_record_source_metadata_evidence(dataframe=df)")
    operations_pos = notebook.index("    _cf_record_operations_evidence()")
    annotations_pos = notebook.index("    _cf_record_annotations_evidence()")
    access_pos = notebook.index("    _cf_record_access_evidence()")
    success_pos = notebook.index("    _cf_record_run_evidence('SUCCESS')")
    failure_pos = notebook.index("    _cf_record_run_evidence('FAILED', str(_cf_error))")

    assert "try:" in notebook
    assert "except Exception as _cf_error:" in notebook
    assert (
        bootstrap_pos
        < lock_pos
        < source_pos
        < read_metric_pos
        < quality_pos
        < write_pos
        < write_metric_pos
        < explain_pos
        < lineage_pos
        < schema_pos
        < metadata_pos
        < operations_pos
        < annotations_pos
        < access_pos
        < success_pos
        < failure_pos
    )


def test_fabric_notebook_evidence_setup_uses_target_layer_and_shared_schema() -> None:
    contract = semantic_contract_from_mapping(_contract())
    block = render_notebook_evidence_setup(contract)

    assert "'layer':" in block
    assert contract.target.layer in block
    assert "_cf_sql_table(EVIDENCE_SCHEMA, table)" in block
    assert "'quality_status': _cf_quality_status" in block
    assert "'rows_quarantined': _cf_rows_quarantined" in block
    assert "'schemaURL': 'https://openlineage.io/spec/1-0-5/OpenLineage.json'" in block
    assert "'event_json': json.dumps(event, sort_keys=True, separators=(',', ':'))" in block
    assert "_CF_SOURCE_METADATA = json.loads(" in block
    assert "metrics['rows_read'] = _cf_rows_read" in block
    assert "metrics['columns_read'] = len(dataframe.columns) if dataframe is not None else 0" in block
    assert "'source_metadata_json': json.dumps(metadata, sort_keys=True, separators=(',', ':'))" in block
    assert "def _cf_record_schema_change_evidence(dataframe=None):" in block
    assert "'change_type': 'OBSERVED_SCHEMA'" in block
    assert "'schema_changes_json': json.dumps(_cf_schema_changes, sort_keys=True, separators=(',', ':')) if _cf_schema_changes else None" in block
    assert "def _cf_record_explain_evidence(dataframe=None):" in block
    assert "'explain_format': 'spark_query_execution'" in block
    assert "def _cf_record_operations_evidence(status='RECORDED'):" in block
    assert "'owners_json': json.dumps(payload.get('owners') or [], sort_keys=True, separators=(',', ':'))" in block
    assert "def _cf_record_annotations_evidence(status='VALIDATED'):" in block
    assert "def _cf_record_access_evidence(status='VALIDATED'):" in block
    assert "def _cf_bootstrap_evidence_tables():" in block
    assert "_CF_EVIDENCE_BOOTSTRAP_SQL = json.loads(" in block


def test_fabric_notebook_evidence_bootstrap_can_be_disabled() -> None:
    contract = {
        **_contract(),
        "extensions": {"fabric": {"bootstrap_evidence_tables": False}},
    }
    notebook = render_fabric_contract(contract).artifacts["workspace_silver_orders.fabric.notebook.py"]

    compile(notebook, "workspace_silver_orders.fabric.notebook.py", "exec")
    assert "_CF_EVIDENCE_BOOTSTRAP_ENABLED = False" in notebook
    assert '_CF_EVIDENCE_BOOTSTRAP_SQL = json.loads("[]")' in notebook
    assert "_cf_bootstrap_evidence_tables()" in notebook
