import json
import sys
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import pytest

from contractforge_snowflake import (
    SNOWFLAKE_SUBTARGET_SQL_WAREHOUSE,
    build_control_retention_plan,
    build_snowflake_publish_bundle,
    build_snowflake_project_cleanup_plan,
    deploy_snowflake_project,
    execute_control_retention_plan,
    list_snowflake_subtargets,
    plan_snowflake_contract,
    publish_snowflake_contract,
    reconcile_snowflake_access_history_lineage,
    reconcile_snowflake_cost_evidence,
    render_control_dashboard_artifacts,
    render_control_dashboard_sql,
    render_snowflake_contract,
    run_snowflake_contract,
    run_snowflake_project,
    snowflake_sql_warehouse_capabilities,
    wait_snowflake_project_tasks,
)
from contractforge_snowflake.naming import quote_identifier, quote_multipart_identifier
from contractforge_snowflake.environment import SnowflakeEnvironment
from contractforge_snowflake.evidence import bootstrap_evidence_tables, render_create_evidence_tables_sql
from contractforge_snowflake.runtime.artifacts import MAX_RUNTIME_ARTIFACT_BYTES, load_json_artifact
from contractforge_snowflake.runtime.schema_policy import source_column_types_for
from contractforge_snowflake.runtime.session import SnowflakeConnectorSession
from contractforge_snowflake.connection_options import validate_connect_options
from contractforge_snowflake.subtargets import adapter_for_subtarget
from contractforge_snowflake.cli import main as snowflake_cli_main


def _append_contract() -> dict:
    return {
        "source": {"type": "table", "table": "raw.customers"},
        "target": {"catalog": "ANALYTICS", "schema": "BRONZE", "table": "CUSTOMERS"},
        "mode": "scd0_append",
    }


def test_snowflake_capabilities_declare_sql_warehouse_target() -> None:
    capabilities = snowflake_sql_warehouse_capabilities()

    assert capabilities.platform == SNOWFLAKE_SUBTARGET_SQL_WAREHOUSE
    assert capabilities.supports_append
    assert capabilities.supports_overwrite
    assert capabilities.supports_merge
    assert capabilities.supports_hash_diff
    assert not capabilities.supports_scd2
    assert not capabilities.supports_snapshot_soft_delete
    assert capabilities.supports_schema_evolution
    assert capabilities.supports_row_filters
    assert capabilities.supports_column_masks
    assert not capabilities.supports_available_now_streaming
    assert capabilities.supports_shape
    assert capabilities.supports_transform
    assert capabilities.evidence_stores == ("snowflake_audit_tables",)
    assert "scd2_historical" in capabilities.review_required_semantics
    assert "snapshot_soft_delete" in capabilities.review_required_semantics
    assert "available_now_streaming" in capabilities.review_required_semantics


def test_snowflake_public_subtarget_registry_lists_reference_target() -> None:
    assert list_snowflake_subtargets() == (SNOWFLAKE_SUBTARGET_SQL_WAREHOUSE,)


def test_snowflake_unsupported_subtarget_errors() -> None:
    with pytest.raises(ValueError, match="Unsupported Snowflake adapter subtarget"):
        adapter_for_subtarget("snowflake_snowpark")


def test_snowflake_plan_supports_simple_append_contract() -> None:
    result = plan_snowflake_contract(_append_contract())

    assert result.status == "SUPPORTED"
    assert result.plan is not None
    assert result.plan.platform == SNOWFLAKE_SUBTARGET_SQL_WAREHOUSE


def test_snowflake_plan_warns_for_unknown_extension_keys() -> None:
    result = plan_snowflake_contract(
        {
            **_append_contract(),
            "extensions": {"snowflake": {"lock_enabled": True, "mystery_option": True}},
        }
    )

    assert result.status == "SUPPORTED_WITH_WARNINGS"
    warning = next(item for item in result.warnings if item.code == "SNOWFLAKE_UNKNOWN_EXTENSION")
    assert "extensions.snowflake.mystery_option" in warning.message


def test_snowflake_plan_warns_for_hash_diff_semantics() -> None:
    contract = {
        "source": {"type": "table", "table": "raw.customers"},
        "target": {"catalog": "ANALYTICS", "schema": "SILVER", "table": "CUSTOMERS"},
        "mode": "scd1_hash_diff",
        "merge_keys": ["customer_id"],
        "hash_strategy": "all_columns_except",
        "hash_exclude_columns": ["loaded_at"],
    }

    result = plan_snowflake_contract(contract)

    assert result.status == "SUPPORTED_WITH_WARNINGS"
    assert "SNOWFLAKE_HASH_DIFF_SEMANTICS" in {warning.code for warning in result.warnings}


def test_snowflake_plan_keeps_scd2_review_required() -> None:
    contract = {
        "source": {"type": "table", "table": "raw.customers"},
        "target": {"catalog": "ANALYTICS", "schema": "SILVER", "table": "CUSTOMERS"},
        "mode": "scd2_historical",
        "merge_keys": ["customer_id"],
    }

    result = plan_snowflake_contract(contract)

    assert result.status == "REVIEW_REQUIRED"
    assert result.plan is not None
    assert "REVIEW_REQUIRED" in {warning.code for warning in result.warnings}


def test_snowflake_plan_keeps_snapshot_soft_delete_review_required() -> None:
    contract = {
        "source": {"type": "table", "table": "raw.customers", "read": {"source_complete": True}},
        "target": {"catalog": "ANALYTICS", "schema": "SILVER", "table": "CUSTOMERS"},
        "mode": "snapshot_soft_delete",
        "merge_keys": ["customer_id"],
    }

    result = plan_snowflake_contract(contract)

    assert result.status == "REVIEW_REQUIRED"
    assert result.plan is not None
    assert "REVIEW_REQUIRED" in {warning.code for warning in result.warnings}


def test_snowflake_plan_supports_sql_compatible_shape_and_transform() -> None:
    contract = {
        "source": {"type": "table", "table": "raw.customers"},
        "target": {"catalog": "ANALYTICS", "schema": "BRONZE", "table": "CUSTOMERS"},
        "mode": "scd0_append",
        "shape": {"columns": {"customer_id": {"expression": "id"}}},
        "transform": {"derive": {"email_domain": "split_part(email, '@', 2)"}},
    }

    result = plan_snowflake_contract(contract)

    assert result.status == "SUPPORTED"
    assert result.plan is not None


def test_snowflake_plan_marks_unsupported_shape_review_required() -> None:
    contract = {
        "source": {"type": "table", "table": "raw.customers"},
        "target": {"catalog": "ANALYTICS", "schema": "BRONZE", "table": "CUSTOMERS"},
        "mode": "scd0_append",
        "shape": {"parse_json": [{"column": "payload", "schema": "id STRING"}]},
    }

    result = plan_snowflake_contract(contract)

    assert result.status == "REVIEW_REQUIRED"
    assert "SNOWFLAKE_PREPARATION_REVIEW_REQUIRED" in {warning.code for warning in result.warnings}


def test_snowflake_plan_marks_available_now_review_required() -> None:
    contract = {
        "source": {"type": "table", "table": "raw.customers", "trigger": "available_now"},
        "target": {"catalog": "ANALYTICS", "schema": "BRONZE", "table": "CUSTOMERS"},
        "mode": "scd0_append",
    }

    result = plan_snowflake_contract(contract)

    assert result.status == "REVIEW_REQUIRED"
    assert result.plan is not None
    assert "REVIEW_REQUIRED" in {warning.code for warning in result.warnings}


def test_snowflake_plan_marks_incremental_files_review_required() -> None:
    contract = {
        "source": {
            "type": "incremental_files",
            "path": "s3://landing/customers/",
            "format": "json",
        },
        "target": {"catalog": "ANALYTICS", "schema": "BRONZE", "table": "CUSTOMERS"},
        "mode": "scd0_append",
    }

    result = plan_snowflake_contract(contract)

    assert result.status == "REVIEW_REQUIRED"
    assert "SNOWFLAKE_INCREMENTAL_FILES_REVIEW_REQUIRED" in {warning.code for warning in result.warnings}


def test_snowflake_plan_supports_staged_files_source() -> None:
    contract = {
        "source": {
            "type": "staged_files",
            "path": "@RAW_STAGE/customers/",
            "format": "csv",
            "options": {
                "file_format": "RAW_CSV_FORMAT",
                "columns": {"customer_id": "$1::NUMBER", "name": "$2::STRING"},
            },
        },
        "target": {"catalog": "ANALYTICS", "schema": "BRONZE", "table": "CUSTOMERS"},
        "mode": "scd0_append",
    }

    result = plan_snowflake_contract(contract)

    assert result.status == "SUPPORTED"
    assert result.plan is not None


def test_snowflake_plan_blocks_databricks_autoloader_source() -> None:
    contract = {
        "source": {"type": "autoloader", "path": "s3://landing/customers/", "format": "json"},
        "target": {"catalog": "ANALYTICS", "schema": "BRONZE", "table": "CUSTOMERS"},
        "mode": "scd0_append",
    }

    result = plan_snowflake_contract(contract)

    assert result.status == "UNSUPPORTED"
    assert result.plan is None
    assert [blocker.code for blocker in result.blockers] == ["SNOWFLAKE_SOURCE_AUTOLOADER_UNSUPPORTED"]


def test_snowflake_render_contract_returns_review_artifacts() -> None:
    rendered = render_snowflake_contract(
        _append_contract(),
        environment={
            "evidence": {"database": "CONTRACTFORGE", "schema": "CF_EVIDENCE"},
            "parameters": {"snowflake": {"warehouse": "CF_WH", "role": "CONTRACTFORGE_ROLE"}},
        },
    )

    assert set(rendered.artifacts) == {
        "infrastructure/ANALYTICS.BRONZE_CUSTOMERS.evidence_ddl.sql",
        "runtime/ANALYTICS.BRONZE_CUSTOMERS.contract.json",
        "runtime/ANALYTICS.BRONZE_CUSTOMERS.environment.json",
        "runtime/ANALYTICS.BRONZE_CUSTOMERS.runner_invocation.json",
        "snowflake.capabilities.json",
        "snowflake.publish_manifest.json",
        "snowflake.planning.md",
    }
    capability_summary = json.loads(rendered.artifacts["snowflake.capabilities.json"])
    assert capability_summary["planning_status"] == "SUPPORTED"
    assert capability_summary["runtime"]["execution_model"] == "library_runner"
    assert capability_summary["runtime"]["warehouse"] == "CF_WH"
    assert "Snowflake Planning Review" in rendered.artifacts["snowflake.planning.md"]
    assert 'CREATE TABLE IF NOT EXISTS "CONTRACTFORGE"."CF_EVIDENCE"."ctrl_ingestion_runs"' in rendered.artifacts[
        "infrastructure/ANALYTICS.BRONZE_CUSTOMERS.evidence_ddl.sql"
    ]
    assert '"trigger" STRING' in rendered.artifacts["infrastructure/ANALYTICS.BRONZE_CUSTOMERS.evidence_ddl.sql"]
    invocation = json.loads(rendered.artifacts["runtime/ANALYTICS.BRONZE_CUSTOMERS.runner_invocation.json"])
    assert invocation["execution_model"] == "library_runner"
    assert invocation["runner_function"] == "run_snowflake_contract"
    manifest = json.loads(rendered.artifacts["snowflake.publish_manifest.json"])
    assert manifest["artifact_summary"]["count"] == len(rendered.artifacts)
    assert manifest["artifact_summary"]["generated_ingestion_artifacts"] is False
    assert "runtime/ANALYTICS.BRONZE_CUSTOMERS.contract.json" in manifest["artifacts"]
    assert all(not name.endswith((".source.sql", ".write.sql")) for name in rendered.artifacts)


def test_snowflake_evidence_ddl_can_skip_existing_database_and_schema_bootstrap() -> None:
    sql = render_create_evidence_tables_sql(
        database="CONTRACTFORGE_TEST_DB",
        schema="PUBLIC",
        create_database=False,
        create_schema=False,
    )

    assert "CREATE DATABASE" not in sql
    assert "CREATE SCHEMA" not in sql
    assert 'CREATE TABLE IF NOT EXISTS "CONTRACTFORGE_TEST_DB"."PUBLIC"."ctrl_ingestion_runs"' in sql


def test_snowflake_bootstrap_reuses_existing_database_and_schema_for_service_role() -> None:
    session = _ExecutingSnowflakeSession()
    environment = SnowflakeEnvironment.from_contract(
        {
            "evidence": {
                "database": "CONTRACTFORGE_TEST_DB",
                "schema": "PUBLIC",
                "create_database": False,
                "create_schema": False,
            }
        }
    )

    result = bootstrap_evidence_tables(session, environment)

    assert not any(command.startswith("CREATE DATABASE") for command in session.commands)
    assert not any(command.startswith("CREATE SCHEMA") for command in session.commands)
    assert result.skipped_commands == (
        'CREATE DATABASE IF NOT EXISTS "CONTRACTFORGE_TEST_DB"',
        'CREATE SCHEMA IF NOT EXISTS "CONTRACTFORGE_TEST_DB"."PUBLIC"',
    )
    assert any('CREATE TABLE IF NOT EXISTS "CONTRACTFORGE_TEST_DB"."PUBLIC"."ctrl_ingestion_runs"' in command for command in session.commands)


def test_snowflake_bootstrap_validate_only_returns_commands_without_execution() -> None:
    session = _ExecutingSnowflakeSession()
    environment = SnowflakeEnvironment.from_contract(
        {
            "evidence": {
                "database": "CONTRACTFORGE",
                "schema": "CF_EVIDENCE",
                "validate_only_ddl": True,
            }
        }
    )

    result = bootstrap_evidence_tables(session, environment)

    assert result.commands
    assert session.commands == []


def test_snowflake_publish_bundle_is_public_api() -> None:
    rendered = build_snowflake_publish_bundle(_append_contract())

    manifest = json.loads(rendered.artifacts["snowflake.publish_manifest.json"])

    assert manifest["artifact_summary"]["mode"] == "publish_bundle"
    assert manifest["artifact_summary"]["execution_model"] == "library_runner"


def test_snowflake_default_import_does_not_require_runtime_dependencies() -> None:
    assert "snowflake.connector" not in sys.modules
    assert "snowflake.snowpark" not in sys.modules


def test_snowflake_runtime_procedure_renders_external_access_options() -> None:
    from contractforge_snowflake.deployment.procedure import render_runtime_procedure_sql

    sql = render_runtime_procedure_sql(
        {
            "parameters": {
                "snowflake": {
                    "runtime_imports": ["@CONTRACTFORGE_ARTIFACTS/runtime/contractforge_snowflake.zip"],
                    "external_access_integrations": ["CF_USGS_REST_ACCESS"],
                    "secrets": {"api_key": "CONTRACTFORGE_TEST_DB.PUBLIC.CF_USGS_API_KEY"},
                }
            }
        }
    )

    assert 'EXTERNAL_ACCESS_INTEGRATIONS = ("CF_USGS_REST_ACCESS")' in sql
    assert 'SECRETS = (\'api_key\' = "CONTRACTFORGE_TEST_DB"."PUBLIC"."CF_USGS_API_KEY")' in sql


def test_snowflake_identifier_quoting_is_safe() -> None:
    assert quote_identifier('weird"name') == '"weird""name"'
    assert quote_multipart_identifier('DB.SCHEMA.table"name') == '"DB"."SCHEMA"."table""name"'


def test_snowflake_publish_bundle_does_not_render_upsert_ingestion_sql() -> None:
    rendered = build_snowflake_publish_bundle(
        {
            "source": {"type": "sql", "query": "select customer_id, name from raw.customers"},
            "target": {"catalog": "ANALYTICS", "schema": "SILVER", "table": "CUSTOMERS"},
            "mode": "scd1_upsert",
            "merge_keys": ["customer_id"],
        }
    )

    assert "runtime/ANALYTICS.SILVER_CUSTOMERS.contract.json" in rendered.artifacts
    assert all(not name.endswith((".source.sql", ".write.sql")) for name in rendered.artifacts)


def test_snowflake_publish_bundle_does_not_render_hash_diff_ingestion_sql() -> None:
    rendered = build_snowflake_publish_bundle(
        {
            "source": {"type": "table", "table": "raw.customers"},
            "target": {"catalog": "ANALYTICS", "schema": "SILVER", "table": "CUSTOMERS"},
            "mode": "scd1_hash_diff",
            "merge_keys": ["customer_id"],
            "hash_keys": ["name", "email"],
        }
    )

    manifest = json.loads(rendered.artifacts["snowflake.publish_manifest.json"])

    assert manifest["planning_status"] == "SUPPORTED_WITH_WARNINGS"
    assert all(not name.endswith((".source.sql", ".write.sql")) for name in rendered.artifacts)


def test_snowflake_publish_contract_uploads_library_runner_bundle() -> None:
    connection = _FakeSnowflakeConnection()

    result = publish_snowflake_contract(
        _append_contract(),
        environment={"artifacts": {"uri": "@CONTRACTFORGE_ARTIFACTS/dev"}},
        connection=connection,
    )

    assert result.execution_model == "library_runner"
    assert result.stage == "@CONTRACTFORGE_ARTIFACTS"
    assert result.prefix == "dev"
    assert result.manifest_uri == "@CONTRACTFORGE_ARTIFACTS/dev/snowflake.publish_manifest.json"
    assert {artifact.name for artifact in result.artifacts} == {
        "infrastructure/ANALYTICS.BRONZE_CUSTOMERS.evidence_ddl.sql",
        "runtime/ANALYTICS.BRONZE_CUSTOMERS.contract.json",
        "runtime/ANALYTICS.BRONZE_CUSTOMERS.environment.json",
        "runtime/ANALYTICS.BRONZE_CUSTOMERS.runner_invocation.json",
        "snowflake.capabilities.json",
        "snowflake.planning.md",
        "snowflake.publish_manifest.json",
    }
    assert len(connection.commands) == len(result.artifacts)
    assert all(" AUTO_COMPRESS=FALSE OVERWRITE=TRUE" in command for command in connection.commands)
    assert all(".source.sql" not in command and ".write.sql" not in command for command in connection.commands)


def test_snowflake_publish_contract_requires_stage() -> None:
    with pytest.raises(ValueError, match="requires a stage"):
        publish_snowflake_contract(_append_contract(), connection=_FakeSnowflakeConnection())


def test_snowflake_publish_contract_rejects_unsafe_stage() -> None:
    with pytest.raises(ValueError, match="Unsafe Snowflake stage"):
        publish_snowflake_contract(_append_contract(), stage="@SAFE;DROP", connection=_FakeSnowflakeConnection())


def test_snowflake_publish_closes_owned_connection_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    from contractforge_snowflake.runtime import publish as publish_module

    connection = _FailingSnowflakeConnection()
    monkeypatch.setattr(publish_module, "_connect", lambda _: connection)

    with pytest.raises(RuntimeError, match="upload failed"):
        publish_snowflake_contract(_append_contract(), stage="@CONTRACTFORGE_ARTIFACTS")

    assert connection.closed


def test_snowflake_publish_accepts_connection_factory() -> None:
    connection = _FakeSnowflakeConnection()
    observed: dict[str, object] = {}

    def factory(options: dict[str, object]) -> _FakeSnowflakeConnection:
        observed["options"] = options
        return connection

    result = publish_snowflake_contract(
        _append_contract(),
        environment={"artifacts": {"uri": "@CONTRACTFORGE_ARTIFACTS/dev"}},
        connect_options={"account": "TEST_ACCOUNT", "user": "CFINGESTSVC"},
        connection_factory=factory,
    )

    assert result.manifest_uri == "@CONTRACTFORGE_ARTIFACTS/dev/snowflake.publish_manifest.json"
    assert observed["options"] == {"account": "TEST_ACCOUNT", "user": "CFINGESTSVC"}
    assert connection.closed


def test_snowflake_runtime_stage_artifacts_require_snowpark_file_session() -> None:
    with pytest.raises(ValueError, match="stage artifact loading requires"):
        run_snowflake_contract(contract_uri="@CONTRACTFORGE_ARTIFACTS/dev/runtime/customers.contract.json")


def test_snowflake_runtime_rejects_unsafe_stage_artifact_uri() -> None:
    session = _FakeSnowflakeSession({})

    with pytest.raises(ValueError, match="Unsafe Snowflake stage artifact URI"):
        run_snowflake_contract(contract_uri="@CONTRACTFORGE_ARTIFACTS/../secrets.contract.json", session=session)


def test_snowflake_runtime_rejects_oversized_local_artifact(tmp_path) -> None:
    artifact = tmp_path / "large.json"
    artifact.write_bytes(b"x" * (MAX_RUNTIME_ARTIFACT_BYTES + 1))

    with pytest.raises(ValueError, match="runtime artifact is too large"):
        load_json_artifact(str(artifact))


def test_snowflake_runtime_dry_run_plans_local_artifacts(tmp_path) -> None:
    contract_path = tmp_path / "contract.json"
    environment_path = tmp_path / "environment.json"
    contract_path.write_text(json.dumps(_append_contract()), encoding="utf-8")
    environment_path.write_text(json.dumps({"parameters": {"snowflake": {"warehouse": "CF_WH"}}}), encoding="utf-8")

    result = run_snowflake_contract(
        contract_uri=contract_path.as_uri(),
        environment_uri=environment_path.as_uri(),
        dry_run=True,
    )

    assert result == {"status": "DRY_RUN", "planning_status": "SUPPORTED", "warnings": [], "blockers": []}


def test_snowflake_runtime_dry_run_loads_stage_artifacts_from_session() -> None:
    session = _FakeSnowflakeSession(
        {
            "@CONTRACTFORGE_ARTIFACTS/dev/runtime/customers.contract.json": json.dumps(_append_contract()),
            "@CONTRACTFORGE_ARTIFACTS/dev/runtime/customers.environment.json": json.dumps({}),
        }
    )

    result = run_snowflake_contract(
        contract_uri="@CONTRACTFORGE_ARTIFACTS/dev/runtime/customers.contract.json",
        environment_uri="@CONTRACTFORGE_ARTIFACTS/dev/runtime/customers.environment.json",
        session=session,
        dry_run=True,
    )

    assert result["planning_status"] == "SUPPORTED"


def test_snowflake_connector_session_loads_stage_artifacts_with_get() -> None:
    connection = _StageGetSnowflakeConnection(b'{"status": "ok"}')
    session = SnowflakeConnectorSession(connection)

    payload = load_json_artifact("@CONTRACTFORGE_ARTIFACTS/dev/runtime/customers.contract.json", session=session)

    assert payload == {"status": "ok"}
    assert any(command.startswith("GET @CONTRACTFORGE_ARTIFACTS/dev/runtime/customers.contract.json") for command in connection.commands)


def test_snowflake_runtime_non_dry_run_loads_and_reports_planning(tmp_path) -> None:
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(_append_contract()), encoding="utf-8")
    session = _ExecutingSnowflakeSession(
        scalars={
            "SELECT CURRENT_WAREHOUSE()": ("COMPUTE_WH", "CONTRACTFORGE_INGEST_ROLE", "ANALYTICS", "BRONZE", "8.40.0"),
            'SELECT COUNT(*) FROM (\nSELECT * FROM "raw"."customers"': 3,
        }
    )

    result = run_snowflake_contract(contract_uri=str(contract_path), session=session)

    assert result["status"] == "SUCCESS"
    assert result["planning_status"] == "SUPPORTED"
    assert result["run_id"]
    assert any('"run_id": "' + result["run_id"] in command for command in session.commands)
    assert any('"target": "ANALYTICS.BRONZE.CUSTOMERS"' in command for command in session.commands)
    assert any('CREATE TABLE IF NOT EXISTS "ANALYTICS"."BRONZE"."CUSTOMERS" AS' in command for command in session.commands)
    assert any('INSERT INTO "ANALYTICS"."BRONZE"."CUSTOMERS"' in command for command in session.commands)
    assert any('FROM "raw"."customers"' in command for command in session.commands)
    run_insert = next(command for command in session.commands if '"ctrl_ingestion_runs"' in command and "INSERT INTO" in command)
    assert '"rows_read"' in run_insert
    assert '"rows_written"' in run_insert
    assert '"rows_inserted"' in run_insert
    assert '"operation_metrics_json"' in run_insert
    assert '"metrics_json"' in run_insert
    assert "'snowflake_logical_count'" in run_insert
    assert '"warehouse":"COMPUTE_WH"' in run_insert
    assert '"role":"CONTRACTFORGE_INGEST_ROLE"' in run_insert
    assert '"rows_read":3' in run_insert
    assert '"rows_written":3' in run_insert


def test_snowflake_runtime_accepts_caller_supplied_run_id(tmp_path) -> None:
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(_append_contract()), encoding="utf-8")
    session = _ExecutingSnowflakeSession()

    result = run_snowflake_contract(contract_uri=str(contract_path), session=session, run_id="run-fixed-1")

    assert result["run_id"] == "run-fixed-1"
    assert any('"run_id": "run-fixed-1"' in command for command in session.commands)
    assert any("'run-fixed-1'" in command and '"ctrl_ingestion_runs"' in command for command in session.commands)


def test_snowflake_runtime_can_skip_query_tag_for_procedure_session(tmp_path) -> None:
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(_append_contract()), encoding="utf-8")
    session = _ExecutingSnowflakeSession()

    result = run_snowflake_contract(contract_uri=str(contract_path), session=session, set_query_tag=False)

    assert result["status"] == "SUCCESS"
    assert not any(command.startswith("ALTER SESSION SET QUERY_TAG = ") for command in session.commands)


def test_snowflake_runtime_falls_back_to_last_query_id_for_snowpark_sessions(tmp_path) -> None:
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(_append_contract()), encoding="utf-8")
    session = _ExecutingSnowflakeSession(scalars={"SELECT LAST_QUERY_ID()": "01-last"})

    result = run_snowflake_contract(contract_uri=str(contract_path), session=session, set_query_tag=False)

    assert result["status"] == "SUCCESS"
    assert result["metrics"]["write_query_id"] == "01-last"
    assert result["metrics"]["query_ids"]
    assert any(command == "SELECT LAST_QUERY_ID()" for command in session.commands)


def test_snowflake_runtime_records_lineage_and_explain_evidence(tmp_path) -> None:
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(_append_contract()), encoding="utf-8")
    session = _ExecutingSnowflakeSession(
        scalars={
            "SELECT CURRENT_WAREHOUSE()": ("COMPUTE_WH", "CONTRACTFORGE_INGEST_ROLE", "ANALYTICS", "BRONZE", "8.40.0"),
            'SELECT COUNT(*) FROM (\nSELECT * FROM "raw"."customers"': 3,
            "EXPLAIN USING TEXT": ("GlobalStats:\n  TableScan raw.customers",),
        }
    )

    result = run_snowflake_contract(contract_uri=str(contract_path), session=session)

    assert result["status"] == "SUCCESS"
    assert result["metrics"]["explain_status"] == "RECORDED"
    assert result["metrics"]["lineage_status"] == "RECORDED"
    assert any(command.startswith("EXPLAIN USING TEXT INSERT INTO") for command in session.commands)
    explain_insert = next(command for command in session.commands if '"ctrl_ingestion_explain"' in command and "INSERT INTO" in command)
    assert "'TEXT'" in explain_insert
    assert "GlobalStats" in explain_insert
    lineage_insert = next(command for command in session.commands if '"ctrl_ingestion_lineage"' in command and "INSERT INTO" in command)
    assert "'COMPLETE'" in lineage_insert
    assert "https://openlineage.io/spec/1-0-5/OpenLineage.json" in lineage_insert
    assert '"rowCount":3' in lineage_insert


def test_snowflake_runtime_explain_failure_does_not_fail_run(tmp_path) -> None:
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(
        json.dumps({**_append_contract(), "extensions": {"snowflake": {"explain_format": "TEXT"}}}),
        encoding="utf-8",
    )
    session = _RuntimeFailingSession(fail_on="EXPLAIN USING TEXT", message="explain blocked")

    result = run_snowflake_contract(contract_uri=str(contract_path), session=session)

    assert result["status"] == "SUCCESS"
    assert result["metrics"]["explain_status"] == "FAILED"
    assert "explain blocked" in result["metrics"]["explain_error"]
    assert any('"ctrl_ingestion_lineage"' in command and "INSERT INTO" in command for command in session.commands)
    assert not any('"ctrl_ingestion_explain"' in command and "INSERT INTO" in command for command in session.commands)


def test_snowflake_runtime_executes_overwrite_sql_source(tmp_path) -> None:
    contract = {
        "source": {"type": "sql", "query": "select * from raw.customers where active = true"},
        "target": {"catalog": "ANALYTICS", "schema": "BRONZE", "table": "CUSTOMERS"},
        "mode": "scd0_overwrite",
    }
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    session = _ExecutingSnowflakeSession(scalars={"select * from raw.customers where active = true": 2})

    result = run_snowflake_contract(contract_uri=str(contract_path), session=session)

    assert result["status"] == "SUCCESS"
    assert not any('CREATE TABLE IF NOT EXISTS "ANALYTICS"."BRONZE"."CUSTOMERS" AS' in command for command in session.commands)
    assert any('CREATE OR REPLACE TABLE "ANALYTICS"."BRONZE"."CUSTOMERS" AS' in command for command in session.commands)
    assert any("select * from raw.customers where active = true" in command for command in session.commands)
    run_insert = next(command for command in session.commands if '"ctrl_ingestion_runs"' in command and "INSERT INTO" in command)
    assert '"rows_written":2' in run_insert
    assert '"rows_inserted":2' in run_insert


def test_snowflake_runtime_executes_staged_files_source(tmp_path) -> None:
    contract = {
        "source": {
            "type": "staged_files",
            "path": "@RAW_STAGE/customers/",
            "format": "csv",
            "options": {
                "file_format": "RAW_CSV_FORMAT",
                "pattern": ".*[.]csv",
                "columns": {"customer_id": "$1::NUMBER", "name": "$2::STRING"},
            },
        },
        "target": {"catalog": "ANALYTICS", "schema": "BRONZE", "table": "CUSTOMERS"},
        "mode": "scd0_append",
    }
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    session = _ExecutingSnowflakeSession(columns=("customer_id", "name"))

    result = run_snowflake_contract(contract_uri=str(contract_path), session=session)

    assert result["status"] == "SUCCESS"
    assert any('FROM @RAW_STAGE/customers/ (FILE_FORMAT => \'RAW_CSV_FORMAT\', PATTERN => \'.*[.]csv\') AS _CF_STAGE' in command for command in session.commands)
    assert any('$1::NUMBER AS "customer_id"' in command for command in session.commands)
    assert any('INSERT INTO "ANALYTICS"."BRONZE"."CUSTOMERS"' in command for command in session.commands)


def test_snowflake_runtime_records_state_for_successful_run(tmp_path) -> None:
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(_append_contract()), encoding="utf-8")
    session = _ExecutingSnowflakeSession()

    result = run_snowflake_contract(contract_uri=str(contract_path), session=session)

    assert result["status"] == "SUCCESS"
    assert any('"ctrl_ingestion_state"' in command and "INSERT INTO" in command for command in session.commands)
    assert any("'SUCCESS'" in command and result["run_id"] in command for command in session.commands if '"ctrl_ingestion_state"' in command)


def test_snowflake_runtime_applies_previous_incremental_watermark_and_records_candidate(tmp_path) -> None:
    contract = {
        "source": {
            "type": "table",
            "table": "raw.customers",
            "incremental": {"watermark_column": "updated_at"},
        },
        "target": {"catalog": "ANALYTICS", "schema": "BRONZE", "table": "CUSTOMERS"},
        "mode": "scd0_append",
    }
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    session = _ExecutingSnowflakeSession(
        scalars={
            'SELECT "watermark_value" FROM': "2026-01-01 00:00:00",
            'SELECT MAX("updated_at")': "2026-01-02 00:00:00",
        }
    )

    result = run_snowflake_contract(contract_uri=str(contract_path), session=session)

    assert result["status"] == "SUCCESS"
    assert any('"ctrl_ingestion_state"' in command and 'ORDER BY "last_updated_at_utc" DESC' in command for command in session.commands)
    assert any('"updated_at" > \'2026-01-01 00:00:00\'' in command for command in session.commands)
    assert any('SELECT MAX("updated_at")' in command for command in session.commands)
    assert any("'2026-01-02 00:00:00'" in command for command in session.commands if '"ctrl_ingestion_state"' in command)


def test_snowflake_runtime_skips_successful_idempotency_key(tmp_path) -> None:
    contract = {
        **_append_contract(),
        "idempotency_key": "orders:batch:1",
        "idempotency_policy": "skip_if_success",
    }
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    session = _ExecutingSnowflakeSession(
        scalars={
            'FROM "CONTRACTFORGE"."CF_EVIDENCE"."ctrl_ingestion_runs"': ("prior-run", "SUCCESS"),
        }
    )

    result = run_snowflake_contract(contract_uri=str(contract_path), session=session)

    assert result["status"] == "SKIPPED"
    assert result["skip_reason"] == "idempotency_key_already_succeeded"
    assert result["metrics"]["skipped_by_run_id"] == "prior-run"
    assert any('"idempotency_key" = \'orders:batch:1\'' in command for command in session.commands)
    assert any('"ctrl_ingestion_runs"' in command and "'SKIPPED'" in command and "'prior-run'" in command for command in session.commands)
    assert not any('INSERT INTO "ANALYTICS"."BRONZE"."CUSTOMERS"' in command for command in session.commands)


def test_snowflake_runtime_acquires_and_releases_lock(tmp_path) -> None:
    contract = {
        **_append_contract(),
        "extensions": {"snowflake": {"lock_enabled": True, "lock_owner": "job-1", "lock_ttl_minutes": 15}},
    }
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    session = _ExecutingSnowflakeSession()

    result = run_snowflake_contract(contract_uri=str(contract_path), session=session)

    assert result["status"] == "SUCCESS"
    assert any('MERGE INTO "CONTRACTFORGE"."CF_EVIDENCE"."ctrl_ingestion_locks"' in command for command in session.commands)
    assert any("DATEADD(minute, 15" in command and "'job-1'" in command for command in session.commands)
    assert any('UPDATE "CONTRACTFORGE"."CF_EVIDENCE"."ctrl_ingestion_locks"' in command and '"status" = \'RELEASED\'' in command for command in session.commands)


def test_snowflake_runtime_releases_lock_and_records_state_on_failure(tmp_path) -> None:
    contract = {
        **_append_contract(),
        "extensions": {"snowflake": {"lock_enabled": True}},
    }
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    session = _RuntimeFailingSession(fail_on='INSERT INTO "ANALYTICS"', message="write failed")

    with pytest.raises(RuntimeError, match="write failed"):
        run_snowflake_contract(contract_uri=str(contract_path), session=session)

    assert any('UPDATE "CONTRACTFORGE"."CF_EVIDENCE"."ctrl_ingestion_locks"' in command and '"status" = \'RELEASED\'' in command for command in session.commands)
    assert any('"ctrl_ingestion_state"' in command and "'FAILED'" in command and "write failed" in command for command in session.commands)


def test_snowflake_lock_release_reports_redacted_failure() -> None:
    from contractforge_snowflake.state import release_snowflake_lock

    session = _LockReleaseFailingSession()
    result = release_snowflake_lock(
        session=session,
        environment=SnowflakeEnvironment.from_contract(
            {"evidence": {"database": "CONTRACTFORGE", "schema": "CF_EVIDENCE"}}
        ),
        target_table='"ANALYTICS"."BRONZE"."CUSTOMERS"',
        run_id="run-123",
    )

    assert result.status == "FAILED"
    assert result.commands
    assert result.warning is not None
    assert result.warning.startswith("lock_release_failed: RuntimeError:")
    assert "raw-secret" not in result.warning
    assert "***REDACTED***" in result.warning


def test_snowflake_runtime_rejects_unsafe_incremental_watermark_column(tmp_path) -> None:
    contract = {
        **_append_contract(),
        "source": {
            "type": "table",
            "table": "raw.customers",
            "incremental": {"watermark_column": "updated_at); DROP TABLE x; --"},
        },
    }
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    with pytest.raises(ValueError, match="watermark_column must be a simple identifier"):
        run_snowflake_contract(contract_uri=str(contract_path), session=_ExecutingSnowflakeSession())


def test_snowflake_runtime_executes_sql_compatible_shape_and_transform(tmp_path) -> None:
    contract = {
        "source": {"type": "table", "table": "raw.customers"},
        "target": {"catalog": "ANALYTICS", "schema": "SILVER", "table": "CUSTOMERS"},
        "mode": "scd1_hash_diff",
        "merge_keys": ["customer_id"],
        "hash_keys": ["email_domain"],
        "shape": {
            "columns": {
                "customer_id": {"expression": "id", "cast": "NUMBER"},
                "email": "email",
                "updated_at": "updated_at",
            }
        },
        "transform": {
            "standardize": {"email": {"trim": True, "lower": True}},
            "derive": {"email_domain": "SPLIT_PART(email, '@', 2)"},
            "deduplicate": {"keys": ["customer_id"], "order_by": [{"column": "updated_at", "direction": "desc"}]},
        },
    }
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    session = _ExecutingSnowflakeSession(columns=("customer_id", "email", "updated_at", "email_domain"))

    result = run_snowflake_contract(contract_uri=str(contract_path), session=session)

    assert result["status"] == "SUCCESS"
    assert any('CAST(id AS NUMBER) AS "customer_id"' in command for command in session.commands)
    assert any('LOWER(TRIM("email")) AS "email"' in command for command in session.commands)
    assert any("SPLIT_PART(\"email\", '@', 2) AS \"email_domain\"" in command for command in session.commands)
    assert any('QUALIFY ROW_NUMBER() OVER (PARTITION BY "customer_id" ORDER BY "updated_at" DESC) = 1' in command for command in session.commands)
    assert any('MERGE INTO "ANALYTICS"."SILVER"."CUSTOMERS" AS target' in command for command in session.commands)


def test_snowflake_runtime_requires_session_for_execution(tmp_path) -> None:
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(_append_contract()), encoding="utf-8")

    with pytest.raises(ValueError, match="requires a Snowflake session"):
        run_snowflake_contract(contract_uri=str(contract_path))


def test_snowflake_runtime_executes_scd1_upsert(tmp_path) -> None:
    contract = {
        "source": {"type": "table", "table": "raw.customers"},
        "target": {"catalog": "ANALYTICS", "schema": "SILVER", "table": "CUSTOMERS"},
        "mode": "scd1_upsert",
        "merge_keys": ["customer_id"],
    }
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    session = _ExecutingSnowflakeSession(
        columns=("customer_id", "name", "email"),
        scalars={
            'WHERE "customer_id" IS NULL': 0,
            "HAVING COUNT(*) > 1": 0,
            'SELECT COUNT(*) FROM (\nSELECT * FROM "raw"."customers"': 4,
        },
    )

    result = run_snowflake_contract(contract_uri=str(contract_path), session=session)

    assert result["status"] == "SUCCESS"
    assert any('CREATE TABLE IF NOT EXISTS "ANALYTICS"."SILVER"."CUSTOMERS" AS' in command for command in session.commands)
    assert any('MERGE INTO "ANALYTICS"."SILVER"."CUSTOMERS" AS target' in command for command in session.commands)
    assert any('target."customer_id" = source."customer_id"' in command for command in session.commands)
    assert any('target."name" = source."name"' in command for command in session.commands)
    run_insert = next(command for command in session.commands if '"ctrl_ingestion_runs"' in command and "INSERT INTO" in command)
    assert '"rows_written":4' in run_insert
    assert '"rows_affected":null' in run_insert


def test_snowflake_runtime_executes_scd1_hash_diff(tmp_path) -> None:
    contract = {
        "source": {"type": "table", "table": "raw.customers"},
        "target": {"catalog": "ANALYTICS", "schema": "SILVER", "table": "CUSTOMERS"},
        "mode": "scd1_hash_diff",
        "merge_keys": ["customer_id"],
        "hash_keys": ["name", "email"],
    }
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    session = _ExecutingSnowflakeSession(
        columns=("customer_id", "name", "email", "loaded_at"),
        scalars={"LEFT JOIN \"ANALYTICS\".\"SILVER\".\"CUSTOMERS\" AS target": 2},
    )

    result = run_snowflake_contract(contract_uri=str(contract_path), session=session)

    assert result["status"] == "SUCCESS"
    assert result["metrics"]["hash_diff_candidate_rows"] == 2
    assert any('CREATE TABLE IF NOT EXISTS "ANALYTICS"."SILVER"."CUSTOMERS" AS' in command for command in session.commands)
    assert any(
        'WHERE (target."customer_id" IS NULL) OR (HASH(target."name", target."email") <> HASH(source."name", source."email"))'
        in command
        for command in session.commands
    )
    assert any("WHEN MATCHED AND HASH(target.\"name\", target.\"email\") <> HASH(source.\"name\", source.\"email\")" in command for command in session.commands)


def test_snowflake_schema_policy_normalizes_quoted_snowpark_field_names() -> None:
    session = _ExecutingSnowflakeSession(
        columns=('\"customer_id\"', '\"segment\"', '\"balance\"', '\"updated_at\"', '\"loaded_at\"'),
        column_types={
            '\"customer_id\"': "LongType()",
            '\"segment\"': "StringType(50331648)",
            '\"balance\"': "DecimalType(18, 2)",
            '\"updated_at\"': "TimestampType(timezone=TimestampTimeZone('NTZ'))",
            '\"loaded_at\"': "TimestampType(timezone=TimestampTimeZone('LTZ'))",
        },
    )

    assert source_column_types_for(session, 'SELECT "customer_id", "balance" FROM "raw"."customers"') == {
        "customer_id": "NUMBER",
        "segment": "VARCHAR",
        "balance": "NUMBER",
        "updated_at": "TIMESTAMP_NTZ",
        "loaded_at": "TIMESTAMP_LTZ",
    }


def test_snowflake_runtime_rejects_null_merge_keys_before_merge(tmp_path) -> None:
    contract = {
        "source": {"type": "table", "table": "raw.customers"},
        "target": {"catalog": "ANALYTICS", "schema": "SILVER", "table": "CUSTOMERS"},
        "mode": "scd1_upsert",
        "merge_keys": ["customer_id"],
    }
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    session = _ExecutingSnowflakeSession(columns=("customer_id", "name"), scalars={'WHERE "customer_id" IS NULL': 2})

    with pytest.raises(ValueError, match="contains 2 rows with null merge_keys"):
        run_snowflake_contract(contract_uri=str(contract_path), session=session)

    assert any('"ctrl_ingestion_errors"' in command and "null merge_keys" in command for command in session.commands)
    assert not any('MERGE INTO "ANALYTICS"."SILVER"."CUSTOMERS"' in command for command in session.commands)


def test_snowflake_merge_key_validation_runs_before_quality_quarantine(tmp_path) -> None:
    contract = {
        "source": {"type": "table", "table": "raw.customers"},
        "target": {"catalog": "ANALYTICS", "schema": "SILVER", "table": "CUSTOMERS"},
        "mode": "scd1_hash_diff",
        "merge_keys": ["customer_id"],
        "hash_keys": ["name"],
        "quality_rules": {"not_null": ["customer_id"]},
    }
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    session = _ExecutingSnowflakeSession(columns=("customer_id", "name"), scalars={'WHERE "customer_id" IS NULL': 1})

    with pytest.raises(ValueError, match="contains 1 rows with null merge_keys"):
        run_snowflake_contract(contract_uri=str(contract_path), session=session)

    validation_at = next(index for index, command in enumerate(session.commands) if 'WHERE "customer_id" IS NULL' in command)
    assert not any('INSERT INTO "CONTRACTFORGE"."CF_AUDIT"."ctrl_ingestion_quarantine"' in command for command in session.commands[: validation_at + 1])
    assert not any('MERGE INTO "ANALYTICS"."SILVER"."CUSTOMERS"' in command for command in session.commands)


def test_snowflake_runtime_rejects_duplicate_merge_keys_before_hash_diff_merge(tmp_path) -> None:
    contract = {
        "source": {"type": "table", "table": "raw.customers"},
        "target": {"catalog": "ANALYTICS", "schema": "SILVER", "table": "CUSTOMERS"},
        "mode": "scd1_hash_diff",
        "merge_keys": ["customer_id"],
        "hash_keys": ["name"],
    }
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    session = _ExecutingSnowflakeSession(columns=("customer_id", "name"), scalars={"HAVING COUNT(*) > 1": 1})

    with pytest.raises(ValueError, match="contains duplicate merge_keys"):
        run_snowflake_contract(contract_uri=str(contract_path), session=session)

    assert any('"ctrl_ingestion_errors"' in command and "duplicate merge_keys" in command for command in session.commands)
    assert not any('MERGE INTO "ANALYTICS"."SILVER"."CUSTOMERS"' in command for command in session.commands)


def test_snowflake_runtime_rejects_review_required_write_mode(tmp_path) -> None:
    contract = {
        "source": {"type": "table", "table": "raw.customers"},
        "target": {"catalog": "ANALYTICS", "schema": "SILVER", "table": "CUSTOMERS"},
        "mode": "scd2_historical",
        "merge_keys": ["customer_id"],
    }
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    with pytest.raises(RuntimeError, match="not executable with planning status REVIEW_REQUIRED"):
        run_snowflake_contract(contract_uri=str(contract_path), session=_ExecutingSnowflakeSession())


def test_snowflake_runtime_records_error_evidence_for_execution_failure(tmp_path) -> None:
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(_append_contract()), encoding="utf-8")
    session = _RuntimeFailingSession(fail_on="INSERT INTO \"ANALYTICS\"", message="runtime write failed password=raw-secret")

    with pytest.raises(RuntimeError, match="runtime write failed") as exc:
        run_snowflake_contract(contract_uri=str(contract_path), session=session)

    notes = getattr(exc.value, "__notes__", (getattr(exc.value, "_contractforge_note", ""),))
    assert any("ContractForge Snowflake run_id=" in note for note in notes)
    assert any('"ctrl_ingestion_errors"' in command and "runtime write failed" in command for command in session.commands)
    assert not any("raw-secret" in command for command in session.commands)
    assert any('"ctrl_ingestion_runs"' in command and "'FAILED'" in command for command in session.commands)


def test_snowflake_runtime_aborts_failed_quality_rule_and_records_evidence(tmp_path) -> None:
    contract = {
        "source": {"type": "table", "table": "raw.customers"},
        "target": {"catalog": "ANALYTICS", "schema": "BRONZE", "table": "CUSTOMERS"},
        "mode": "scd0_append",
        "quality_rules": {"min_rows": 10},
    }
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    session = _ExecutingSnowflakeSession(scalars={"SELECT COUNT(*)": 3})

    with pytest.raises(RuntimeError, match="Snowflake quality rule failed: min_rows"):
        run_snowflake_contract(contract_uri=str(contract_path), session=session)

    assert any('"ctrl_ingestion_quality"' in command and "'FAILED'" in command for command in session.commands)
    assert any('"ctrl_ingestion_errors"' in command and "Snowflake quality rule failed" in command for command in session.commands)
    assert not any('INSERT INTO "ANALYTICS"."BRONZE"."CUSTOMERS"' in command for command in session.commands)


def test_snowflake_runtime_quotes_known_columns_in_quality_expressions(tmp_path) -> None:
    contract = {
        "source": {"type": "table", "table": "raw.customers"},
        "target": {"catalog": "ANALYTICS", "schema": "BRONZE", "table": "CUSTOMERS"},
        "mode": "scd0_append",
        "quality_rules": {
            "expressions": [
                {"name": "non_negative_balance", "expression": "balance >= 0", "severity": "abort"}
            ]
        },
    }
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    session = _ExecutingSnowflakeSession(columns=("customer_id", "balance"))

    result = run_snowflake_contract(contract_uri=str(contract_path), session=session)

    assert result["status"] == "SUCCESS"
    assert any('WHERE NOT ("balance" >= 0) OR ("balance" >= 0) IS NULL' in command for command in session.commands)


def test_snowflake_runtime_quality_resolves_unquoted_sql_alias_case(tmp_path) -> None:
    contract = {
        "source": {"type": "sql", "query": "SELECT 1 AS movie_id, 'Dune' AS title"},
        "target": {"catalog": "ANALYTICS", "schema": "SILVER", "table": "MOVIES"},
        "mode": "scd0_overwrite",
        "quality_rules": {"not_null": ["movie_id"], "unique_key": ["movie_id"]},
    }
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    session = _ExecutingSnowflakeSession(columns=("MOVIE_ID", "TITLE"))

    result = run_snowflake_contract(contract_uri=str(contract_path), session=session)

    assert result["status"] == "SUCCESS"
    assert any('WHERE "MOVIE_ID" IS NULL' in command for command in session.commands)
    assert any('SELECT "MOVIE_ID", COUNT(*) AS _CF_COUNT' in command for command in session.commands)


def test_snowflake_runtime_quarantines_row_level_quality_failures(tmp_path) -> None:
    contract = {
        "source": {"type": "table", "table": "raw.customers"},
        "target": {"catalog": "ANALYTICS", "schema": "BRONZE", "table": "CUSTOMERS"},
        "mode": "scd0_append",
        "quality_rules": {"not_null": ["customer_id"]},
    }
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    session = _ExecutingSnowflakeSession(
        scalars={
            'WHERE NOT ("customer_id" IS NULL)': 1,
            'WHERE "customer_id" IS NULL': 2,
            "SELECT COUNT(*) FROM (": 3,
        }
    )

    result = run_snowflake_contract(contract_uri=str(contract_path), session=session)

    assert result["status"] == "SUCCESS"
    assert result["metrics"]["quality_status"] == "QUARANTINED"
    assert result["metrics"]["rows_read"] == 3
    assert result["metrics"]["rows_written"] == 1
    assert result["metrics"]["rows_inserted"] == 1
    assert result["metrics"]["rows_quarantined"] == 2
    assert result["metrics"]["quality_results"][0]["rule_name"] == "customer_id_not_null"
    assert result["metrics"]["quality_results"][0]["failed_count"] == 2
    assert any('"ctrl_ingestion_quality"' in command and "'FAILED'" in command for command in session.commands)
    assert any('"ctrl_ingestion_quarantine"' in command and '"customer_id" IS NULL' in command for command in session.commands)
    assert any('WHERE NOT ("customer_id" IS NULL)' in command and 'INSERT INTO "ANALYTICS"."BRONZE"."CUSTOMERS"' in command for command in session.commands)
    assert any('"ctrl_ingestion_runs"' in command and "'QUARANTINED'" in command for command in session.commands)


def test_snowflake_runtime_records_warn_quality_summary_in_run_evidence(tmp_path) -> None:
    contract = {
        "source": {"type": "table", "table": "raw.customers"},
        "target": {"catalog": "ANALYTICS", "schema": "BRONZE", "table": "CUSTOMERS"},
        "mode": "scd0_append",
        "quality_rules": {"max_null_ratio": {"email": 0.1}},
    }
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    session = _ExecutingSnowflakeSession(scalars={"AVG(IFF": 0.5})

    result = run_snowflake_contract(contract_uri=str(contract_path), session=session)

    assert result["status"] == "SUCCESS"
    assert result["metrics"]["quality_status"] == "WARNED"
    assert result["metrics"]["quality_results"] == [
        {
            "rule_name": "email_max_null_ratio",
            "rule": "max_null_ratio",
            "columns": ["email"],
            "severity": "warn",
            "status": "FAILED",
            "failed_count": 1,
            "observed_value": 0.5,
            "row_level": False,
        }
    ]
    assert any('"ctrl_ingestion_quality"' in command and "'warn'" in command and "'FAILED'" in command for command in session.commands)
    assert any('"ctrl_ingestion_runs"' in command and "'WARNED'" in command and '"quality_results"' in command for command in session.commands)


def test_snowflake_runtime_rejects_aggregate_quarantine_without_row_filter(tmp_path) -> None:
    contract = {
        "source": {"type": "table", "table": "raw.customers"},
        "target": {"catalog": "ANALYTICS", "schema": "BRONZE", "table": "CUSTOMERS"},
        "mode": "scd0_append",
        "quality_rules": {
            "expressions": [
                {"name": "min_dataset_size", "expression": "COUNT(*) > 10", "severity": "quarantine"},
            ]
        },
    }
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    session = _ExecutingSnowflakeSession(scalars={"COUNT(*) > 10": 1})

    with pytest.raises(RuntimeError, match="cannot quarantine rows"):
        run_snowflake_contract(contract_uri=str(contract_path), session=session)


def test_snowflake_runtime_enforces_strict_schema_policy(tmp_path) -> None:
    contract = {
        "source": {"type": "table", "table": "raw.customers"},
        "target": {"catalog": "ANALYTICS", "schema": "BRONZE", "table": "CUSTOMERS"},
        "mode": "scd0_append",
        "schema_policy": "strict",
    }
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    session = _ExecutingSnowflakeSession(columns=("customer_id", "name", "extra_col"), target_columns=("customer_id", "name"))

    with pytest.raises(ValueError, match="strict schema policy violation"):
        run_snowflake_contract(contract_uri=str(contract_path), session=session)

    assert any('"ctrl_ingestion_errors"' in command and "strict schema policy violation" in command for command in session.commands)


def test_snowflake_runtime_enforces_additive_only_removed_columns(tmp_path) -> None:
    contract = {
        "source": {"type": "table", "table": "raw.customers"},
        "target": {"catalog": "ANALYTICS", "schema": "BRONZE", "table": "CUSTOMERS"},
        "mode": "scd0_append",
        "schema_policy": "additive_only",
    }
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    session = _ExecutingSnowflakeSession(columns=("customer_id",), target_columns=("customer_id", "name"))

    with pytest.raises(ValueError, match="additive_only schema policy violation"):
        run_snowflake_contract(contract_uri=str(contract_path), session=session)


def test_snowflake_runtime_additive_only_adds_missing_source_columns(tmp_path) -> None:
    contract = {
        "source": {"type": "table", "table": "raw.customers"},
        "target": {"catalog": "ANALYTICS", "schema": "BRONZE", "table": "CUSTOMERS"},
        "mode": "scd0_append",
        "schema_policy": "additive_only",
    }
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    session = _ExecutingSnowflakeSession(
        columns=("customer_id", "name", "email"),
        column_types={"customer_id": "NUMBER", "name": "VARCHAR", "email": "VARCHAR"},
        target_columns=("customer_id", "name"),
    )

    result = run_snowflake_contract(contract_uri=str(contract_path), session=session)

    assert result["status"] == "SUCCESS"
    assert any('ALTER TABLE "ANALYTICS"."BRONZE"."CUSTOMERS" ADD COLUMN IF NOT EXISTS "email" VARCHAR' in command for command in session.commands)
    assert any('"ctrl_ingestion_schema_changes"' in command and "'ADD_COLUMN'" in command for command in session.commands)
    assert result["metrics"]["schema_changes"]["added_columns"][0]["column"] == "email"


def test_snowflake_runtime_rejects_incompatible_schema_type_changes(tmp_path) -> None:
    contract = {
        "source": {"type": "table", "table": "raw.customers"},
        "target": {"catalog": "ANALYTICS", "schema": "BRONZE", "table": "CUSTOMERS"},
        "mode": "scd0_append",
        "schema_policy": "additive_only",
    }
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    session = _ExecutingSnowflakeSession(
        columns=("customer_id", "email"),
        column_types={"customer_id": "NUMBER", "email": "VARCHAR"},
        target_columns=("customer_id", "email"),
        target_column_types={"customer_id": "NUMBER", "email": "NUMBER"},
    )

    with pytest.raises(ValueError, match="incompatible type changes"):
        run_snowflake_contract(contract_uri=str(contract_path), session=session)


def test_snowflake_runtime_applies_annotations_and_records_evidence(tmp_path) -> None:
    contract = {
        **_append_contract(),
        "annotations": {
            "table": {"description": "Curated customers", "tags": {"domain": "crm"}},
            "columns": {
                "email": {
                    "description": "Customer email",
                    "pii": {"enabled": True, "type": "email", "sensitivity": "confidential"},
                }
            },
        },
    }
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    session = _ExecutingSnowflakeSession()

    result = run_snowflake_contract(contract_uri=str(contract_path), session=session)

    assert result["status"] == "SUCCESS"
    assert any('COMMENT ON TABLE "ANALYTICS"."BRONZE"."CUSTOMERS" IS' in command for command in session.commands)
    assert any('COMMENT ON COLUMN "ANALYTICS"."BRONZE"."CUSTOMERS"."email" IS' in command for command in session.commands)
    assert any('ALTER TABLE "ANALYTICS"."BRONZE"."CUSTOMERS" SET TAG "domain" = ' in command for command in session.commands)
    assert any('ALTER TABLE "ANALYTICS"."BRONZE"."CUSTOMERS" ALTER COLUMN "email" SET TAG "pii_enabled" = ' in command for command in session.commands)
    assert any('"ctrl_ingestion_annotations"' in command and "'APPLIED'" in command for command in session.commands)


def test_snowflake_runtime_annotation_warn_policy_records_failed_tag_and_continues(tmp_path) -> None:
    contract = {
        **_append_contract(),
        "annotations": {
            "policy": "warn",
            "table": {"tags": {"missing_tag": "value"}},
        },
    }
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    session = _AnnotationTagFailingSession()

    result = run_snowflake_contract(contract_uri=str(contract_path), session=session)

    assert result["status"] == "SUCCESS"
    assert any('"ctrl_ingestion_annotations"' in command and "'FAILED'" in command for command in session.commands)
    assert any('INSERT INTO "ANALYTICS"."BRONZE"."CUSTOMERS"' in command for command in session.commands)


def test_snowflake_runtime_annotation_fail_policy_raises_after_evidence(tmp_path) -> None:
    contract = {
        **_append_contract(),
        "annotations": {
            "policy": "fail",
            "table": {"tags": {"missing_tag": "value"}},
        },
    }
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    session = _AnnotationTagFailingSession()

    with pytest.raises(RuntimeError, match="tag object does not exist"):
        run_snowflake_contract(contract_uri=str(contract_path), session=session)

    assert any('"ctrl_ingestion_annotations"' in command and "'FAILED'" in command for command in session.commands)
    assert not any("raw-secret" in command for command in session.commands)


def test_snowflake_runtime_annotation_ignore_policy_skips_steps(tmp_path) -> None:
    contract = {
        **_append_contract(),
        "annotations": {
            "policy": "ignore",
            "table": {"description": "Curated customers", "tags": {"domain": "crm"}},
        },
    }
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    session = _ExecutingSnowflakeSession()

    result = run_snowflake_contract(contract_uri=str(contract_path), session=session)

    assert result["status"] == "SUCCESS"
    assert not any(command.startswith("COMMENT ON") for command in session.commands)
    assert not any(command.startswith("ALTER TABLE") and " SET TAG " in command for command in session.commands)


def test_snowflake_runtime_annotation_validate_only_tags_record_evidence_without_apply(tmp_path) -> None:
    contract = {
        **_append_contract(),
        "extensions": {"snowflake": {"annotation_tag_mode": "validate_only"}},
        "annotations": {
            "table": {"description": "Curated customers", "tags": {"GOVERNANCE.PUBLIC.DOMAIN": "crm"}},
            "columns": {"email": {"tags": {"GOVERNANCE.PUBLIC.CLASSIFICATION": "restricted"}}},
        },
    }
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    session = _ExecutingSnowflakeSession()

    result = run_snowflake_contract(contract_uri=str(contract_path), session=session)

    assert result["status"] == "SUCCESS"
    assert any('COMMENT ON TABLE "ANALYTICS"."BRONZE"."CUSTOMERS" IS' in command for command in session.commands)
    assert not any(command.startswith("ALTER TABLE") and " SET TAG " in command for command in session.commands)
    assert any('"ctrl_ingestion_annotations"' in command and "'VALIDATED'" in command for command in session.commands)
    assert any('"GOVERNANCE"."PUBLIC"."DOMAIN"' in command for command in session.commands if '"ctrl_ingestion_annotations"' in command)


def test_snowflake_annotation_evidence_redacts_secret_values(tmp_path) -> None:
    contract = {
        **_append_contract(),
        "extensions": {"snowflake": {"annotation_tag_mode": "validate_only"}},
        "annotations": {
            "table": {"tags": {"SECURITY.PUBLIC.TOKEN": "password=raw-secret"}},
        },
    }
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    session = _ExecutingSnowflakeSession()

    result = run_snowflake_contract(contract_uri=str(contract_path), session=session)

    assert result["status"] == "SUCCESS"
    assert any('"ctrl_ingestion_annotations"' in command and "***REDACTED***" in command for command in session.commands)
    assert not any("raw-secret" in command for command in session.commands)


def test_snowflake_runtime_applies_access_grants_and_records_evidence(tmp_path) -> None:
    contract = {
        **_append_contract(),
        "access": {
            "grants": [
                {"principal": "ANALYST_ROLE", "privileges": ["select", "references"]},
            ]
        },
    }
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    session = _ExecutingSnowflakeSession()

    result = run_snowflake_contract(contract_uri=str(contract_path), session=session)

    assert result["status"] == "SUCCESS"
    assert any('GRANT SELECT ON TABLE "ANALYTICS"."BRONZE"."CUSTOMERS" TO ROLE "ANALYST_ROLE"' in command for command in session.commands)
    assert any('GRANT REFERENCES ON TABLE "ANALYTICS"."BRONZE"."CUSTOMERS" TO ROLE "ANALYST_ROLE"' in command for command in session.commands)
    assert any('"ctrl_ingestion_access"' in command and "'APPLIED'" in command for command in session.commands)


def test_snowflake_runtime_validate_only_access_records_without_grant(tmp_path) -> None:
    contract = {
        **_append_contract(),
        "access": {
            "mode": "validate_only",
            "grants": [{"principal": "ANALYST_ROLE", "privileges": "select"}],
        },
    }
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    session = _ExecutingSnowflakeSession()

    result = run_snowflake_contract(contract_uri=str(contract_path), session=session)

    assert result["status"] == "SUCCESS"
    assert not any(command.startswith("GRANT SELECT") for command in session.commands)
    assert any('"ctrl_ingestion_access"' in command and "'VALIDATED'" in command for command in session.commands)


def test_snowflake_runtime_applies_row_access_and_masking_policies(tmp_path) -> None:
    contract = {
        **_append_contract(),
        "access": {
            "row_filters": [
                {
                    "name": "region_filter",
                    "function": "SECURITY.POLICIES.REGION_ROW_ACCESS",
                    "columns": ["region"],
                    "applies_to": {"principals": ["ANALYST_ROLE"]},
                }
            ],
            "column_masks": [
                {
                    "column": "email",
                    "function": "SECURITY.POLICIES.EMAIL_MASK",
                    "using_columns": ["region"],
                    "applies_to": {"principals": ["ANALYST_ROLE"]},
                }
            ],
        },
    }
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    session = _ExecutingSnowflakeSession()

    result = run_snowflake_contract(contract_uri=str(contract_path), session=session)

    assert result["status"] == "SUCCESS"
    assert any(
        'ALTER TABLE "ANALYTICS"."BRONZE"."CUSTOMERS" ADD ROW ACCESS POLICY "SECURITY"."POLICIES"."REGION_ROW_ACCESS" ON ("region")'
        in command
        for command in session.commands
    )
    assert any(
        'ALTER TABLE "ANALYTICS"."BRONZE"."CUSTOMERS" MODIFY COLUMN "email" SET MASKING POLICY "SECURITY"."POLICIES"."EMAIL_MASK" USING ("email", "region")'
        in command
        for command in session.commands
    )
    assert any('"ctrl_ingestion_access"' in command and "'APPLIED'" in command for command in session.commands)


def test_snowflake_runtime_validate_only_access_records_policy_steps_without_apply(tmp_path) -> None:
    contract = {
        **_append_contract(),
        "access": {
            "mode": "validate_only",
            "row_filters": [{"name": "region_filter", "function": "SECURITY.RAP", "columns": "region"}],
            "column_masks": {"email": {"function": "SECURITY.EMAIL_MASK"}},
        },
    }
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    session = _ExecutingSnowflakeSession()

    result = run_snowflake_contract(contract_uri=str(contract_path), session=session)

    assert result["status"] == "SUCCESS"
    assert not any(command.startswith("ALTER TABLE") and "ADD ROW ACCESS POLICY" in command for command in session.commands)
    assert not any(command.startswith("ALTER TABLE") and "SET MASKING POLICY" in command for command in session.commands)
    assert any('"ctrl_ingestion_access"' in command and "'VALIDATED'" in command for command in session.commands)


def test_snowflake_runtime_validate_only_access_accepts_column_mask_mapping(tmp_path) -> None:
    contract = {
        **_append_contract(),
        "access": {
            "mode": "validate_only",
            "column_masks": {"email": {"function": "SECURITY.POLICIES.EMAIL_MASK", "using_columns": ["region"]}},
        },
    }
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    session = _ExecutingSnowflakeSession()

    result = run_snowflake_contract(contract_uri=str(contract_path), session=session)

    assert result["status"] == "SUCCESS"
    assert not any(command.startswith("ALTER TABLE") and "SET MASKING POLICY" in command for command in session.commands)
    assert any(
        '"ctrl_ingestion_access"' in command
        and "'VALIDATED'" in command
        and "SECURITY.POLICIES.EMAIL_MASK" in command
        and "'email'" in command
        for command in session.commands
    )


def test_snowflake_access_evidence_redacts_secret_values(tmp_path) -> None:
    contract = {
        **_append_contract(),
        "access": {
            "mode": "validate_only",
            "grants": [{"principal": "password=raw-secret", "privileges": "select"}],
        },
    }
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    session = _ExecutingSnowflakeSession()

    result = run_snowflake_contract(contract_uri=str(contract_path), session=session)

    assert result["status"] == "SUCCESS"
    assert any('"ctrl_ingestion_access"' in command and "***REDACTED***" in command for command in session.commands)
    assert not any("raw-secret" in command for command in session.commands)


def test_snowflake_access_revoke_unmanaged_requires_review(tmp_path) -> None:
    contract = {
        **_append_contract(),
        "access": {
            "access_policy": {"mode": "apply", "on_drift": "reconcile", "revoke_unmanaged": True},
            "grants": [{"principal": "ANALYST_ROLE", "privileges": "select"}],
        },
    }
    planning = plan_snowflake_contract(contract)

    assert planning.status == "REVIEW_REQUIRED"
    assert "SNOWFLAKE_ACCESS_REVOKE_REVIEW_REQUIRED" in {warning.code for warning in planning.warnings}

    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    session = _ExecutingSnowflakeSession()
    with pytest.raises(RuntimeError, match="REVIEW_REQUIRED"):
        run_snowflake_contract(contract_uri=str(contract_path), session=session)


def test_snowflake_runtime_records_operations_metadata(tmp_path) -> None:
    contract = {
        **_append_contract(),
        "operations": {
            "criticality": "high",
            "expected_frequency": "daily",
            "freshness_sla_minutes": 90,
            "alert_on_failure": True,
            "owners": ["data-platform"],
            "groups": "analytics|support",
            "tags": {"tier": "gold"},
        },
    }
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    session = _ExecutingSnowflakeSession()

    result = run_snowflake_contract(contract_uri=str(contract_path), session=session)

    assert result["status"] == "SUCCESS"
    assert any('"ctrl_ingestion_operations"' in command and "'RECORDED'" in command for command in session.commands)
    assert any('"ctrl_ingestion_operations"' in command and "'high'" in command and "'daily'" in command for command in session.commands)


def test_snowflake_runtime_query_tag_is_parseable_json(tmp_path) -> None:
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(_append_contract()), encoding="utf-8")
    session = _ExecutingSnowflakeSession()

    result = run_snowflake_contract(contract_uri=str(contract_path), session=session)

    query_tag = next(command for command in session.commands if command.startswith("ALTER SESSION SET QUERY_TAG = "))
    payload = json.loads(query_tag.split(" = '", 1)[1].rsplit("'", 1)[0])
    assert payload["run_id"] == result["run_id"]
    assert payload["target"] == "ANALYTICS.BRONZE.CUSTOMERS"
    assert '"' not in payload["target"]


def test_snowflake_cost_reconciliation_records_query_history_signals() -> None:
    session = _ExecutingSnowflakeSession(scalars={"COUNT(*) AS QUERY_COUNT": 2})

    result = reconcile_snowflake_cost_evidence(
        session=session,
        environment={"evidence": {"database": "CONTRACTFORGE", "schema": "CF_EVIDENCE"}},
        run_id="run-123",
        target_table='"ANALYTICS"."BRONZE"."CUSTOMERS"',
    )

    assert result.status == "RECORDED"
    assert result.query_count == 2
    assert len(result.commands) == 4
    assert result.commands[0].startswith("SELECT COUNT(*) AS QUERY_COUNT")
    assert result.commands[1].startswith('DELETE FROM "CONTRACTFORGE"."CF_EVIDENCE"."ctrl_ingestion_cost"')
    command = result.commands[2]
    assert 'INSERT INTO "CONTRACTFORGE"."CF_EVIDENCE"."ctrl_ingestion_cost"' in command
    assert "SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY" in command
    assert "TRY_PARSE_JSON(query_tag):run_id::STRING = 'run-123'" in command
    assert "'bytes_scanned'" in command
    assert "'execution_time_ms'" in command
    assert "'cloud_services_credits'" in command
    assert "'warehouse_count'" in command
    assert "SNOWFLAKE.ACCOUNT_USAGE.QUERY_ATTRIBUTION_HISTORY" in result.commands[3]
    assert "'attributed_compute_credits'" in result.commands[3]


def test_snowflake_cost_reconciliation_falls_back_to_persisted_query_ids() -> None:
    session = _ExecutingSnowflakeSession(
        scalars={
            "TRY_PARSE_JSON(query_tag):run_id": 0,
            "query_id IN": 2,
        }
    )

    result = reconcile_snowflake_cost_evidence(
        session=session,
        environment={"evidence": {"database": "CONTRACTFORGE", "schema": "CF_EVIDENCE"}},
        run_id="run-123",
        target_table='"ANALYTICS"."BRONZE"."CUSTOMERS"',
    )

    assert result.status == "RECORDED"
    assert result.query_count == 2
    assert len(result.commands) == 5
    assert "TRY_PARSE_JSON(query_tag):run_id::STRING = 'run-123'" in result.commands[0]
    assert 'FROM "CONTRACTFORGE"."CF_EVIDENCE"."ctrl_ingestion_runs",' in result.commands[1]
    assert 'TRY_PARSE_JSON("metrics_json"):query_ids' in result.commands[1]
    assert "query_id IN (" in result.commands[3]
    assert "query_id IN (" in result.commands[4]


def test_snowflake_cost_reconciliation_pending_when_query_history_is_delayed() -> None:
    session = _ExecutingSnowflakeSession(scalars={"COUNT(*) AS QUERY_COUNT": 0})

    result = reconcile_snowflake_cost_evidence(
        session=session,
        environment={"evidence": {"database": "CONTRACTFORGE", "schema": "CF_EVIDENCE"}},
        run_id="run-123",
        target_table='"ANALYTICS"."BRONZE"."CUSTOMERS"',
    )

    assert result.status == "PENDING"
    assert result.query_count == 0
    assert len(result.commands) == 2
    assert result.commands == tuple(session.commands)
    assert 'FROM "CONTRACTFORGE"."CF_EVIDENCE"."ctrl_ingestion_runs",' in result.commands[1]
    assert not any(command.startswith("INSERT INTO") for command in session.commands)


def test_snowflake_cost_reconciliation_pending_when_query_history_is_unavailable() -> None:
    connection = _FailingSnowflakeConnection()

    result = reconcile_snowflake_cost_evidence(
        session=connection,
        environment={"evidence": {"database": "CONTRACTFORGE", "schema": "CF_EVIDENCE"}},
        run_id="run-123",
        target_table='"ANALYTICS"."BRONZE"."CUSTOMERS"',
    )

    assert result.status == "PENDING"
    assert result.query_count == 0
    assert len(result.commands) == 1
    assert result.warnings
    assert result.warnings[0].startswith("query_history_unavailable: RuntimeError: upload failed")
    assert "raw-token" not in result.warnings[0]
    assert "raw-secret" not in result.warnings[0]
    assert "***REDACTED***" in result.warnings[0]
    assert not any(command.startswith("INSERT INTO") for command in connection.commands)


def test_snowflake_cost_reconciliation_redacts_attribution_warning() -> None:
    session = _FailingAttributionSnowflakeSession(scalars={"COUNT(*) AS QUERY_COUNT": 1})

    result = reconcile_snowflake_cost_evidence(
        session=session,
        environment={"evidence": {"database": "CONTRACTFORGE", "schema": "CF_EVIDENCE"}},
        run_id="run-123",
        target_table='"ANALYTICS"."BRONZE"."CUSTOMERS"',
    )

    assert result.status == "RECORDED_WITH_WARNINGS"
    assert result.warnings
    assert result.warnings[0].startswith("query_attribution_history_unavailable: RuntimeError: attribution failed")
    assert "raw-token" not in result.warnings[0]
    assert "***REDACTED***" in result.warnings[0]


def test_snowflake_cost_reconciliation_deletes_previous_signals_before_insert() -> None:
    session = _ExecutingSnowflakeSession(scalars={"COUNT(*) AS QUERY_COUNT": 1})

    result = reconcile_snowflake_cost_evidence(
        session=session,
        environment={"evidence": {"database": "CONTRACTFORGE", "schema": "CF_EVIDENCE"}},
        run_id="run-123",
        target_table='"ANALYTICS"."BRONZE"."CUSTOMERS"',
    )

    delete = result.commands[1]
    insert = result.commands[2]
    assert session.commands.index(delete) < session.commands.index(insert)
    assert '"run_id" = \'run-123\'' in delete
    assert '"target_table" = \'"ANALYTICS"."BRONZE"."CUSTOMERS"\'' in delete
    assert "'query_count'" in delete
    assert "'attributed_compute_credits'" in delete


def test_snowflake_cost_reconciliation_accepts_connector_connection() -> None:
    connection = _CostSnowflakeConnection(rows=[(1,)])

    result = reconcile_snowflake_cost_evidence(
        session=connection,
        environment=None,
        run_id="run-123",
        target_table='"ANALYTICS"."BRONZE"."CUSTOMERS"',
    )

    assert result.status == "RECORDED"
    assert result.query_count == 1
    assert connection.commands == list(result.commands)


def test_snowflake_access_history_lineage_reconciliation_pending_when_delayed() -> None:
    session = _ExecutingSnowflakeSession(scalars={"ACCESS_HISTORY_ROWS": 0})

    result = reconcile_snowflake_access_history_lineage(
        session=session,
        environment={"evidence": {"database": "CONTRACTFORGE", "schema": "CF_EVIDENCE"}},
        run_id="run-123",
    )

    assert result.status == "PENDING"
    assert result.row_count == 0
    assert len(result.commands) == 1
    assert "SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY" in result.commands[0]
    assert "TRY_PARSE_JSON(qh.query_tag):run_id::STRING = 'run-123'" in result.commands[0]
    assert not any('"ctrl_ingestion_lineage"' in command and "INSERT INTO" in command for command in session.commands)


def test_snowflake_access_history_lineage_reconciliation_records_rows() -> None:
    session = _ExecutingSnowflakeSession(scalars={"ACCESS_HISTORY_ROWS": 2})

    result = reconcile_snowflake_access_history_lineage(
        session=session,
        environment={"evidence": {"database": "CONTRACTFORGE", "schema": "CF_EVIDENCE"}},
        run_id="run-123",
    )

    assert result.status == "RECORDED"
    assert result.row_count == 2
    assert len(result.commands) == 2
    insert = result.commands[1]
    assert 'INSERT INTO "CONTRACTFORGE"."CF_EVIDENCE"."ctrl_ingestion_lineage"' in insert
    assert "'NATIVE_ACCESS_HISTORY'" in insert
    assert "ARRAY_AGG(ah.base_objects_accessed)" in insert


def test_snowflake_access_history_lineage_reconciliation_pending_when_unavailable() -> None:
    connection = _FailingSnowflakeConnection()

    result = reconcile_snowflake_access_history_lineage(
        session=connection,
        environment={"evidence": {"database": "CONTRACTFORGE", "schema": "CF_EVIDENCE"}},
        run_id="run-123",
    )

    assert result.status == "PENDING"
    assert result.warnings
    assert result.warnings[0].startswith("access_history_unavailable:")
    assert "raw-token" not in result.warnings[0]
    assert "raw-secret" not in result.warnings[0]
    assert "***REDACTED***" in result.warnings[0]


def test_snowflake_control_dashboard_sql_renders_control_tables() -> None:
    sql = render_control_dashboard_sql(database="OPS", schema="AUDIT", lookback_days=14)

    assert "-- q01_executive_kpis" in sql
    assert "-- q12_governance_artifacts" in sql
    assert '"OPS"."AUDIT"."ctrl_ingestion_runs"' in sql
    assert '"OPS"."AUDIT"."ctrl_ingestion_state"' in sql
    assert "DATEADD(day, -14, CURRENT_DATE())" in sql


def test_snowflake_control_dashboard_artifacts_include_blueprint() -> None:
    artifacts = render_control_dashboard_artifacts()

    assert set(artifacts) == {"control_tables_dashboard.sql", "control_tables_dashboard_blueprint.json"}
    assert "ContractForge Operations Command Center" in artifacts["control_tables_dashboard_blueprint.json"]
    assert "q11_state_watermarks" in artifacts["control_tables_dashboard_blueprint.json"]


def test_snowflake_control_retention_plan_for_selected_targets() -> None:
    plan = build_control_retention_plan(database="OPS", schema="AUDIT", retention_days=30, targets=("runs", "state"))

    assert [item["target"] for item in plan] == ["runs", "state"]
    assert 'DELETE FROM "OPS"."AUDIT"."ctrl_ingestion_runs"' in plan[0]["commands"][0]
    assert '"run_date" < DATEADD(day, -30, CURRENT_DATE())' in plan[0]["commands"][0]
    assert "last_updated_at_utc < DATEADD(day, -30, CURRENT_TIMESTAMP())" in plan[1]["commands"][0]


def test_snowflake_execute_control_retention_plan_supports_session_and_connection() -> None:
    session = _ExecutingSnowflakeSession()
    connection = _FakeSnowflakeConnection()
    plan = build_control_retention_plan(retention_days=7, targets=("cost",))

    session_executed = execute_control_retention_plan(session, plan)
    connection_executed = execute_control_retention_plan(connection, plan)

    assert session.commands == list(session_executed)
    assert connection.commands == list(connection_executed)
    assert "ctrl_ingestion_cost" in session_executed[0]


def test_snowflake_cli_reconcile_cost_uses_connector_connection(tmp_path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    from contractforge_snowflake import cli as cli_module

    connection = _CostSnowflakeConnection(rows=[(1,)])
    env_path = tmp_path / "snowflake.yaml"
    env_path.write_text("evidence:\n  database: CONTRACTFORGE\n  schema: CF_EVIDENCE\n", encoding="utf-8")
    monkeypatch.setattr(cli_module, "_connect", lambda _options: connection)

    exit_code = snowflake_cli_main(
        [
            "reconcile-cost",
            "--run-id",
            "run-123",
            "--target-table",
            '"ANALYTICS"."BRONZE"."CUSTOMERS"',
            "--environment",
            str(env_path),
            "--wait",
            "--max-wait-seconds",
            "0",
        ]
    )

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["status"] == "RECORDED"
    assert output["query_count"] == 1
    assert output["warnings"] == []
    assert connection.closed
    assert connection.commands


def test_snowflake_cli_reconcile_lineage_uses_connector_connection(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    from contractforge_snowflake import cli as cli_module

    connection = _CostSnowflakeConnection(rows=[(2,)])
    env_path = tmp_path / "snowflake.yaml"
    env_path.write_text("evidence:\n  database: CONTRACTFORGE\n  schema: CF_EVIDENCE\n", encoding="utf-8")
    monkeypatch.setattr(cli_module, "_connect", lambda _options: connection)

    exit_code = snowflake_cli_main(
        [
            "reconcile-lineage",
            "--run-id",
            "run-123",
            "--environment",
            str(env_path),
        ]
    )

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["status"] == "RECORDED"
    assert output["row_count"] == 2
    assert output["warnings"] == []
    assert connection.closed
    assert any("SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY" in command for command in connection.commands)
    assert any('"ctrl_ingestion_lineage"' in command and "INSERT INTO" in command for command in connection.commands)


def test_snowflake_cli_dashboard_writes_artifacts(tmp_path, capsys) -> None:
    exit_code = snowflake_cli_main(
        [
            "dashboard",
            "--database",
            "OPS",
            "--schema",
            "AUDIT",
            "--lookback-days",
            "14",
            "--output-dir",
            str(tmp_path),
        ]
    )

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["status"] == "SUCCESS"
    assert (tmp_path / "control_tables_dashboard.sql").exists()
    assert '"OPS"."AUDIT"."ctrl_ingestion_runs"' in (tmp_path / "control_tables_dashboard.sql").read_text(encoding="utf-8")


def test_snowflake_cli_maintenance_ctrl_retention_dry_run(capsys) -> None:
    exit_code = snowflake_cli_main(
        [
            "maintenance",
            "ctrl-retention",
            "--database",
            "OPS",
            "--schema",
            "AUDIT",
            "--retention-days",
            "30",
            "--target",
            "runs",
        ]
    )

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["status"] == "DRY_RUN"
    assert output["plan"][0]["target"] == "runs"
    assert 'DELETE FROM "OPS"."AUDIT"."ctrl_ingestion_runs"' in output["plan"][0]["commands"][0]


def test_snowflake_cli_maintenance_ctrl_retention_execute_uses_connector(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    from contractforge_snowflake import cli as cli_module

    connection = _FakeSnowflakeConnection()
    monkeypatch.setattr(cli_module, "_connect", lambda _options: connection)

    exit_code = snowflake_cli_main(
        [
            "maintenance",
            "ctrl-retention",
            "--retention-days",
            "7",
            "--target",
            "cost",
            "--execute",
        ]
    )

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["status"] == "SUCCESS"
    assert connection.closed
    assert connection.commands == output["commands"]
    assert "ctrl_ingestion_cost" in connection.commands[0]


def test_snowflake_cli_publish_bundle_writes_nested_artifacts(tmp_path) -> None:
    contract_path = tmp_path / "contract.yaml"
    output_dir = tmp_path / "out"
    contract_path.write_text(
        "\n".join(
            [
                "source:",
                "  type: table",
                "  table: raw.customers",
                "target:",
                "  catalog: ANALYTICS",
                "  schema: BRONZE",
                "  table: CUSTOMERS",
                "mode: scd0_append",
            ]
        ),
        encoding="utf-8",
    )

    exit_code = snowflake_cli_main(["publish-bundle", str(contract_path), "--output-dir", str(output_dir)])

    assert exit_code == 0
    assert (output_dir / "runtime" / "ANALYTICS.BRONZE_CUSTOMERS.contract.json").exists()
    assert (output_dir / "snowflake.publish_manifest.json").exists()


def test_snowflake_cli_smoke_stage_publish_dry_run(capsys) -> None:
    exit_code = snowflake_cli_main(["smoke-stage-publish", "--table-prefix", "CF_SMOKE_STAGE_TEST"])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["execute"] is False
    assert output["stage"] == '@"CONTRACTFORGE_TEST_DB"."PUBLIC"."CF_SMOKE_STAGE_TEST_ARTIFACTS"'
    assert output["artifact_uri"].startswith('@"CONTRACTFORGE_TEST_DB"."PUBLIC"."CF_SMOKE_STAGE_TEST_ARTIFACTS"/')


def test_snowflake_cli_smoke_access_policy_dry_run(capsys) -> None:
    exit_code = snowflake_cli_main(["smoke-access-policy", "--table-prefix", "CF_SMOKE_ACCESS_TEST"])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["status"] == "DRY_RUN"
    assert set(output["contracts"]) == {"row_access", "masking"}
    row_access = output["contracts"]["row_access"]["access"]
    masking = output["contracts"]["masking"]["access"]
    assert row_access["grants"][0]["principal"] == "CONTRACTFORGE_INGEST_ROLE"
    assert row_access["row_filters"][0]["function"] == '"CONTRACTFORGE_TEST_DB"."PUBLIC"."CF_SMOKE_ACCESS_TEST_REGION_RAP"'
    assert masking["column_masks"][0]["function"] == '"CONTRACTFORGE_TEST_DB"."PUBLIC"."CF_SMOKE_ACCESS_TEST_EMAIL_MASK"'
    assert "row_access_blocked_count" in output["validation_queries"]
    assert "masking_blocked_email" in output["validation_queries"]


def test_snowflake_cli_smoke_procedure_dry_run(capsys) -> None:
    exit_code = snowflake_cli_main(["smoke-procedure", "--table-prefix", "CF_SMOKE_PROC_TEST"])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["execute"] is False
    assert output["procedure"] == "CONTRACTFORGE_TEST_DB.PUBLIC.CF_SMOKE_PROC_TEST_RUNNER"
    assert output["stage"] == '@"CONTRACTFORGE_TEST_DB"."PUBLIC"."CF_SMOKE_PROC_TEST_ARTIFACTS"'


def test_snowflake_cli_smoke_task_graph_dry_run(capsys) -> None:
    exit_code = snowflake_cli_main(["smoke-task-graph", "--table-prefix", "CF_SMOKE_TASK_TEST"])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["execute"] is False
    assert output["procedure"] == "CONTRACTFORGE_TEST_DB.PUBLIC.CF_SMOKE_TASK_TEST_RUNNER"
    assert output["task_names"] == ["bronze_customers", "silver_customers"]
    assert 'ALTER TASK "CONTRACTFORGE_TEST_DB"."PUBLIC"."bronze_customers" RESUME' in output["resume_sql"]
    assert 'EXECUTE TASK "CONTRACTFORGE_TEST_DB"."PUBLIC"."bronze_customers"' in output["execute_sql"]
    assert "TASK_HISTORY" in output["history_sql"]


def test_snowflake_smoke_task_graph_live_path_uses_execute_helper() -> None:
    import inspect

    from contractforge_snowflake.smoke import task_graph

    source = inspect.getsource(task_graph._execute_task_graph_smoke)

    assert "_execute(" not in source
    assert 'execute(session, f"CREATE OR REPLACE STAGE' in source
    assert "wait_snowflake_project_tasks(" in source
    assert "ALTER TASK IF EXISTS" in inspect.getsource(task_graph._cleanup)
    assert "DROP STAGE IF EXISTS" in inspect.getsource(task_graph._cleanup)


def test_snowflake_runtime_procedure_can_skip_database_and_schema_bootstrap() -> None:
    from contractforge_snowflake.deployment.procedure import render_runtime_procedure_sql

    sql = render_runtime_procedure_sql(
        {
            "parameters": {
                "snowflake": {
                    "runner_procedure": "CONTRACTFORGE_TEST_DB.PUBLIC.CF_SMOKE_PROC_RUNNER",
                    "runtime_imports": ["@STAGE/libs/contractforge_core-0.1.0-py3-none-any.zip"],
                    "runtime_wheel_uri": "@STAGE/libs/contractforge_snowflake-0.1.0-py3-none-any.zip",
                    "runtime_create_database": False,
                    "runtime_create_schema": False,
                }
            }
        }
    )

    assert "CREATE DATABASE" not in sql
    assert "CREATE SCHEMA" not in sql
    assert 'CREATE OR REPLACE PROCEDURE "CONTRACTFORGE_TEST_DB"."PUBLIC"."CF_SMOKE_PROC_RUNNER"' in sql
    assert "PACKAGES = ('snowflake-snowpark-python', 'pydantic', 'pyyaml', 'eval-type-backport')" in sql
    assert "'@STAGE/libs/contractforge_core-0.1.0-py3-none-any.zip'" in sql
    assert "'@STAGE/libs/contractforge_snowflake-0.1.0-py3-none-any.zip'" in sql


def test_snowflake_cli_run_dry_run_outputs_planning(tmp_path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    from contractforge_snowflake import cli as cli_module

    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(_append_contract()), encoding="utf-8")
    monkeypatch.setattr(cli_module, "_connect", lambda _options: pytest.fail("dry-run should not connect"))

    exit_code = snowflake_cli_main(["run", "--contract-uri", str(contract_path), "--dry-run"])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["status"] == "DRY_RUN"
    assert output["planning_status"] == "SUPPORTED"


def test_snowflake_cli_run_uses_connector_session(tmp_path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    from contractforge_snowflake import cli as cli_module

    contract_path = tmp_path / "contract.json"
    options_path = tmp_path / "connect.yaml"
    contract_path.write_text(json.dumps(_append_contract()), encoding="utf-8")
    options_path.write_text("account: TEST_ACCOUNT\nuser: CFINGESTSVC\n", encoding="utf-8")
    connection = _FakeSnowflakeConnection()
    observed: dict[str, object] = {}

    def fake_connect(options):
        observed["options"] = options
        return connection

    def fake_run_snowflake_contract(**kwargs):
        observed.update(kwargs)
        assert isinstance(kwargs["session"], SnowflakeConnectorSession)
        return {"status": "SUCCESS", "planning_status": "SUPPORTED"}

    monkeypatch.setattr(cli_module, "_connect", fake_connect)
    monkeypatch.setattr(cli_module, "run_snowflake_contract", fake_run_snowflake_contract)

    exit_code = snowflake_cli_main(
        ["run", "--contract-uri", str(contract_path), "--connect-options", str(options_path)]
    )

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["status"] == "SUCCESS"
    assert observed["options"] == {"account": "TEST_ACCOUNT", "user": "CFINGESTSVC"}
    assert observed["contract_uri"] == str(contract_path)
    assert connection.closed


def test_snowflake_connector_options_reject_unknown_keys() -> None:
    with pytest.raises(ValueError, match="Unsupported Snowflake connector option"):
        validate_connect_options({"account": "TEST_ACCOUNT", "unsafe_extra": "value"})


def test_snowflake_connector_options_accept_known_keys() -> None:
    options = validate_connect_options(
        {
            "account": "TEST_ACCOUNT",
            "user": "CFINGESTSVC",
            "warehouse": "CF_WH",
            "session_parameters": {"QUERY_TAG": "contractforge"},
        }
    )

    assert options == {
        "account": "TEST_ACCOUNT",
        "user": "CFINGESTSVC",
        "warehouse": "CF_WH",
        "session_parameters": {"QUERY_TAG": "contractforge"},
    }


def test_snowflake_connector_session_exposes_result_schema() -> None:
    connection = _MetadataSnowflakeConnection()
    session = SnowflakeConnectorSession(connection)

    result = session.sql("SELECT id, name FROM customers")

    assert result.collect() == [(1, "Ada")]
    assert result.schema.names == ("ID", "NAME")
    assert [field.datatype for field in result.schema.fields] == ["NUMBER", "VARCHAR"]
    assert result.query_id == "01abc"
    assert result.rowcount == 1
    assert connection.closed_cursors == 1


def test_snowflake_connector_session_maps_numeric_type_codes() -> None:
    connection = _MetadataSnowflakeConnection(description=(("AMOUNT", 0), ("EMAIL", 2), ("ACTIVE", 13)))
    session = SnowflakeConnectorSession(connection)

    result = session.sql("SELECT amount, email, active FROM customers")

    assert [field.datatype for field in result.schema.fields] == ["NUMBER", "VARCHAR", "BOOLEAN"]


def test_snowflake_deploy_project_dry_run_uses_project_contracts(tmp_path) -> None:
    project_file = _write_snowflake_project(tmp_path)

    result = deploy_snowflake_project(project_file, dry_run=True)

    assert result.execution_model == "library_runner"
    assert result.dry_run is True
    assert len(result.steps) == 2
    assert [step.name for step in result.steps] == ["bronze_customers", "silver_customers"]
    assert [step.planning_status for step in result.steps] == ["SUPPORTED", "SUPPORTED_WITH_WARNINGS"]
    assert all(step.deployment is None for step in result.steps)
    assert all("snowflake.publish_manifest.json" in step.artifacts for step in result.steps)
    assert result.deployment_artifacts == {}


def test_snowflake_deploy_project_dry_run_renders_task_graph_for_schedule_and_dependencies(tmp_path) -> None:
    project_file = _write_snowflake_project(tmp_path, include_schedule=True, include_dependencies=True, include_task_settings=True)

    result = deploy_snowflake_project(project_file, dry_run=True)

    procedure = result.deployment_artifacts["deployment/snowflake_runtime_procedure.sql"]
    task_graph = result.deployment_artifacts["deployment/snowflake_task_graph.sql"]
    assert 'CREATE OR REPLACE PROCEDURE "CONTRACTFORGE"."CF_RUNTIME"."RUN_CONTRACTFORGE_CONTRACT"' in procedure
    assert "LANGUAGE PYTHON" in procedure
    assert "RUNTIME_VERSION = '3.10'" in procedure
    assert "PACKAGES = ('snowflake-snowpark-python', 'pydantic', 'pyyaml', 'eval-type-backport')" in procedure
    assert "IMPORTS = ('@CONTRACTFORGE_ARTIFACTS/libs/contractforge_snowflake-0.1.0-py3-none-any.zip')" in procedure
    assert "HANDLER = 'contractforge_snowflake.runtime.snowpark_handler.run'" in procedure
    assert "SCHEDULE = 'USING CRON 0 6 * * * America/Sao_Paulo'" in task_graph
    assert 'ALTER TASK IF EXISTS "CONTRACTFORGE"."CF_TASKS"."silver_customers" SUSPEND' in task_graph
    assert 'CREATE OR REPLACE TASK "CONTRACTFORGE"."CF_TASKS"."bronze_customers"' in task_graph
    assert 'AFTER "CONTRACTFORGE"."CF_TASKS"."bronze_customers"' in task_graph
    assert 'CALL "CONTRACTFORGE"."CF_RUNTIME"."RUN_CONTRACTFORGE_CONTRACT"' in task_graph
    assert "@CONTRACTFORGE_ARTIFACTS/dev/runtime/ANALYTICS.BRONZE_CUSTOMERS.contract.json" in task_graph
    assert "@CONTRACTFORGE_ARTIFACTS/dev/runtime/ANALYTICS.SILVER_CUSTOMERS.environment.json" in task_graph
    assert ".source.sql" not in task_graph
    assert ".write.sql" not in task_graph


def test_snowflake_deploy_project_schedule_requires_artifact_destination(tmp_path) -> None:
    project_file = _write_snowflake_project(tmp_path, include_schedule=True, include_artifact_uri=False)

    with pytest.raises(ValueError, match="requires an artifact destination"):
        deploy_snowflake_project(project_file, dry_run=True)


def test_snowflake_deploy_project_schedule_requires_runtime_wheel_uri(tmp_path) -> None:
    project_file = _write_snowflake_project(tmp_path, include_schedule=True)

    with pytest.raises(ValueError, match="runtime_wheel_uri"):
        deploy_snowflake_project(project_file, dry_run=True)


def test_snowflake_deploy_project_rejects_unsafe_runtime_wheel_uri(tmp_path) -> None:
    project_file = _write_snowflake_project(tmp_path, include_schedule=True, include_task_settings=True, runtime_wheel_uri="@STAGE/../bad.whl")

    with pytest.raises(ValueError, match="Unsafe Snowflake runtime import URI"):
        deploy_snowflake_project(project_file, dry_run=True)


def test_snowflake_deploy_project_rejects_wheel_only_runtime_import(tmp_path) -> None:
    project_file = _write_snowflake_project(
        tmp_path,
        include_schedule=True,
        include_task_settings=True,
        runtime_wheel_uri="@STAGE/libs/contractforge_snowflake-0.1.0-py3-none-any.whl",
    )

    with pytest.raises(ValueError, match=".whl files are not valid Python procedure imports"):
        deploy_snowflake_project(project_file, dry_run=True)


def test_snowflake_deploy_project_publishes_each_step(tmp_path) -> None:
    project_file = _write_snowflake_project(tmp_path)
    connection = _FakeSnowflakeConnection()

    result = deploy_snowflake_project(project_file, connection=connection)

    assert result.dry_run is False
    assert len(result.steps) == 2
    assert all(step.deployment is not None for step in result.steps)
    assert len(connection.commands) == 14
    assert all(".source.sql" not in command and ".write.sql" not in command for command in connection.commands)


def test_snowflake_deploy_project_applies_task_graph_when_scheduled(tmp_path) -> None:
    project_file = _write_snowflake_project(tmp_path, include_schedule=True, include_dependencies=True, include_task_settings=True)
    connection = _FakeSnowflakeConnection()

    result = deploy_snowflake_project(project_file, connection=connection)

    assert result.dry_run is False
    assert "deployment/snowflake_runtime_procedure.sql" in result.deployment_artifacts
    assert "deployment/snowflake_task_graph.sql" in result.deployment_artifacts
    assert any(command.startswith("CREATE OR REPLACE PROCEDURE") for command in result.applied_deployment_commands)
    assert any(command.startswith("ALTER TASK IF EXISTS") for command in result.applied_deployment_commands)
    assert any(command.startswith("CREATE OR REPLACE TASK") for command in result.applied_deployment_commands)
    assert any("SCHEDULE = 'USING CRON 0 6 * * * America/Sao_Paulo'" in command for command in result.applied_deployment_commands)
    assert any('AFTER "CONTRACTFORGE"."CF_TASKS"."bronze_customers"' in command for command in result.applied_deployment_commands)
    assert len(connection.commands) == len(result.applied_deployment_commands) + 14


def test_snowflake_deploy_project_accepts_connection_factory(tmp_path) -> None:
    project_file = _write_snowflake_project(tmp_path, include_schedule=True, include_dependencies=True, include_task_settings=True)
    connections = [_FakeSnowflakeConnection() for _ in range(3)]
    observed_options: list[dict[str, object]] = []

    def factory(options: dict[str, object]) -> _FakeSnowflakeConnection:
        observed_options.append(options)
        return connections[len(observed_options) - 1]

    result = deploy_snowflake_project(
        project_file,
        connect_options={"account": "TEST_ACCOUNT", "warehouse": "CF_WH"},
        connection_factory=factory,
    )

    assert result.dry_run is False
    assert len(result.steps) == 2
    assert len(observed_options) == 3
    assert all(options == {"account": "TEST_ACCOUNT", "warehouse": "CF_WH"} for options in observed_options)
    assert all(connection.closed for connection in connections)


def test_snowflake_task_lifecycle_commands_are_explicit() -> None:
    from contractforge_snowflake.deployment import render_task_lifecycle_sql

    environment = {
        "parameters": {
            "snowflake": {
                "task_database": "CONTRACTFORGE_TEST_DB",
                "task_schema": "PUBLIC",
            }
        }
    }

    resume = render_task_lifecycle_sql(environment=environment, task_names=["bronze_customers"], action="resume")
    execute = render_task_lifecycle_sql(environment=environment, task_names=["bronze_customers"], action="execute")
    suspend = render_task_lifecycle_sql(environment=environment, task_names=["bronze_customers"], action="suspend")

    assert resume == 'ALTER TASK "CONTRACTFORGE_TEST_DB"."PUBLIC"."bronze_customers" RESUME;\n'
    assert execute == 'EXECUTE TASK "CONTRACTFORGE_TEST_DB"."PUBLIC"."bronze_customers";\n'
    assert suspend == 'ALTER TASK "CONTRACTFORGE_TEST_DB"."PUBLIC"."bronze_customers" SUSPEND;\n'


def test_snowflake_task_lifecycle_rejects_unknown_action() -> None:
    from contractforge_snowflake.deployment import render_task_lifecycle_sql

    with pytest.raises(ValueError, match="resume, suspend, or execute"):
        render_task_lifecycle_sql(environment={}, task_names=["bronze_customers"], action="drop")


def test_snowflake_task_history_query_is_bounded() -> None:
    from contractforge_snowflake.deployment import render_task_history_query

    query = render_task_history_query(
        environment={"parameters": {"snowflake": {"task_database": "CONTRACTFORGE_TEST_DB", "task_schema": "PUBLIC"}}},
        task_names=["bronze_customers", "silver_customers"],
        limit=10,
    )

    assert '"CONTRACTFORGE_TEST_DB".INFORMATION_SCHEMA.TASK_HISTORY' in query
    assert "TASK_NAME =>" not in query
    assert "RESULT_LIMIT => 10" in query
    assert "'BRONZE_CUSTOMERS', 'SILVER_CUSTOMERS'" in query


def test_snowflake_deploy_project_requires_snowflake_contract_mapping(tmp_path) -> None:
    project_file = _write_snowflake_project(tmp_path, include_snowflake_contract=False)

    with pytest.raises(ValueError, match="contracts.snowflake"):
        deploy_snowflake_project(project_file, dry_run=True)


def test_snowflake_cli_deploy_project_dry_run_outputs_steps(tmp_path, capsys) -> None:
    project_file = _write_snowflake_project(tmp_path)

    exit_code = snowflake_cli_main(["deploy-project", str(project_file), "--dry-run", "--summary-only"])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["execution_model"] == "library_runner"
    assert len(output["steps"]) == 2
    assert "artifacts" not in output["steps"][0]


def test_snowflake_run_project_dry_run_executes_root_tasks(tmp_path) -> None:
    project_file = _write_snowflake_project(tmp_path, include_schedule=True, include_dependencies=True, include_task_settings=True)

    result = run_snowflake_project(project_file, dry_run=True)

    assert result.dry_run is True
    assert result.task_names == ("bronze_customers", "silver_customers")
    assert result.root_tasks == ("bronze_customers",)
    assert result.commands == (
        'ALTER TASK "CONTRACTFORGE"."CF_TASKS"."silver_customers" RESUME',
        'EXECUTE TASK "CONTRACTFORGE"."CF_TASKS"."bronze_customers"',
    )


def test_snowflake_run_project_requires_task_graph(tmp_path) -> None:
    project_file = _write_snowflake_project(tmp_path)

    with pytest.raises(ValueError, match="scheduled or dependency task graph"):
        run_snowflake_project(project_file, dry_run=True)


def test_snowflake_wait_project_tasks_returns_terminal_history() -> None:
    connection = _TaskHistorySnowflakeConnection(
        [
            ("bronze_customers", "SUCCEEDED", "01-bronze"),
            ("silver_customers", "SUCCEEDED", "01-silver"),
        ]
    )

    result = wait_snowflake_project_tasks(
        connection=connection,
        environment={"parameters": {"snowflake": {"task_database": "CONTRACTFORGE", "task_schema": "CF_TASKS"}}},
        task_names=("bronze_customers", "silver_customers"),
        poll_interval_seconds=0,
        max_wait_seconds=1,
    )

    assert result["status"] == "SUCCESS"
    assert [task["query_id"] for task in result["tasks"]] == ["01-bronze", "01-silver"]
    assert any("TASK_HISTORY" in command for command in connection.commands)


def test_snowflake_wait_project_tasks_returns_failed_when_root_fails() -> None:
    connection = _TaskHistorySnowflakeConnection(
        [
            ("bronze_customers", "FAILED", "01-bronze"),
        ]
    )

    result = wait_snowflake_project_tasks(
        connection=connection,
        environment={"parameters": {"snowflake": {"task_database": "CONTRACTFORGE", "task_schema": "CF_TASKS"}}},
        task_names=("bronze_customers", "silver_customers"),
        poll_interval_seconds=0,
        max_wait_seconds=1,
    )

    assert result["status"] == "FAILED"
    assert result["tasks"] == ({"name": "bronze_customers", "state": "FAILED", "query_id": "01-bronze"},)


def test_snowflake_wait_project_tasks_tracks_newest_history_per_poll(monkeypatch: pytest.MonkeyPatch) -> None:
    import contractforge_snowflake.runtime.project as project_runtime

    sleeps: list[float] = []
    connection = _SequentialTaskHistorySnowflakeConnection(
        [
            [
                ("silver_customers", "EXECUTING", "01-silver-executing"),
                ("bronze_customers", "SUCCEEDED", "01-bronze-old"),
                ("silver_customers", "SUCCEEDED", "01-silver-old"),
            ],
            [
                ("bronze_customers", "SUCCEEDED", "01-bronze"),
                ("silver_customers", "SUCCEEDED", "01-silver"),
            ],
        ]
    )
    monkeypatch.setattr(project_runtime.time, "sleep", lambda seconds: sleeps.append(seconds))

    result = wait_snowflake_project_tasks(
        connection=connection,
        environment={"parameters": {"snowflake": {"task_database": "CONTRACTFORGE", "task_schema": "CF_TASKS"}}},
        task_names=("bronze_customers", "silver_customers"),
        poll_interval_seconds=0,
        max_wait_seconds=1,
    )

    assert result["status"] == "SUCCESS"
    assert [task["query_id"] for task in result["tasks"]] == ["01-bronze", "01-silver"]
    assert sleeps == [1.0]


def test_snowflake_wait_project_tasks_ignores_history_before_cutoff() -> None:
    cutoff = datetime(2026, 6, 9, 13, 0, tzinfo=timezone.utc)
    connection = _TaskHistorySnowflakeConnection(
        [
            ("bronze_customers", "SUCCEEDED", "01-bronze-old", datetime(2026, 6, 9, 12, 59, tzinfo=timezone.utc)),
            ("silver_customers", "SUCCEEDED", "01-silver", datetime(2026, 6, 9, 13, 1, tzinfo=timezone.utc)),
            ("bronze_customers", "SUCCEEDED", "01-bronze", datetime(2026, 6, 9, 13, 1, tzinfo=timezone.utc)),
        ]
    )

    result = wait_snowflake_project_tasks(
        connection=connection,
        environment={"parameters": {"snowflake": {"task_database": "CONTRACTFORGE", "task_schema": "CF_TASKS"}}},
        task_names=("bronze_customers", "silver_customers"),
        poll_interval_seconds=0,
        max_wait_seconds=1,
        started_after=cutoff,
    )

    assert result["status"] == "SUCCESS"
    assert [task["query_id"] for task in result["tasks"]] == ["01-bronze", "01-silver"]


def test_snowflake_wait_project_tasks_ignores_future_scheduled_placeholders() -> None:
    connection = _TaskHistorySnowflakeConnection(
        [
            ("bronze_customers", "SCHEDULED", None),
            ("silver_customers", "SUCCEEDED", "01-silver"),
            ("bronze_customers", "SUCCEEDED", "01-bronze"),
        ]
    )

    result = wait_snowflake_project_tasks(
        connection=connection,
        environment={"parameters": {"snowflake": {"task_database": "CONTRACTFORGE", "task_schema": "CF_TASKS"}}},
        task_names=("bronze_customers", "silver_customers"),
        poll_interval_seconds=0,
        max_wait_seconds=1,
    )

    assert result["status"] == "SUCCESS"
    assert [task["query_id"] for task in result["tasks"]] == ["01-bronze", "01-silver"]


def test_snowflake_wait_project_tasks_clamps_poll_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    import contractforge_snowflake.runtime.project as project_runtime

    sleeps: list[float] = []
    connection = _SequentialTaskHistorySnowflakeConnection(
        [
            [],
            [("bronze_customers", "SUCCEEDED", "01-bronze")],
        ]
    )
    monkeypatch.setattr(project_runtime.time, "sleep", lambda seconds: sleeps.append(seconds))

    result = wait_snowflake_project_tasks(
        connection=connection,
        environment={"parameters": {"snowflake": {"task_database": "CONTRACTFORGE", "task_schema": "CF_TASKS"}}},
        task_names=("bronze_customers",),
        poll_interval_seconds=0,
        max_wait_seconds=1,
    )

    assert result["status"] == "SUCCESS"
    assert sleeps == [1.0]


def test_snowflake_run_project_accepts_connection_factory(tmp_path) -> None:
    project_file = _write_snowflake_project(tmp_path, include_schedule=True, include_dependencies=True, include_task_settings=True)
    connection = _FakeSnowflakeConnection()
    observed: dict[str, object] = {}

    def factory(options: dict[str, object]) -> _FakeSnowflakeConnection:
        observed["options"] = options
        return connection

    result = run_snowflake_project(
        project_file,
        connect_options={"account": "TEST_ACCOUNT", "role": "CONTRACTFORGE_ROLE"},
        connection_factory=factory,
    )

    assert result.dry_run is False
    assert observed["options"] == {"account": "TEST_ACCOUNT", "role": "CONTRACTFORGE_ROLE"}
    assert connection.closed
    assert connection.commands == [
        'ALTER TASK "CONTRACTFORGE"."CF_TASKS"."silver_customers" RESUME',
        'EXECUTE TASK "CONTRACTFORGE"."CF_TASKS"."bronze_customers"',
    ]


def test_snowflake_run_project_wait_ignores_stale_task_history(tmp_path) -> None:
    project_file = _write_snowflake_project(tmp_path, include_schedule=True, include_dependencies=True, include_task_settings=True)
    connection = _TaskHistorySnowflakeConnection(
        [
            ("bronze_customers", "FAILED", "01-old", datetime(2000, 1, 1, tzinfo=timezone.utc)),
            ("silver_customers", "SUCCEEDED", "01-silver-new", datetime(2999, 1, 1, tzinfo=timezone.utc)),
            ("bronze_customers", "SUCCEEDED", "01-new", datetime(2999, 1, 1, tzinfo=timezone.utc)),
        ]
    )

    result = run_snowflake_project(project_file, connection=connection, wait=True, poll_interval_seconds=0, max_wait_seconds=1)

    assert result.wait is not None
    assert result.wait["status"] == "SUCCESS"
    assert result.wait["tasks"][0]["query_id"] == "01-new"
    assert result.wait["tasks"][1]["query_id"] == "01-silver-new"


def test_snowflake_project_cleanup_plan_is_non_destructive(tmp_path) -> None:
    project_file = _write_snowflake_project(tmp_path, include_schedule=True, include_dependencies=True, include_task_settings=True)

    plan = build_snowflake_project_cleanup_plan(project_file)

    assert plan.dry_run is True
    assert plan.commands == (
        'DROP TASK IF EXISTS "CONTRACTFORGE"."CF_TASKS"."silver_customers"',
        'DROP TASK IF EXISTS "CONTRACTFORGE"."CF_TASKS"."bronze_customers"',
        'DROP PROCEDURE IF EXISTS "CONTRACTFORGE"."CF_RUNTIME"."RUN_CONTRACTFORGE_CONTRACT"(STRING, STRING)',
    )
    assert any("not executed" in note for note in plan.notes)
    assert not any("DROP TABLE" in command for command in plan.commands)


def test_snowflake_cli_run_project_dry_run_summary_only(tmp_path, capsys) -> None:
    project_file = _write_snowflake_project(tmp_path, include_schedule=True, include_dependencies=True, include_task_settings=True)

    exit_code = snowflake_cli_main(["run-project", str(project_file), "--dry-run", "--summary-only"])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["dry_run"] is True
    assert output["root_tasks"] == ["bronze_customers"]
    assert "commands" not in output


def test_snowflake_cli_cleanup_plan_outputs_commands(tmp_path, capsys) -> None:
    project_file = _write_snowflake_project(tmp_path, include_schedule=True, include_dependencies=True, include_task_settings=True)

    exit_code = snowflake_cli_main(["cleanup-plan", str(project_file)])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["dry_run"] is True
    assert output["commands"][0].startswith('DROP TASK IF EXISTS "CONTRACTFORGE"."CF_TASKS"."silver_customers"')


class _FakeSnowflakeConnection:
    def __init__(self) -> None:
        self.commands: list[str] = []
        self.closed = False

    def cursor(self) -> "_FakeSnowflakeCursor":
        return _FakeSnowflakeCursor(self.commands)

    def close(self) -> None:
        self.closed = True


class _FailingSnowflakeConnection(_FakeSnowflakeConnection):
    def cursor(self) -> "_FailingSnowflakeCursor":
        return _FailingSnowflakeCursor(self.commands)


class _CostSnowflakeConnection(_FakeSnowflakeConnection):
    def __init__(self, *, rows: list[tuple[object, ...]]) -> None:
        super().__init__()
        self.rows = rows

    def cursor(self) -> "_CostSnowflakeCursor":
        return _CostSnowflakeCursor(self)


class _FakeSnowflakeCursor:
    def __init__(self, commands: list[str]) -> None:
        self._commands = commands

    def execute(self, command: str) -> None:
        self._commands.append(command)

    def close(self) -> None:
        pass


class _FailingSnowflakeCursor(_FakeSnowflakeCursor):
    def execute(self, command: str) -> None:
        self._commands.append(command)
        raise RuntimeError("upload failed token=raw-token password=raw-secret")


class _CostSnowflakeCursor:
    def __init__(self, connection: _CostSnowflakeConnection) -> None:
        self._connection = connection
        self._is_probe = False
        self.description = (("QUERY_COUNT", "FIXED"),)

    def execute(self, command: str) -> None:
        self._connection.commands.append(command)
        if command.startswith("SELECT COUNT(*) AS ACCESS_HISTORY_ROWS"):
            self.description = (("ACCESS_HISTORY_ROWS", "FIXED"),)
            self._is_probe = True
        else:
            self.description = (("QUERY_COUNT", "FIXED"),)
            self._is_probe = command.startswith("SELECT COUNT(*) AS QUERY_COUNT")

    def fetchall(self) -> list[tuple[object, ...]]:
        return self._connection.rows if self._is_probe else []

    def close(self) -> None:
        pass


class _StageGetSnowflakeConnection:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.commands: list[str] = []

    def cursor(self) -> "_StageGetSnowflakeCursor":
        return _StageGetSnowflakeCursor(self)


class _StageGetSnowflakeCursor:
    description = None
    rowcount = -1

    def __init__(self, connection: _StageGetSnowflakeConnection) -> None:
        self._connection = connection

    def execute(self, command: str) -> None:
        self._connection.commands.append(command)
        if command.startswith("GET "):
            target = command.split(" file://", 1)[1].split(" PARALLEL=1", 1)[0]
            directory = Path(target)
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "customers.contract.json").write_bytes(self._connection.payload)

    def fetchall(self) -> list[tuple[object, ...]]:
        return []

    def close(self) -> None:
        pass


class _TaskHistorySnowflakeConnection:
    def __init__(self, rows: list[tuple[str, str, str]]) -> None:
        self.rows = rows
        self.commands: list[str] = []

    def cursor(self) -> "_TaskHistorySnowflakeCursor":
        return _TaskHistorySnowflakeCursor(self)


class _TaskHistorySnowflakeCursor:
    description = (("NAME", "TEXT"), ("STATE", "TEXT"), ("QUERY_ID", "TEXT"))

    def __init__(self, connection: _TaskHistorySnowflakeConnection) -> None:
        self._connection = connection

    def execute(self, command: str) -> None:
        self._connection.commands.append(command)

    def fetchall(self) -> list[tuple[str, str, str]]:
        return self._connection.rows

    def close(self) -> None:
        pass


class _SequentialTaskHistorySnowflakeConnection:
    def __init__(self, batches: list[list[tuple[str, str, str]]]) -> None:
        self.batches = batches
        self.commands: list[str] = []

    def cursor(self) -> "_SequentialTaskHistorySnowflakeCursor":
        return _SequentialTaskHistorySnowflakeCursor(self)


class _SequentialTaskHistorySnowflakeCursor:
    description = (("NAME", "TEXT"), ("STATE", "TEXT"), ("QUERY_ID", "TEXT"))

    def __init__(self, connection: _SequentialTaskHistorySnowflakeConnection) -> None:
        self._connection = connection

    def execute(self, command: str) -> None:
        self._connection.commands.append(command)

    def fetchall(self) -> list[tuple[str, str, str]]:
        return self._connection.batches.pop(0) if self._connection.batches else []

    def close(self) -> None:
        pass


class _MetadataSnowflakeConnection:
    def __init__(self, *, description=(("ID", "FIXED"), ("NAME", "TEXT"))) -> None:
        self.closed_cursors = 0
        self.description = description

    def cursor(self) -> "_MetadataSnowflakeCursor":
        return _MetadataSnowflakeCursor(self)


class _MetadataSnowflakeCursor:
    sfqid = "01abc"
    rowcount = 1

    def __init__(self, connection: _MetadataSnowflakeConnection) -> None:
        self._connection = connection
        self.description = connection.description

    def execute(self, command: str) -> None:
        self.command = command

    def fetchall(self) -> list[tuple[object, ...]]:
        return [(1, "Ada")]

    def close(self) -> None:
        self._connection.closed_cursors += 1


class _FakeSnowflakeSession:
    def __init__(self, artifacts: dict[str, str]) -> None:
        self.file = _FakeSnowflakeFileAccessor(artifacts)


class _FakeSnowflakeFileAccessor:
    def __init__(self, artifacts: dict[str, str]) -> None:
        self._artifacts = artifacts

    def get_stream(self, uri: str) -> BytesIO:
        return BytesIO(self._artifacts[uri].encode("utf-8"))


class _ExecutingSnowflakeSession:
    def __init__(
        self,
        *,
        columns: tuple[str, ...] = ("customer_id", "name", "email"),
        column_types: dict[str, str] | None = None,
        target_columns: tuple[str, ...] = (),
        target_column_types: dict[str, str] | None = None,
        scalars: dict[str, object] | None = None,
    ) -> None:
        self.commands: list[str] = []
        self._columns = columns
        self._column_types = column_types
        self._target_columns = target_columns
        self._target_column_types = target_column_types
        self._scalars = scalars or {}

    def sql(self, command: str) -> "_ExecutingSnowflakeResult":
        self.commands.append(command)
        scalar = next((value for marker, value in self._scalars.items() if marker in command), None)
        columns = self._target_columns if command.startswith("SELECT * FROM \"ANALYTICS\"") else self._columns
        column_types = self._target_column_types if command.startswith("SELECT * FROM \"ANALYTICS\"") else self._column_types
        return _ExecutingSnowflakeResult(columns=columns if " LIMIT 0" in command else (), column_types=column_types, scalar=scalar)


class _FailingAttributionSnowflakeSession(_ExecutingSnowflakeSession):
    def sql(self, command: str) -> "_ExecutingSnowflakeResult":
        if "SNOWFLAKE.ACCOUNT_USAGE.QUERY_ATTRIBUTION_HISTORY" in command:
            self.commands.append(command)
            raise RuntimeError("attribution failed token=raw-token")
        return super().sql(command)


class _ExecutingSnowflakeResult:
    def __init__(
        self,
        *,
        columns: tuple[str, ...] = (),
        column_types: dict[str, str] | None = None,
        scalar: object | None = None,
    ) -> None:
        self.schema = _FakeSnowflakeSchema(columns, column_types=column_types) if columns else None
        self._scalar = scalar

    def collect(self) -> list:
        if isinstance(self._scalar, tuple):
            return [self._scalar]
        return [(self._scalar,)] if self._scalar is not None else []


class _RuntimeFailingSession(_ExecutingSnowflakeSession):
    def __init__(self, *, fail_on: str, message: str = "runtime write failed") -> None:
        super().__init__()
        self._fail_on = fail_on
        self._message = message

    def sql(self, command: str) -> "_ExecutingSnowflakeResult":
        if self._fail_on in command:
            self.commands.append(command)
            raise RuntimeError(self._message)
        return super().sql(command)


class _LockReleaseFailingSession:
    def __init__(self) -> None:
        self.commands: list[str] = []

    def sql(self, command: str) -> "_ExecutingSnowflakeResult":
        self.commands.append(command)
        raise RuntimeError("release failed password=raw-secret")


class _AnnotationTagFailingSession(_ExecutingSnowflakeSession):
    def sql(self, command: str) -> "_ExecutingSnowflakeResult":
        if command.startswith('ALTER TABLE "ANALYTICS"."BRONZE"."CUSTOMERS"') and " SET TAG " in command:
            self.commands.append(command)
            raise RuntimeError("tag object does not exist password=raw-secret")
        return super().sql(command)


class _FakeSnowflakeSchema:
    def __init__(self, columns: tuple[str, ...], *, column_types: dict[str, str] | None = None) -> None:
        if column_types:
            self.fields = tuple(_FakeSnowflakeField(name, column_types.get(name, "VARIANT")) for name in columns)
        else:
            self.names = columns


class _FakeSnowflakeField:
    def __init__(self, name: str, datatype: str) -> None:
        self.name = name
        self.datatype = datatype


def _write_snowflake_project(
    tmp_path,
    *,
    include_snowflake_contract: bool = True,
    include_schedule: bool = False,
    include_dependencies: bool = False,
    include_task_settings: bool = False,
    include_artifact_uri: bool = True,
    runtime_wheel_uri: str = "@CONTRACTFORGE_ARTIFACTS/libs/contractforge_snowflake-0.1.0-py3-none-any.zip",
):
    contracts = tmp_path / "contracts"
    envs = tmp_path / "envs"
    contracts.mkdir()
    envs.mkdir()
    (envs / "snowflake.yaml").write_text(
        "\n".join(
            _snowflake_environment_lines(
                include_artifact_uri=include_artifact_uri,
                include_task_settings=include_task_settings,
                runtime_wheel_uri=runtime_wheel_uri,
            )
        ),
        encoding="utf-8",
    )
    (contracts / "bronze_customers.yaml").write_text(
        "\n".join(
            [
                "source:",
                "  type: table",
                "  table: raw.customers",
                "target:",
                "  catalog: ANALYTICS",
                "  schema: BRONZE",
                "  table: CUSTOMERS",
                "mode: scd0_append",
            ]
        ),
        encoding="utf-8",
    )
    (contracts / "silver_customers.yaml").write_text(
        "\n".join(
            [
                "source:",
                "  type: table",
                "  table: ANALYTICS.BRONZE.CUSTOMERS",
                "target:",
                "  catalog: ANALYTICS",
                "  schema: SILVER",
                "  table: CUSTOMERS",
                "mode: scd1_hash_diff",
                "merge_keys: [customer_id]",
                "hash_keys: [name, email]",
            ]
        ),
        encoding="utf-8",
    )
    first_contract = "contracts/bronze_customers.yaml" if include_snowflake_contract else None
    first_contract_block = (
        ["      snowflake: contracts/bronze_customers.yaml"] if first_contract else ["      aws: contracts/bronze_customers.yaml"]
    )
    project_lines = [
        "name: snowflake_project",
        "environments:",
        "  snowflake: envs/snowflake.yaml",
        *_snowflake_project_schedule_lines(include_schedule),
        "execution_order:",
        "  - name: bronze_customers",
        "    contracts:",
        *first_contract_block,
        "  - name: silver_customers",
        *_snowflake_project_dependency_lines(include_dependencies),
        "    contracts:",
        "      snowflake: contracts/silver_customers.yaml",
    ]
    project_file = tmp_path / "project.yaml"
    project_file.write_text("\n".join(project_lines), encoding="utf-8")
    return project_file


def _snowflake_environment_lines(*, include_artifact_uri: bool, include_task_settings: bool, runtime_wheel_uri: str) -> list[str]:
    lines: list[str] = []
    if include_artifact_uri:
        lines += [
            "artifacts:",
            "  uri: '@CONTRACTFORGE_ARTIFACTS/dev'",
        ]
    lines += [
        "parameters:",
        "  snowflake:",
        "    warehouse: CF_WH",
    ]
    if include_task_settings:
        lines += [
            "    task_database: CONTRACTFORGE",
            "    task_schema: CF_TASKS",
            "    runner_procedure: CONTRACTFORGE.CF_RUNTIME.RUN_CONTRACTFORGE_CONTRACT",
            f"    runtime_wheel_uri: '{runtime_wheel_uri}'",
        ]
    return lines


def _snowflake_project_schedule_lines(include_schedule: bool) -> list[str]:
    return [
        "schedule:",
        "  cron: '0 6 * * *'",
        "  timezone: America/Sao_Paulo",
    ] if include_schedule else []


def _snowflake_project_dependency_lines(include_dependencies: bool) -> list[str]:
    return [
        "    depends_on:",
        "      - bronze_customers",
    ] if include_dependencies else []
