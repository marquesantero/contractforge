from __future__ import annotations

from datetime import datetime, timezone

from contractforge_core.deployment import (
    DEPLOYMENT_LEDGER_SCHEMA_VERSION,
    DEPLOYMENT_LEDGER_TABLE,
    build_deployment_ledger_record,
)
from contractforge_core.evidence import EVIDENCE_TABLES


def _record() -> dict[str, object]:
    return build_deployment_ledger_record(
        deployment_id="dep_test",
        adapter="contractforge-core-test",
        platform="test",
        subtarget="test_runtime",
        deployment_ts_utc=datetime(2026, 6, 19, 12, 0, tzinfo=timezone.utc),
        step_name="bronze_orders",
        project_name="ledger-smoke",
        project_path="project.yaml",
        environment_key="test",
        environment_path="test.environment.yaml",
        contract_name="bronze_orders",
        contract_path="contracts/bronze_orders.ingestion.yaml",
        contract_layer="bronze",
        target_table="catalog.schema.orders",
        mode="overwrite",
        action="created",
        deployment_status="SUCCEEDED",
        artifact_kind="job",
        artifact_name="cf_bronze_orders",
        artifact_id="artifact-1",
        definition_hash="a" * 64,
        contract_payload={"target": {"table": "orders"}, "mode": "overwrite"},
        environment_payload={"parameters": {"runtime": "test"}},
        manifest_payload={"step": "bronze_orders"},
        package_versions={"contractforge-core": "0.2.0"},
        git_commit="abc123",
        deployed_by="tester",
        deployment_config={"dry_run": False},
        deployment_result={"action": "created"},
        framework_version="0.2.0",
    )


def test_core_builds_unique_deployment_ledger_row_hashes() -> None:
    record = _record()

    assert DEPLOYMENT_LEDGER_TABLE == EVIDENCE_TABLES["deployments"]
    assert record["deployment_id"] == "dep_test"
    assert isinstance(record["deployment_step_id"], str)
    assert isinstance(record["deployment_hash"], str)
    assert isinstance(record["contract_hash"], str)
    assert isinstance(record["environment_hash"], str)
    assert isinstance(record["manifest_hash"], str)
    assert record["deployment_date"].isoformat() == "2026-06-19"  # type: ignore[union-attr]
    assert record["ctrl_schema_version"] == DEPLOYMENT_LEDGER_SCHEMA_VERSION


def test_all_adapters_render_native_deployment_ledger_ddl_and_inserts() -> None:
    from contractforge_aws.evidence import (
        render_create_evidence_tables_sql as aws_ddl,
        render_deployment_ledger_insert_sql as aws_insert,
    )
    from contractforge_databricks.evidence import (
        render_create_evidence_tables_sql as databricks_ddl,
        render_deployment_ledger_insert_sql as databricks_insert,
    )
    from contractforge_fabric.deployment import (
        render_deployment_ledger_ddl_sql as fabric_ddl,
        render_deployment_ledger_insert_sql as fabric_insert,
    )
    from contractforge_gcp.environment import GCPEnvironment
    from contractforge_gcp.evidence import render_deployment_ledger_insert_sql as gcp_insert
    from contractforge_gcp.rendering.evidence import render_bigquery_evidence_ddl
    from contractforge_snowflake.evidence import (
        render_create_evidence_tables_sql as snowflake_ddl,
        render_deployment_ledger_insert_sql as snowflake_insert,
    )

    record = _record()

    ddl_outputs = [
        databricks_ddl(catalog="main", schema="ops"),
        aws_ddl(database="contractforge_ops"),
        snowflake_ddl(database="CONTRACTFORGE", schema="CF_EVIDENCE"),
        fabric_ddl(schema="contractforge"),
        render_bigquery_evidence_ddl(project_id="p", dataset="ops"),
    ]
    assert all("ctrl_deployment_versions" in ddl for ddl in ddl_outputs)
    assert "PARTITION BY deployment_date" in ddl_outputs[-1]

    insert_outputs = [
        databricks_insert(record, catalog="main", schema="ops"),
        aws_insert(record, database="contractforge_ops"),
        snowflake_insert(record, database="CONTRACTFORGE", schema="CF_EVIDENCE"),
        fabric_insert(record, schema="contractforge"),
        gcp_insert(record, environment=GCPEnvironment(project_id="p", evidence_dataset="ops")),
    ]

    assert all(sql.startswith("INSERT INTO") for sql in insert_outputs)
    assert all("ctrl_deployment_versions" in sql for sql in insert_outputs)
    assert "DATE '2026-06-19'" in insert_outputs[1]
    assert "TO_DATE('2026-06-19')" in insert_outputs[2]
    assert "`p.ops.ctrl_deployment_versions`" in insert_outputs[4]


def test_aws_athena_evidence_ddl_uses_safe_unquoted_identifiers() -> None:
    from contractforge_aws.evidence.athena_ddl import render_create_evidence_tables_athena_sql

    sql = render_create_evidence_tables_athena_sql(
        database="contractforge_ops",
        warehouse_uri="s3://contractforge-test/warehouse/",
    )

    assert "contractforge_ops.ctrl_deployment_versions" in sql
    assert "deployment_id STRING" in sql
    assert "`" not in sql
