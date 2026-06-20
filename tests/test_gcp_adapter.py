from __future__ import annotations

import json

from contractforge_gcp import (
    GCP_SUBTARGET_BIGQUERY,
    annotation_steps,
    classify_gcp_source,
    deploy_gcp_project,
    gcp_bigquery_capabilities,
    gcp_source_review_payload,
    gcp_source_support,
    is_gcp_source_renderable,
    governance_ledger_plan,
    governance_reconciliation_plan,
    has_annotations,
    has_dataplex_aspect_plan,
    has_dataplex_lineage_plan,
    has_dataplex_quality_plan,
    has_governance_ledger_plan,
    has_governance_reconciliation_plan,
    has_policy_tag_access,
    list_gcp_source_support,
    policy_tag_steps,
    plan_bigquery_schema_policy,
    plan_gcp_contract,
    render_bigquery_annotations_evidence_sql,
    render_bigquery_annotations_plan,
    render_bigquery_annotations_sql,
    render_bigquery_advanced_write_mode_review,
    render_bigquery_advanced_write_sql,
    render_bigquery_governance_evidence_insert_sql,
    render_bigquery_governance_ledger_plan,
    render_bigquery_governance_reconciliation_plan,
    render_bigquery_policy_tags_plan,
    render_bigquery_schema_policy_plan,
    render_dataplex_aspect_plan,
    render_dataplex_data_quality_execution_plan,
    render_dataplex_data_quality_plan,
    render_dataplex_lineage_plan,
    render_gcp_contract,
    render_gcp_deployment_manifest,
    render_gcp_project_deployment_manifest,
    render_gcp_source_promotion_plan,
    render_gcp_source_review_markdown,
    render_gcp_source_secret_resolution_plan,
    render_gcp_workflows_cleanup_plan,
    render_gcp_workflows_evidence_readback_plan,
    render_gcp_workflows_execution_plan,
    render_gcp_workflows_runner_yaml,
    resolve_gcp_secret_placeholders,
    review_required_gcp_source_types,
    run_bigquery_governance_reconciliation,
    run_dataplex_data_quality,
    run_dataplex_lineage_aspects,
    run_gcp_source_promotion,
    run_gcp_workflows_orchestration,
    secret_placeholder_refs,
    workflow_name,
)
from contractforge_gcp.cli import main as gcp_cli
from contractforge_gcp.deployment import GCPWorkflowOperation, GCPWorkflowReadbackTarget
from contractforge_gcp.stabilization import gcp_stabilization_report


def _contract(mode: str = "overwrite") -> dict[str, object]:
    return {
        "source": {"type": "table", "table": "raw.orders"},
        "target": {"catalog": "test-project", "schema": "bronze", "table": "orders"},
        "layer": "bronze",
        "mode": mode,
    }


def _environment() -> dict[str, object]:
    return {
        "parameters": {
            "gcp": {
                "project_id": "test-project",
                "location": "US",
                "dataset": "contractforge",
                "staging_bucket": "cf-staging",
                "service_account": "contractforge@test-project.iam.gserviceaccount.com",
            }
        },
        "evidence": {"dataset": "contractforge_ops"},
    }


def _write_gcp_project(tmp_path) -> tuple[object, object]:
    project = tmp_path / "project.yaml"
    environment = tmp_path / "gcp.environment.yaml"
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    environment.write_text(
        """
parameters:
  gcp:
    project_id: test-project
    location: US
    dataset: contractforge
evidence:
  dataset: contractforge_ops
""".lstrip(),
        encoding="utf-8",
    )
    (contracts / "01_orders.ingestion.yaml").write_text(
        """
source:
  type: table
  table: raw.orders
target:
  catalog: test-project
  schema: bronze
  table: orders
mode: overwrite
""".lstrip(),
        encoding="utf-8",
    )
    project.write_text(
        """
name: gcp-deployment-smoke
environments:
  gcp: gcp.environment.yaml
execution_order:
  - name: bronze_orders
    layer: bronze
    contracts:
      gcp: contracts/01_orders.ingestion.yaml
""".lstrip(),
        encoding="utf-8",
    )
    return project, environment


def test_gcp_capabilities_are_conservative_until_runtime_is_validated() -> None:
    capabilities = gcp_bigquery_capabilities()

    assert capabilities.platform == GCP_SUBTARGET_BIGQUERY
    assert capabilities.supports_append is True
    assert capabilities.supports_overwrite is True
    assert capabilities.supports_merge is True
    assert capabilities.supports_hash_diff is False
    assert capabilities.supports_scd2 is False
    assert capabilities.evidence_stores == ("bigquery_audit_tables",)
    assert "scd1_hash_diff" in capabilities.review_required_semantics
    assert "source.delta" in capabilities.review_required_semantics
    assert "source.delta_table" in capabilities.review_required_semantics
    assert "source.delta_share" in capabilities.review_required_semantics
    assert "source.http_file" in capabilities.review_required_semantics
    for source_type in review_required_gcp_source_types():
        assert f"source.{source_type}" in capabilities.review_required_semantics


def test_gcp_source_support_declares_bigquery_and_review_required_sources() -> None:
    table = gcp_source_support("table")
    gcs = gcp_source_support({"type": "gcs", "format": "parquet", "path": "gs://bucket/orders/"})
    csv = gcp_source_support({"type": "csv", "path": "gs://bucket/orders.csv"})
    registered_iceberg = gcp_source_support({"type": "iceberg_table", "table": "project.dataset.orders_iceberg"})
    raw_iceberg_path = gcp_source_support({"type": "iceberg_table", "path": "gs://bucket/iceberg/orders/"})
    xml_file = gcp_source_support({"type": "xml", "path": "gs://bucket/orders.xml"})
    rest_api = gcp_source_support({"type": "rest_api", "request": {"url": "https://api.example.com/orders"}})
    rest_api_auth = gcp_source_support(
        {"type": "rest_api", "request": {"url": "https://api.example.com/orders"}, "auth": {"type": "bearer_token"}}
    )
    rest_api_secret_auth = gcp_source_support(
        {
            "type": "rest_api",
            "request": {"url": "https://api.example.com/orders"},
            "auth": {"type": "bearer_token", "token": "{{ secret:gcp/api-token }}"},
        }
    )
    http_json = gcp_source_support({"type": "http_json", "request": {"url": "https://api.example.com/orders.json"}})
    http_json_secret_auth = gcp_source_support(
        {
            "type": "http_json",
            "request": {"url": "https://api.example.com/orders.json"},
            "auth": {"type": "api_key", "header": "X-API-Key", "value": "{{ secret:gcp/http-api-key }}"},
        }
    )
    http_csv = gcp_source_support({"type": "http_csv", "request": {"url": "https://api.example.com/orders.csv"}})
    http_file_json = gcp_source_support(
        {"type": "http_file", "format": "json", "request": {"url": "https://api.example.com/orders.json"}}
    )
    http_file_text = gcp_source_support(
        {"type": "http_file", "format": "text", "request": {"url": "https://api.example.com/orders.txt"}}
    )
    http_file_parquet = gcp_source_support(
        {"type": "http_file", "format": "parquet", "request": {"url": "https://api.example.com/orders.parquet"}}
    )
    http_file_missing_format = gcp_source_support({"type": "http_file", "request": {"url": "https://api.example.com/orders"}})
    http_text = gcp_source_support({"type": "http_text", "request": {"url": "https://api.example.com/orders.txt"}})
    http_text_secret_auth = gcp_source_support(
        {
            "type": "http_text",
            "request": {"url": "https://api.example.com/orders.txt"},
            "auth": {"type": "bearer_token", "token": "{{ secret:gcp/http-text-token }}"},
        }
    )
    http_text_inline_auth = gcp_source_support(
        {
            "type": "http_text",
            "request": {"url": "https://api.example.com/orders.txt"},
            "auth": {"type": "bearer_token", "token": "inline-token"},
        }
    )
    kafka = gcp_source_support("kafka_bounded")
    delta = gcp_source_support("delta")
    delta_table = gcp_source_support("delta_table")
    delta_share = gcp_source_support("delta_share")
    native_passthrough = gcp_source_support("native_passthrough")
    oracle = gcp_source_support("oracle")
    unknown = gcp_source_support("made_up")
    catalog = {entry["source_type"]: entry for entry in list_gcp_source_support()}

    assert table["status"] == "SUPPORTED"
    assert table["renderable"] is True
    assert gcs["status"] == "SUPPORTED"
    assert "BigQuery load job" in gcs["native_mapping"]
    assert csv["status"] == "SUPPORTED"
    assert registered_iceberg["status"] == "SUPPORTED"
    assert registered_iceberg["renderable"] is True
    assert "BigLake managed Iceberg" in registered_iceberg["native_mapping"]
    assert raw_iceberg_path["status"] == "REVIEW_REQUIRED"
    assert raw_iceberg_path["renderable"] is False
    assert xml_file["status"] == "UNSUPPORTED"
    assert rest_api["status"] == "SUPPORTED_WITH_WARNINGS"
    assert rest_api["renderable"] is True
    assert "Core REST client" in rest_api["native_mapping"]
    assert rest_api_auth["status"] == "REVIEW_REQUIRED"
    assert rest_api_auth["renderable"] is False
    assert rest_api_secret_auth["status"] == "SUPPORTED_WITH_WARNINGS"
    assert rest_api_secret_auth["renderable"] is True
    assert "Secret Manager" in rest_api_secret_auth["native_mapping"]
    assert http_json["status"] == "SUPPORTED_WITH_WARNINGS"
    assert http_json["renderable"] is True
    assert http_json_secret_auth["status"] == "SUPPORTED_WITH_WARNINGS"
    assert http_json_secret_auth["renderable"] is True
    assert http_csv["status"] == "SUPPORTED_WITH_WARNINGS"
    assert http_csv["renderable"] is True
    assert http_file_json["status"] == "SUPPORTED_WITH_WARNINGS"
    assert http_file_json["renderable"] is True
    assert "NDJSON" in http_file_json["native_mapping"]
    assert http_file_text["status"] == "SUPPORTED_WITH_WARNINGS"
    assert http_file_text["renderable"] is True
    assert "line-oriented NDJSON" in http_file_text["native_mapping"]
    assert http_file_parquet["status"] == "SUPPORTED_WITH_WARNINGS"
    assert http_file_parquet["renderable"] is True
    assert "PARQUET" in http_file_parquet["native_mapping"]
    assert http_file_missing_format["status"] == "REVIEW_REQUIRED"
    assert http_file_missing_format["renderable"] is False
    assert http_text["status"] == "SUPPORTED_WITH_WARNINGS"
    assert http_text["renderable"] is True
    assert "line-oriented NDJSON" in http_text["native_mapping"]
    assert http_text_secret_auth["status"] == "SUPPORTED_WITH_WARNINGS"
    assert http_text_secret_auth["renderable"] is True
    assert http_text_inline_auth["status"] == "REVIEW_REQUIRED"
    assert http_text_inline_auth["renderable"] is False
    assert kafka["status"] == "REVIEW_REQUIRED"
    assert delta["status"] == "REVIEW_REQUIRED"
    assert delta_table["status"] == "REVIEW_REQUIRED"
    assert delta_share["status"] == "REVIEW_REQUIRED"
    assert native_passthrough["status"] == "REVIEW_REQUIRED"
    assert oracle["status"] == "REVIEW_REQUIRED"
    assert unknown["status"] == "UNSUPPORTED"
    assert "connection" not in catalog


def test_gcp_plan_contract_returns_runtime_parity_warning() -> None:
    result = plan_gcp_contract(_contract(), environment=_environment())

    assert result.status == "SUPPORTED_WITH_WARNINGS"
    assert result.plan is not None
    assert result.plan.platform == GCP_SUBTARGET_BIGQUERY
    assert any(warning.code == "GCP_STABLE_SURFACE_SCOPE" for warning in result.warnings)


def test_gcp_render_contract_emits_bigquery_bundle() -> None:
    artifacts = render_gcp_contract(_contract(), environment=_environment()).artifacts
    prefix = "test-project_bronze_orders"

    assert f"{prefix}.gcp.review.md" in artifacts
    assert f"{prefix}.gcp.capabilities.json" in artifacts
    assert f"{prefix}.gcp.source_support.json" in artifacts
    assert f"{prefix}.gcp.source_review.json" in artifacts
    assert f"{prefix}.gcp.source_review.md" in artifacts
    assert f"{prefix}.gcp.schema_policy.json" in artifacts
    assert f"{prefix}.gcp.write.sql" in artifacts
    assert f"{prefix}.gcp.evidence_ddl.sql" in artifacts
    assert f"{prefix}.gcp.contract.json" in artifacts
    assert f"{prefix}.gcp.manifest.json" in artifacts

    review = artifacts[f"{prefix}.gcp.review.md"]
    assert "GCP BigQuery Planning Review" in review
    assert "`test-project`" in review
    assert "`contractforge_ops`" in review

    capabilities = json.loads(artifacts[f"{prefix}.gcp.capabilities.json"])
    assert capabilities["runtime"]["project_id"] == "test-project"
    assert capabilities["runtime"]["status"] == "single_contract_smoke_available"
    assert capabilities["supports"]["upsert"] is True
    assert capabilities["supports"]["historical"] is False
    assert "historical" in capabilities["review_required_semantics"]

    write_sql = artifacts[f"{prefix}.gcp.write.sql"]
    assert "CREATE OR REPLACE TABLE `test-project.bronze.orders` AS" in write_sql
    assert "SELECT * FROM `raw.orders`" in write_sql

    ddl = artifacts[f"{prefix}.gcp.evidence_ddl.sql"]
    assert "CREATE SCHEMA IF NOT EXISTS `test-project.contractforge_ops`" in ddl
    assert "total_slot_ms INT64" in ddl
    assert "CREATE TABLE IF NOT EXISTS `test-project.contractforge_ops.contractforge_annotation_evidence`" in ddl
    assert "CREATE TABLE IF NOT EXISTS `test-project.contractforge_ops.contractforge_schema_evidence`" in ddl
    assert "CREATE TABLE IF NOT EXISTS `test-project.contractforge_ops.contractforge_governance_evidence`" in ddl
    assert "CREATE TABLE IF NOT EXISTS `test-project.contractforge_ops.contractforge_lineage_evidence`" in ddl

    schema_policy = json.loads(artifacts[f"{prefix}.gcp.schema_policy.json"])
    assert schema_policy["kind"] == "contractforge.gcp.bigquery_schema_policy_plan.v1"
    assert schema_policy["policy"]["policy"] == "permissive"
    assert schema_policy["status"] == "PLANNED_REVIEW_REQUIRED"
    assert "bronze.INFORMATION_SCHEMA.COLUMNS" in schema_policy["bigquery"]["preflight_queries"]["target_columns"]
    assert schema_policy["evidence"]["schema_evidence_table"] == "contractforge_schema_evidence"

    manifest = json.loads(artifacts[f"{prefix}.gcp.manifest.json"])
    assert manifest["artifact_summary"]["execution_model"] == "single_contract_bigquery_smoke"
    assert manifest["artifact_summary"]["deployable"] is True
    assert manifest["artifact_summary"]["orchestration_included"] is False

    deployment = json.loads(artifacts[f"{prefix}.gcp.deployment_manifest.json"])
    assert deployment["kind"] == "contractforge.gcp.deployment_manifest.v1"
    assert deployment["status"] == "supported"
    assert deployment["execution_ready"] is True
    assert deployment["target"]["table"] == "test-project.bronze.orders"
    assert deployment["execution_model"] == "single_contract_bigquery_smoke"
    assert deployment["orchestration"]["included"] is False
    assert [step["name"] for step in deployment["apply_order"]] == [
        "prepare_evidence",
        "write_target",
        "schema_evidence",
    ]
    assert any("--enforce-schema-policy is the validated live runtime path" in item for item in deployment["review_boundaries"])
    assert any("Automatic BigQuery type widening or mutation remains review-required" in item for item in deployment["review_boundaries"])
    assert deployment["artifact_summary"]["artifact_count"] >= 7


def test_gcp_render_contract_emits_rest_source_materialization_plan() -> None:
    contract = {
        "source": {
            "type": "rest_api",
            "request": {"url": "https://api.example.com/orders"},
            "read": {"columns": [{"name": "order_id", "type": "STRING"}, {"name": "amount", "type": "FLOAT64"}]},
        },
        "target": {"catalog": "test-project", "schema": "bronze", "table": "orders"},
        "mode": "overwrite",
    }

    artifacts = render_gcp_contract(contract, environment=_environment()).artifacts
    plan = json.loads(artifacts["test-project_bronze_orders.gcp.source_materialization.json"])

    assert plan["kind"] == "contractforge.gcp.bigquery_source_materialization.v1"
    assert plan["source_type"] == "rest_api"
    assert plan["reader"] == "contractforge_core.connectors.read_rest_api_records"
    assert plan["local_format"] == "ndjson"
    assert plan["destination_table"] == "test-project.bronze.orders"
    assert plan["source_format"] == "NEWLINE_DELIMITED_JSON"
    assert plan["write_disposition"] == "WRITE_TRUNCATE"
    assert plan["schema_fields"] == [
        {"name": "order_id", "type": "STRING"},
        {"name": "amount", "type": "FLOAT64"},
    ]


def test_gcp_render_contract_emits_secret_manager_review_plan_for_authenticated_rest() -> None:
    contract = {
        "source": {
            "type": "rest_api",
            "request": {"url": "https://api.example.com/orders"},
            "auth": {"type": "bearer_token", "token": "{{ secret:gcp/api-token }}"},
            "read": {"columns": [{"name": "order_id", "type": "STRING"}]},
        },
        "target": {"catalog": "test-project", "schema": "bronze", "table": "orders"},
        "mode": "overwrite",
    }

    result = plan_gcp_contract(contract, environment=_environment())
    artifacts = render_gcp_contract(contract, environment=_environment()).artifacts
    plan = json.loads(artifacts["test-project_bronze_orders.gcp.source_secret_resolution.json"])
    body = artifacts["test-project_bronze_orders.gcp.source_secret_resolution.json"]

    assert result.status == "SUPPORTED_WITH_WARNINGS"
    assert plan["kind"] == "contractforge.gcp.source_secret_resolution_plan.v1"
    assert plan["status"] == "PLANNED"
    assert plan["execution"]["included"] is True
    assert plan["auth_redacted"]["token"] == "***REDACTED***"
    assert plan["secret_manager"]["project_id"] == "test-project"
    assert plan["secret_manager"]["runtime_service_account"] == "contractforge@test-project.iam.gserviceaccount.com"
    assert plan["secret_manager"]["required_role"] == "roles/secretmanager.secretAccessor"
    assert plan["secret_refs"][0]["contract_ref"] == "gcp/api-token"
    assert plan["secret_refs"][0]["suggested_secret_id"] == "gcp-api-token"
    assert plan["secret_refs"][0]["version_resource"] == "projects/test-project/secrets/gcp-api-token/versions/latest"
    assert "--role=roles/secretmanager.secretAccessor" in plan["secret_refs"][0]["iam_command"]
    assert "{{ secret:gcp/api-token }}" not in body
    assert "api-token }}" not in body


def test_gcp_secret_placeholder_runtime_resolution_uses_gcloud_access() -> None:
    from subprocess import CompletedProcess

    commands: list[list[str]] = []

    def fake_runner(command):
        commands.append(list(command))
        return CompletedProcess(command, 0, stdout="resolved-token\n", stderr="")

    resolved = resolve_gcp_secret_placeholders(
        {"auth": {"type": "bearer_token", "token": "{{ secret:gcp/api-token }}"}},
        project_id="test-project",
        runner=fake_runner,
    )

    assert resolved["auth"]["token"] == "resolved-token"
    assert commands == [
        [
            "gcloud",
            "secrets",
            "versions",
            "access",
            "latest",
            "--secret=gcp-api-token",
            "--project=test-project",
        ]
    ]


def test_gcp_secret_resolution_plan_records_inline_auth_blocker() -> None:
    from contractforge_core.contracts import semantic_contract_from_mapping
    from contractforge_gcp.environment import GCPEnvironment

    contract = semantic_contract_from_mapping(
        {
            "source": {
                "type": "http_json",
                "request": {"url": "https://api.example.com/orders.json"},
                "auth": {"type": "bearer_token", "token": "raw-token"},
            },
            "target": {"catalog": "test-project", "schema": "bronze", "table": "orders"},
            "mode": "overwrite",
        }
    )

    plan = json.loads(render_gcp_source_secret_resolution_plan(contract, GCPEnvironment(project_id="test-project")))

    assert plan["blockers"] == [
        {
            "code": "NO_SECRET_PLACEHOLDER",
            "message": "Authenticated GCP REST/HTTP sources must use {{ secret:scope/key }} placeholders before rendering an executable runtime path.",
        }
    ]
    assert plan["auth_redacted"]["token"] == "***REDACTED***"
    assert plan["secret_refs"] == []


def test_gcp_secret_placeholder_refs_are_field_scoped() -> None:
    refs = secret_placeholder_refs(
        {
            "auth": {
                "username": "svc",
                "password": "{{ secret:gcp/basic-password }}",
                "headers": {"X-Token": "Bearer {{ secret:gcp/header-token }}"},
            }
        }
    )

    assert [(ref.field_path, ref.contract_ref, ref.suggested_secret_id) for ref in refs] == [
        ("$.auth.password", "gcp/basic-password", "gcp-basic-password"),
        ("$.auth.headers.X-Token", "gcp/header-token", "gcp-header-token"),
    ]


def test_gcp_schema_policy_plans_are_conservative() -> None:
    from contractforge_core.contracts import semantic_contract_from_mapping
    from contractforge_gcp.environment import GCPEnvironment

    strict = semantic_contract_from_mapping({**_contract(), "schema_policy": "strict"})
    additive = semantic_contract_from_mapping({**_contract(), "schema_policy": "additive_only"})
    permissive = semantic_contract_from_mapping({**_contract(), "schema_policy": "permissive"})

    strict_plan = plan_bigquery_schema_policy(strict)
    additive_plan = plan_bigquery_schema_policy(additive)
    permissive_plan = plan_bigquery_schema_policy(permissive)

    assert strict_plan.preflight_required is True
    assert strict_plan.writer_options == {}
    assert "Strict schema" in strict_plan.reason
    assert additive_plan.writer_options == {
        "schemaUpdateOptions": "ALLOW_FIELD_ADDITION when an explicit nullable schema is supplied"
    }
    assert "explicit schema" in additive_plan.warnings[0]
    assert any("Permissive does not mean automatic BigQuery type changes" in item for item in permissive_plan.warnings)
    assert any("blocked by the stable runtime path" in item for item in permissive_plan.warnings)

    rendered = json.loads(render_bigquery_schema_policy_plan(additive, GCPEnvironment.from_contract(_environment())))
    assert rendered["target"]["table_id"] == "test-project.bronze.orders"
    assert [hint["name"] for hint in rendered["bigquery"]["apply_hints"]] == [
        "nullable_field_addition",
        "alter_table_add_column",
    ]
    assert "ALLOW_FIELD_ADDITION" in rendered["review_boundaries"][2]
    assert "type widening or mutation remains review-required" in rendered["review_boundaries"][3]


def test_gcp_source_review_redacts_contract_secrets_and_records_graduation_gates() -> None:
    contract = {
        "source": {
            "type": "rest_api",
            "request": {"url": "https://api.example.com/orders"},
            "auth": {"type": "bearer_token", "token": "raw-token"},
        },
        "target": {"catalog": "test-project", "schema": "bronze", "table": "orders"},
        "mode": "overwrite",
    }

    artifacts = render_gcp_contract(contract, environment=_environment()).artifacts
    review = json.loads(artifacts["test-project_bronze_orders.gcp.source_review.json"])
    markdown = artifacts["test-project_bronze_orders.gcp.source_review.md"]

    assert review["source_type"] == "rest_api"
    assert review["status"] == "REVIEW_REQUIRED"
    assert review["source_redacted"]["auth"]["token"] == "***REDACTED***"
    assert any("real GCP smoke" in item for item in review["graduation_gates"])
    assert "raw-token" not in markdown
    assert gcp_source_review_payload(contract["source"])["source_redacted"]["auth"]["token"] == "***REDACTED***"


def test_gcp_source_review_accepts_classifier_source_shapes() -> None:
    table_review = gcp_source_review_payload("table")
    unknown_review = gcp_source_review_payload(None)
    raw_iceberg_review = gcp_source_review_payload({"type": "iceberg_table", "path": "gs://bucket/iceberg/orders"})
    delta_share_review = gcp_source_review_payload({"type": "delta_share", "profile_file": "profile.json"})
    kafka_review = gcp_source_review_payload({"type": "kafka_available_now", "topic": "orders"})
    sqlserver_review = gcp_source_review_payload({"type": "sqlserver", "table": "dbo.orders"})
    http_text_review = gcp_source_review_payload({"type": "http_text", "request": {"url": "https://api.example.com/x.txt"}})

    assert table_review["status"] == "SUPPORTED"
    assert table_review["renderable"] is True
    assert table_review["promotion_path"] == {}
    assert is_gcp_source_renderable("table") is True
    assert unknown_review["status"] == "UNSUPPORTED"
    assert unknown_review["renderable"] is False
    assert is_gcp_source_renderable(None) is False
    assert raw_iceberg_review["promotion_path"]["candidate_runtime"].startswith("Register the raw Iceberg location")
    assert "gs://bucket/iceberg/orders" in raw_iceberg_review["promotion_path"]["required_bindings"][2]
    assert any("registered table access" in item for item in raw_iceberg_review["promotion_path"]["blockers"])
    assert delta_share_review["promotion_path"]["candidate_runtime"].startswith("Materialize Delta or Delta Sharing")
    assert any("Manual export/import" in item for item in delta_share_review["promotion_path"]["blockers"])
    assert kafka_review["promotion_path"]["candidate_runtime"].startswith("Dataflow or Pub/Sub staging")
    assert any("offsets" in item for item in kafka_review["promotion_path"]["evidence_required"])
    assert sqlserver_review["promotion_path"]["candidate_runtime"].startswith("Dataflow JDBC to BigQuery")
    assert any("driver JAR" in item for item in sqlserver_review["promotion_path"]["required_bindings"])
    assert http_text_review["status"] == "SUPPORTED_WITH_WARNINGS"
    assert http_text_review["promotion_path"] == {}


def test_gcp_source_review_markdown_includes_non_jdbc_promotion_path() -> None:
    markdown = render_gcp_source_review_markdown({"type": "delta_share", "profile_file": "profile.json"})

    assert "## Promotion Path" in markdown
    assert "Materialize Delta or Delta Sharing data through Dataproc/Spark" in markdown
    assert "Manual export/import or notebook-only materialization is not acceptable promotion evidence." in markdown


def test_gcp_render_contract_emits_source_family_promotion_plan_for_raw_iceberg_path() -> None:
    contract = {
        "source": {"type": "iceberg_table", "path": "gs://bucket/iceberg/orders"},
        "target": {"catalog": "test-project", "schema": "bronze", "table": "orders"},
        "mode": "overwrite",
    }

    artifacts = render_gcp_contract(contract, environment=_environment()).artifacts
    plan = json.loads(artifacts["test-project_bronze_orders.gcp.source_promotion_plan.json"])

    assert plan["kind"] == "contractforge.gcp.source_family_promotion_plan.v1"
    assert plan["source_type"] == "iceberg_table"
    assert plan["status"] == "PLANNED_REVIEW_REQUIRED"
    assert plan["execution"]["included"] is True
    assert "source-promotion" in plan["execution"]["command"]
    assert plan["stable_boundary"] == {
        "current_gate": "GCP-BQ-20E",
        "decision": "RAW_ICEBERG_REGISTRATION_COMMAND_INCLUDED_FULL_SOURCE_PARITY_PENDING",
        "future_gate": "GCP-BQ-20",
    }
    assert plan["promotion_path"]["candidate_runtime"].startswith("Register the raw Iceberg location")
    assert "gs://bucket/iceberg/orders" in plan["promotion_path"]["required_bindings"][2]
    registration = plan["biglake_iceberg_registration"]
    assert registration["kind"] == "contractforge.gcp.biglake_iceberg_registration_plan.v1"
    assert registration["source_storage_uri"] == "gs://bucket/iceberg/orders/"
    assert registration["registered_table"] == "test-project.contractforge.registered_orders"
    assert registration["bq_table_arg"] == "test-project:contractforge.registered_orders"
    assert registration["table_options"] == {
        "file_format": "PARQUET",
        "managed_table_type": "BIGLAKE",
        "table_format": "ICEBERG",
    }
    assert registration["schema"] == "{{ parameter:gcp.biglake.schema }}"
    assert "--managed_table_type=BIGLAKE" in registration["bq_mk_command"]
    assert "--table_format=ICEBERG" in registration["bq_mk_command"]
    assert "--storage_uri=gs://bucket/iceberg/orders/" in registration["bq_mk_command"]
    assert registration["post_registration_source"] == {
        "type": "iceberg_table",
        "table": "test-project.contractforge.registered_orders",
    }


def test_gcp_source_family_promotion_plan_accepts_explicit_biglake_registration_binding() -> None:
    plan = json.loads(
        render_gcp_source_promotion_plan(
            {
                "type": "iceberg_table",
                "path": "gs://bucket/lake/orders",
                "registration": {
                    "project_id": "analytics-project",
                    "dataset": "raw",
                    "table": "orders_iceberg",
                    "location": "us-east1",
                    "connection_id": "analytics-project.us-east1.cf_biglake",
                    "connection_service_account": "bqcx-123@example.iam.gserviceaccount.com",
                    "schema": [
                        {"name": "order_id", "type": "INT64"},
                        {"name": "status", "type": "STRING"},
                    ],
                },
            }
        )
    )

    registration = plan["biglake_iceberg_registration"]
    assert registration["registered_table"] == "analytics-project.raw.orders_iceberg"
    assert registration["connection"] == {
        "connection_id": "analytics-project.us-east1.cf_biglake",
        "location": "us-east1",
        "required_storage_role": "roles/storage.objectAdmin",
        "service_account": "bqcx-123@example.iam.gserviceaccount.com",
    }
    assert registration["bq_mk_command"] == [
        "bq",
        "--location",
        "us-east1",
        "mk",
        "--table",
        "--connection_id=analytics-project.us-east1.cf_biglake",
        "--managed_table_type=BIGLAKE",
        "--table_format=ICEBERG",
        "--file_format=PARQUET",
        "--storage_uri=gs://bucket/lake/orders/",
        "analytics-project:raw.orders_iceberg",
        "order_id:INT64,status:STRING",
    ]


def test_gcp_source_promotion_executes_biglake_registration_with_readback() -> None:
    calls: list[list[str]] = []

    class Completed:
        def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def runner(command: list[str], **_: object) -> Completed:
        calls.append(command)
        if command[:3] == ["bq", "--format=prettyjson", "show"]:
            return Completed(
                0,
                json.dumps(
                    {
                        "biglakeConfiguration": {
                            "storageUri": "gs://bucket/lake/orders/",
                            "tableFormat": "ICEBERG",
                            "fileFormat": "PARQUET",
                        },
                        "schema": {
                            "fields": [
                                {"name": "order_id", "type": "INTEGER"},
                                {"name": "status", "type": "STRING"},
                                {"name": "amount", "type": "FLOAT"},
                            ]
                        },
                        "numRows": "3",
                    }
                ),
            )
        return Completed(0, "created")

    result = run_gcp_source_promotion(
        {
            "type": "iceberg_table",
            "path": "gs://bucket/lake/orders",
            "registration": {
                "project_id": "analytics-project",
                "dataset": "raw",
                "table": "orders_iceberg",
                "location": "us-east1",
                "connection_id": "analytics-project.us-east1.cf_biglake",
                "schema": "order_id:INT64,status:STRING,amount:FLOAT64",
            },
        },
        execute=True,
        readback=True,
        runner=runner,
    )

    assert result["status"] == "SUCCEEDED"
    assert [operation["name"] for operation in result["operations"]] == [
        "register_biglake_iceberg_table",
        "readback_biglake_iceberg_table",
    ]
    assert calls[0] == [
        "bq",
        "--location",
        "us-east1",
        "mk",
        "--table",
        "--connection_id=analytics-project.us-east1.cf_biglake",
        "--managed_table_type=BIGLAKE",
        "--table_format=ICEBERG",
        "--file_format=PARQUET",
        "--storage_uri=gs://bucket/lake/orders/",
        "analytics-project:raw.orders_iceberg",
        "order_id:INT64,status:STRING,amount:FLOAT64",
    ]
    assert calls[1] == ["bq", "--format=prettyjson", "show", "analytics-project:raw.orders_iceberg"]
    assert all(assertion["passed"] for assertion in result["readback_assertions"])
    assert result["operations"][1]["num_rows"] == "3"


def test_gcp_source_promotion_keeps_delta_plan_non_executable() -> None:
    result = run_gcp_source_promotion(
        {"type": "delta_share", "profile_file": "profile.json", "table": "share.schema.orders"},
        execute=True,
    )

    assert result["status"] == "PLANNED_NOT_EXECUTED"
    assert result["source_type"] == "delta_share"
    assert "no adapter-owned execution path" in result["reason"]
    assert result["plan"]["delta_materialization"]["status"] == "REVIEW_REQUIRED"


def test_gcp_source_family_promotion_plan_emits_delta_sharing_materialization_plan() -> None:
    plan = json.loads(
        render_gcp_source_promotion_plan(
            {
                "type": "delta_share",
                "profile_file": "{{ secret:gcp/delta_share_profile }}",
                "table": "share.schema.orders",
                "materialization": {
                    "project_id": "analytics-project",
                    "location": "us-east1",
                    "staging_bucket": "cf-gcp-staging",
                    "output_table": "analytics-project.raw.delta_share_orders",
                },
            }
        )
    )

    materialization = plan["delta_materialization"]
    assert materialization["kind"] == "contractforge.gcp.delta_materialization_plan.v1"
    assert materialization["status"] == "REVIEW_REQUIRED"
    assert materialization["source_type"] == "delta_share"
    assert materialization["source_identity"] == "share.schema.orders"
    assert materialization["landing_prefix"] == "gs://cf-gcp-staging/contractforge/delta-materialized/share_schema_orders/"
    assert materialization["output_table"] == "analytics-project.raw.delta_share_orders"
    assert materialization["dependency_set"] == ["delta-sharing-spark", "google-cloud-bigquery"]
    assert "Secret Manager" in materialization["credential_binding"]
    assert materialization["post_materialization_source"] == {
        "type": "table",
        "table": "analytics-project.raw.delta_share_orders",
    }
    assert any("Manual export/import" in item for item in materialization["non_claims"])


def test_gcp_source_family_promotion_plan_emits_dataflow_kafka_available_now_plan() -> None:
    plan = json.loads(
        render_gcp_source_promotion_plan(
            {
                "type": "kafka_available_now",
                "bootstrap_servers": "pkc-123.us-east1.gcp.confluent.cloud:9092",
                "topic": "orders",
                "consumer_group_id": "contractforge-gcp-orders",
                "auth": {
                    "mode": "SASL_PLAIN",
                    "username_secret_id": "projects/p/secrets/kafka-user/versions/latest",
                    "password_secret_id": "projects/p/secrets/kafka-password/versions/latest",
                },
                "output": {
                    "table": "analytics-project:raw.kafka_orders",
                    "deadletter_table": "analytics-project:raw.kafka_orders_dlq",
                },
                "dataflow": {"project_id": "analytics-project", "location": "us-east1", "temp_location": "gs://cf-gcp-staging/tmp"},
            }
        )
    )

    streaming = plan["dataflow_streaming"]
    assert streaming["kind"] == "contractforge.gcp.dataflow_streaming_promotion_plan.v1"
    assert streaming["status"] == "REVIEW_REQUIRED"
    assert streaming["source_type"] == "kafka_available_now"
    assert streaming["provider"] == "kafka"
    assert streaming["template"]["name"] == "Kafka_to_BigQuery_Flex"
    assert streaming["temp_location"] == "gs://cf-gcp-staging/tmp/"
    assert streaming["job_name"] == "cf-orders-stream"
    assert streaming["checkpoint_location"] == "gs://{{ parameter:gcp.staging_bucket }}/dataflow/checkpoints/orders/"
    assert streaming["parameters"]["readBootstrapServerAndTopic"] == "pkc-123.us-east1.gcp.confluent.cloud:9092;orders"
    assert streaming["parameters"]["writeMode"] == "SINGLE_TABLE_NAME"
    assert streaming["parameters"]["outputTableSpec"] == "analytics-project:raw.kafka_orders"
    assert streaming["parameters"]["outputDeadletterTable"] == "analytics-project:raw.kafka_orders_dlq"
    assert streaming["parameters"]["kafkaReadAuthenticationMode"] == "SASL_PLAIN"
    assert streaming["parameters"]["enableCommitOffsets"] == "true"
    assert streaming["parameters"]["consumerGroupId"] == "contractforge-gcp-orders"
    assert streaming["parameters"]["kafkaReadOffset"] == "earliest"
    assert streaming["parameters"]["kafkaReadUsernameSecretId"] == "projects/p/secrets/kafka-user/versions/latest"
    assert streaming["parameters"]["kafkaReadPasswordSecretId"] == "projects/p/secrets/kafka-password/versions/latest"
    assert any("Kafka_to_BigQuery" in item for item in streaming["launch_command"])
    assert streaming["readback_commands"]["describe_job"][0:4] == ["gcloud", "dataflow", "jobs", "describe"]
    assert streaming["readback_commands"]["count_output_table"] == [
        "bq",
        "--format=json",
        "query",
        "--use_legacy_sql=false",
        "SELECT COUNT(*) AS row_count FROM `analytics-project.raw.kafka_orders`",
    ]
    assert streaming["readback_commands"]["count_dlq_table"] == [
        "bq",
        "--format=json",
        "query",
        "--use_legacy_sql=false",
        "SELECT COUNT(*) AS row_count FROM `analytics-project.raw.kafka_orders_dlq`",
    ]
    assert any("starting offsets" in item for item in streaming["evidence_required"])
    assert any("continuous Dataflow job" in item for item in streaming["non_claims"])


def test_gcp_source_promotion_executes_dataflow_streaming_with_readback() -> None:
    calls: list[list[str]] = []

    class Completed:
        def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def runner(command: list[str], **_: object) -> Completed:
        calls.append(command)
        if command[:4] == ["gcloud", "dataflow", "flex-template", "run"]:
            return Completed(0, json.dumps({"job": {"id": "2026-06-17_10_00_00-1234567890"}}))
        if command[:4] == ["gcloud", "dataflow", "jobs", "describe"]:
            return Completed(0, json.dumps({"id": "2026-06-17_10_00_00-1234567890", "currentState": "JOB_STATE_RUNNING"}))
        if command[:3] == ["bq", "--format=json", "query"]:
            return Completed(0, json.dumps([{"row_count": "3"}]))
        return Completed(1, "", "unexpected command")

    result = run_gcp_source_promotion(
        {
            "type": "kafka_available_now",
            "bootstrap_servers": "pkc-123.us-east1.gcp.confluent.cloud:9092",
            "topic": "orders",
            "consumer_group_id": "contractforge-gcp-orders",
            "auth": {
                "mode": "SASL_PLAIN",
                "username_secret_id": "projects/p/secrets/kafka-user/versions/latest",
                "password_secret_id": "projects/p/secrets/kafka-password/versions/latest",
            },
            "output": {
                "table": "analytics-project:raw.kafka_orders",
                "deadletter_table": "analytics-project:raw.kafka_orders_dlq",
            },
            "dataflow": {"project_id": "analytics-project", "location": "us-east1", "temp_location": "gs://cf-gcp-staging/tmp"},
        },
        execute=True,
        readback=True,
        runner=runner,
    )

    assert result["status"] == "SUCCEEDED"
    assert [operation["name"] for operation in result["operations"]] == [
        "launch_dataflow_kafka_to_bigquery",
        "readback_dataflow_job",
        "readback_bigquery_output_table",
        "readback_bigquery_dlq_table",
    ]
    assert calls[0][:8] == [
        "gcloud",
        "dataflow",
        "flex-template",
        "run",
        "cf-orders-stream",
        "--region",
        "us-east1",
        "--project",
    ]
    assert "gs://dataflow-templates-us-east1/latest/flex/Kafka_to_BigQuery_Flex" in calls[0]
    assert "--parameters" in calls[0]
    rendered_parameters = calls[0][calls[0].index("--parameters") + 1]
    assert rendered_parameters.startswith("^~^")
    assert "readBootstrapServerAndTopic=pkc-123.us-east1.gcp.confluent.cloud:9092;orders" in rendered_parameters
    assert "kafkaReadAuthenticationMode=SASL_PLAIN" in rendered_parameters
    assert calls[1] == [
        "gcloud",
        "dataflow",
        "jobs",
        "describe",
        "2026-06-17_10_00_00-1234567890",
        "--region",
        "us-east1",
        "--project",
        "analytics-project",
        "--format=json",
    ]
    assert calls[2] == [
        "bq",
        "--format=json",
        "query",
        "--use_legacy_sql=false",
        "SELECT COUNT(*) AS row_count FROM `analytics-project.raw.kafka_orders`",
    ]
    assert calls[3] == [
        "bq",
        "--format=json",
        "query",
        "--use_legacy_sql=false",
        "SELECT COUNT(*) AS row_count FROM `analytics-project.raw.kafka_orders_dlq`",
    ]
    assert result["operations"][1]["current_state"] == "JOB_STATE_RUNNING"
    assert result["operations"][2]["row_count"] == 3
    assert result["operations"][3]["row_count"] == 3
    assert "row, DLQ, offset, checkpoint" in result["review_boundary"]


def test_gcp_source_family_promotion_plan_emits_eventhubs_provider_context() -> None:
    plan = json.loads(
        render_gcp_source_promotion_plan(
            {
                "type": "eventhubs_available_now",
                "bootstrap_servers": "namespace.servicebus.windows.net:9093",
                "topic": "orders",
            }
        )
    )

    streaming = plan["dataflow_streaming"]
    assert streaming["provider"] == "eventhubs_kafka"
    assert streaming["parameters"]["readBootstrapServerAndTopic"] == "namespace.servicebus.windows.net:9093;orders"


def test_gcp_source_family_promotion_plan_emits_sqlserver_jdbc_plan() -> None:
    plan = json.loads(
        render_gcp_source_promotion_plan(
            {
                "type": "sqlserver",
                "url": "jdbc:sqlserver://server.database.windows.net:1433;database=contractforge",
                "query": "SELECT id, status, amount FROM dbo.orders",
                "driver_jars": ["gs://cf-gcp-drivers/mssql-jdbc.jar"],
                "auth": {
                    "username_secret_id": "projects/p/secrets/sql-user/versions/latest",
                    "password_secret_id": "projects/p/secrets/sql-password/versions/latest",
                },
                "output": {
                    "table": "analytics-project:raw.sqlserver_orders",
                    "create_disposition": "CREATE_NEVER",
                },
                "dataflow": {
                    "project_id": "analytics-project",
                    "location": "us-east1",
                    "temp_location": "gs://cf-gcp-staging/tmp",
                    "staging_location": "gs://cf-gcp-staging/staging",
                    "network": "default",
                    "subnetwork": "regions/us-east1/subnetworks/default",
                    "disable_public_ips": True,
                    "service_account_email": "contractforge-dataflow@analytics-project.iam.gserviceaccount.com",
                    "fetch_size": 1000,
                    "max_workers": 1,
                },
            }
        )
    )

    jdbc = plan["dataflow_jdbc"]
    assert jdbc["kind"] == "contractforge.gcp.dataflow_jdbc_promotion_plan.v1"
    assert jdbc["status"] == "REVIEW_REQUIRED"
    assert jdbc["source_type"] == "sqlserver"
    assert jdbc["template"]["name"] == "Jdbc_to_BigQuery_Flex"
    assert jdbc["temp_location"] == "gs://cf-gcp-staging/tmp/"
    assert jdbc["job_name"] == "cf-sqlserver_orders-jdbc"
    assert jdbc["parameters"]["driverJars"] == "gs://cf-gcp-drivers/mssql-jdbc.jar"
    assert jdbc["parameters"]["driverClassName"] == "com.microsoft.sqlserver.jdbc.SQLServerDriver"
    assert jdbc["parameters"]["connectionURL"].startswith("jdbc:sqlserver://")
    assert jdbc["parameters"]["query"] == "SELECT id, status, amount FROM dbo.orders"
    assert jdbc["parameters"]["outputTable"] == "analytics-project:raw.sqlserver_orders"
    assert jdbc["parameters"]["bigQueryLoadingTemporaryDirectory"] == "gs://cf-gcp-staging/tmp/bq-load/"
    assert jdbc["parameters"]["username"] == "projects/p/secrets/sql-user/versions/latest"
    assert jdbc["parameters"]["password"] == "projects/p/secrets/sql-password/versions/latest"
    assert jdbc["parameters"]["fetchSize"] == "1000"
    assert jdbc["parameters"]["createDisposition"] == "CREATE_NEVER"
    assert jdbc["launch_options"]["network"] == "default"
    assert jdbc["launch_options"]["subnetwork"] == "regions/us-east1/subnetworks/default"
    assert jdbc["launch_options"]["disable_public_ips"] is True
    assert jdbc["launch_options"]["service_account_email"] == "contractforge-dataflow@analytics-project.iam.gserviceaccount.com"
    assert jdbc["launch_options"]["staging_location"] == "gs://cf-gcp-staging/staging"
    assert jdbc["launch_options"]["temp_location"] == "gs://cf-gcp-staging/tmp/"
    assert jdbc["launch_options"]["max_workers"] == "1"
    assert any("Jdbc_to_BigQuery" in item for item in jdbc["launch_command"])
    assert "--disable-public-ips" in jdbc["launch_command"]
    assert "regions/us-east1/subnetworks/default" in jdbc["launch_command"]
    assert jdbc["readback_commands"]["count_output_table"] == [
        "bq",
        "--format=json",
        "query",
        "--use_legacy_sql=false",
        "SELECT COUNT(*) AS row_count FROM `analytics-project.raw.sqlserver_orders`",
    ]
    assert plan["stable_boundary"]["current_gate"] == "GCP-BQ-20F"


def test_gcp_source_promotion_executes_dataflow_jdbc_with_readback() -> None:
    calls: list[list[str]] = []

    class Completed:
        def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def runner(command: list[str], **_: object) -> Completed:
        calls.append(command)
        if command[:4] == ["gcloud", "dataflow", "flex-template", "run"]:
            return Completed(0, json.dumps({"job": {"id": "2026-06-17_12_00_00-1234567890"}}))
        if command[:4] == ["gcloud", "dataflow", "jobs", "describe"]:
            return Completed(0, json.dumps({"id": "2026-06-17_12_00_00-1234567890", "currentState": "JOB_STATE_DONE"}))
        if command[:3] == ["bq", "--format=json", "query"]:
            return Completed(0, json.dumps([{"row_count": "5"}]))
        return Completed(1, "", "unexpected command")

    result = run_gcp_source_promotion(
        {
            "type": "sqlserver",
            "url": "jdbc:sqlserver://server.database.windows.net:1433;database=contractforge",
            "query": "SELECT id, status, amount FROM dbo.orders",
            "driver_jars": "gs://cf-gcp-drivers/mssql-jdbc.jar",
            "auth": {
                "username_secret_id": "projects/p/secrets/sql-user/versions/latest",
                "password_secret_id": "projects/p/secrets/sql-password/versions/latest",
            },
            "output": {"table": "analytics-project:raw.sqlserver_orders"},
            "dataflow": {"project_id": "analytics-project", "location": "us-east1", "temp_location": "gs://cf-gcp-staging/tmp"},
        },
        execute=True,
        readback=True,
        runner=runner,
    )

    assert result["status"] == "SUCCEEDED"
    assert [operation["name"] for operation in result["operations"]] == [
        "launch_dataflow_jdbc_to_bigquery",
        "readback_dataflow_job",
        "readback_bigquery_output_table",
    ]
    assert "gs://dataflow-templates-us-east1/latest/flex/Jdbc_to_BigQuery_Flex" in calls[0]
    rendered_parameters = calls[0][calls[0].index("--parameters") + 1]
    assert "driverClassName=com.microsoft.sqlserver.jdbc.SQLServerDriver" in rendered_parameters
    assert "outputTable=analytics-project:raw.sqlserver_orders" in rendered_parameters
    assert calls[1] == [
        "gcloud",
        "dataflow",
        "jobs",
        "describe",
        "2026-06-17_12_00_00-1234567890",
        "--region",
        "us-east1",
        "--project",
        "analytics-project",
        "--format=json",
    ]
    assert result["operations"][1]["current_state"] == "JOB_STATE_DONE"
    assert result["operations"][2]["row_count"] == 5
    assert "GCP-BQ-20F" in result["review_boundary"]


def test_gcp_source_family_promotion_plan_noops_for_supported_table_source() -> None:
    assert render_gcp_source_promotion_plan({"type": "table", "table": "raw.orders"}) == ""


def test_gcp_render_contract_emits_dataplex_quality_plan_for_review() -> None:
    from contractforge_core.contracts import semantic_contract_from_mapping
    from contractforge_gcp.environment import GCPEnvironment

    contract = _contract()
    contract["quality_rules"] = {
        "required_columns": ["order_id"],
        "not_null": ["order_id"],
        "unique_key": ["order_id"],
        "accepted_values": {"status": ["paid", "open"]},
        "min_rows": 1,
        "max_null_ratio": {"email": 0.2},
        "expressions": [{"name": "amount_positive", "expression": "amount > 0"}],
    }

    artifacts = render_gcp_contract(contract, environment=_environment()).artifacts
    payload = json.loads(artifacts["test-project_bronze_orders.gcp.dataplex_data_quality.json"])
    execution = json.loads(artifacts["test-project_bronze_orders.gcp.dataplex_data_quality_execution.json"])

    assert payload["kind"] == "contractforge.gcp.dataplex_data_quality_plan.v1"
    assert payload["status"] == "PLANNED_REVIEW_REQUIRED"
    assert payload["execution"]["included"] is False
    assert payload["create_request"]["parent"] == "projects/test-project/locations/us"
    assert payload["create_request"]["dataScanId"] == "cf-bronze-orders-dq"
    data_scan = payload["create_request"]["dataScan"]
    assert data_scan["data"]["resource"] == (
        "//bigquery.googleapis.com/projects/test-project/datasets/bronze/tables/orders"
    )
    assert data_scan["dataQualitySpec"]["postScanActions"]["bigqueryExport"]["resultsTable"] == (
        "projects/test-project/datasets/contractforge_ops/tables/contractforge_dataplex_quality_results"
    )
    rule_types = {rule["name"]: rule["type"] for rule in payload["mapped_rules"]}
    assert rule_types["order-id-not-null"] == "nonNullExpectation"
    assert rule_types["unique-key"] == "uniquenessExpectation"
    assert rule_types["status-accepted-values"] == "setExpectation"
    assert rule_types["min-rows"] == "tableConditionExpectation"
    assert rule_types["email-max-null-ratio"] == "rowConditionExpectation"
    assert rule_types["amount-positive"] == "rowConditionExpectation"
    assert payload["review_required_rules"] == [
        {
            "name": "required_columns",
            "reason": (
                "Dataplex DataQualityRule does not directly prove ContractForge required-column schema presence parity."
            ),
            "rule": "required_columns",
        }
    ]

    assert execution["kind"] == "contractforge.gcp.dataplex_data_quality_execution_plan.v1"
    assert execution["status"] == "PLANNED_REVIEW_REQUIRED"
    assert execution["execution"]["included"] is False
    assert execution["data_scan"]["name"] == "projects/test-project/locations/us/dataScans/cf-bronze-orders-dq"
    assert execution["rest"]["create"]["body"]["data"]["resource"] == (
        "//bigquery.googleapis.com/projects/test-project/datasets/bronze/tables/orders"
    )
    assert execution["rest"]["run"] == {
        "body": {},
        "method": "POST",
        "url": "https://dataplex.googleapis.com/v1/projects/test-project/locations/us/dataScans/cf-bronze-orders-dq:run",
    }
    assert execution["rest"]["list_jobs"]["url"] == (
        "https://dataplex.googleapis.com/v1/projects/test-project/locations/us/dataScans/cf-bronze-orders-dq/jobs"
    )
    assert execution["rest"]["get_job_template"]["url"].endswith("/jobs/{job_id}")
    assert execution["readback"]["job_state_path"] == "jobs[].state"
    assert execution["readback"]["bigquery_export_query"] == (
        "SELECT * FROM `test-project.contractforge_ops.contractforge_dataplex_quality_results` LIMIT 100"
    )
    assert (
        "https://docs.cloud.google.com/dataplex/docs/reference/rest/v1/projects.locations.dataScans/run"
        in execution["sources"]
    )

    deployment = json.loads(artifacts["test-project_bronze_orders.gcp.deployment_manifest.json"])
    assert "test-project_bronze_orders.gcp.dataplex_data_quality.json" not in {
        step["artifact"] for step in deployment["apply_order"]
    }
    assert "test-project_bronze_orders.gcp.dataplex_data_quality_execution.json" not in {
        step["artifact"] for step in deployment["apply_order"]
    }
    assert any("Dataplex data-quality artifacts are deterministic review plans" in item for item in deployment["review_boundaries"])

    semantic = semantic_contract_from_mapping(contract)
    env = GCPEnvironment.from_contract(_environment())
    assert has_dataplex_quality_plan(semantic) is True
    assert json.loads(render_dataplex_data_quality_plan(semantic, env))["target"]["location"] == "us"
    rendered_execution = json.loads(render_dataplex_data_quality_execution_plan(semantic, env))
    assert rendered_execution["data_scan"]["id"] == "cf-bronze-orders-dq"


def test_gcp_dataplex_quality_plan_noop_without_quality_rules() -> None:
    from contractforge_core.contracts import semantic_contract_from_mapping
    from contractforge_gcp.environment import GCPEnvironment

    semantic = semantic_contract_from_mapping(_contract())

    assert has_dataplex_quality_plan(semantic) is False
    assert render_dataplex_data_quality_plan(semantic, GCPEnvironment()) == ""
    assert render_dataplex_data_quality_execution_plan(semantic, GCPEnvironment()) == ""


def test_gcp_render_contract_emits_dataplex_lineage_and_aspect_plans() -> None:
    from contractforge_core.contracts import semantic_contract_from_mapping
    from contractforge_gcp.environment import GCPEnvironment

    contract = _contract()
    contract["annotations"] = {
        "table": {
            "description": "Orders table",
            "aliases": ["sales_orders"],
            "tags": {"domain": "sales", "product": "checkout"},
        },
        "columns": {
            "customer_email": {
                "description": "Customer email",
                "pii": {"enabled": True, "type": "email", "sensitivity": "confidential"},
            }
        },
    }
    contract["operations"] = {
        "criticality": "high",
        "expected_frequency": "daily",
        "freshness_sla_minutes": 60,
        "runbook_url": "https://runbooks.example/orders",
        "owners": ["data-platform"],
        "ownership": {"business_owner": "sales", "technical_owner": "data-eng"},
    }

    artifacts = render_gcp_contract(contract, environment=_environment()).artifacts
    lineage = json.loads(artifacts["test-project_bronze_orders.gcp.dataplex_lineage.json"])
    aspects = json.loads(artifacts["test-project_bronze_orders.gcp.dataplex_aspects.json"])

    assert lineage["kind"] == "contractforge.gcp.dataplex_lineage_plan.v1"
    assert lineage["status"] == "PLANNED_REVIEW_REQUIRED"
    assert lineage["execution"]["included"] is False
    assert lineage["target"]["bigquery_resource"] == (
        "//bigquery.googleapis.com/projects/test-project/datasets/bronze/tables/orders"
    )
    assert lineage["source"]["resource"] == (
        "//bigquery.googleapis.com/projects/test-project/datasets/raw/tables/orders"
    )
    assert lineage["openlineage_publication"]["url"] == (
        "https://datalineage.googleapis.com/v1/projects/test-project/locations/us:processOpenLineageRunEvent"
    )
    assert lineage["readback"]["search_links"]["url"] == (
        "https://datalineage.googleapis.com/v1/projects/test-project/locations/us:searchLinks"
    )
    assert any("bronze-to-gold real-account run" in item for item in lineage["review_boundaries"])
    assert "https://cloud.google.com/data-catalog/docs/reference/data-lineage/rest" in lineage["sources"]

    assert aspects["kind"] == "contractforge.gcp.dataplex_aspect_plan.v1"
    assert aspects["status"] == "PLANNED_REVIEW_REQUIRED"
    assert aspects["execution"]["included"] is False
    assert aspects["aspect_type"]["id"] == "contractforge-governance"
    assert aspects["aspect_type"]["reference"] == "test-project.us.contractforge-governance"
    assert aspects["modify_entry"]["url"] == "https://dataplex.googleapis.com/v1/projects/test-project/locations/us:modifyEntry"
    template_fields = aspects["aspect_type"]["create"]["body_template"]["metadataTemplate"]["recordFields"]
    assert [field["index"] for field in template_fields] == [1, 2, 3, 4, 5, 6, 7]
    data = aspects["modify_entry"]["body_template"]["entry"]["aspects"]["test-project.us.contractforge-governance"]["data"]
    payload = json.loads(data["contractforge_payload_json"])
    assert data["table_aliases"] == ["sales_orders"]
    assert json.loads(data["table_tags_json"]) == {"domain": "sales", "product": "checkout"}
    assert payload["table"]["aliases"] == ["sales_orders"]
    assert payload["table"]["tags"] == {"domain": "sales", "product": "checkout"}
    assert payload["columns"]["customer_email"]["pii"] == {
        "enabled": True,
        "sensitivity": "confidential",
        "type": "email",
    }
    assert json.loads(data["columns_json"])["customer_email"]["pii"]["type"] == "email"
    assert payload["operations"]["criticality"] == "high"
    assert payload["operations"]["runbook_url"] == "https://runbooks.example/orders"
    assert payload["operations"]["ownership"] == {"business_owner": "sales", "technical_owner": "data-eng"}
    assert json.loads(data["operations_json"])["criticality"] == "high"
    assert "modifyEntry" in aspects["sources"][1]

    deployment = json.loads(artifacts["test-project_bronze_orders.gcp.deployment_manifest.json"])
    apply_artifacts = {step["artifact"] for step in deployment["apply_order"]}
    assert "test-project_bronze_orders.gcp.dataplex_lineage.json" not in apply_artifacts
    assert "test-project_bronze_orders.gcp.dataplex_aspects.json" not in apply_artifacts
    assert any("Dataplex lineage artifacts are deterministic native API plans" in item for item in deployment["review_boundaries"])
    assert any("Dataplex aspect artifacts are deterministic taxonomy/apply/readback plans" in item for item in deployment["review_boundaries"])

    semantic = semantic_contract_from_mapping(contract)
    env = GCPEnvironment.from_contract(_environment())
    assert has_dataplex_lineage_plan(semantic) is True
    assert has_dataplex_aspect_plan(semantic) is True
    assert json.loads(render_dataplex_lineage_plan(semantic, env))["native_resource_publication"]["process"]["processId"] == (
        "cf-bronze-orders-scd0-overwrite"
    )
    assert json.loads(render_dataplex_aspect_plan(semantic, env))["readback"]["get_aspect_type"]["method"] == "GET"


def test_gcp_dataplex_aspect_plan_noop_without_richer_metadata() -> None:
    from contractforge_core.contracts import semantic_contract_from_mapping
    from contractforge_gcp.environment import GCPEnvironment

    semantic = semantic_contract_from_mapping(_contract())

    assert has_dataplex_lineage_plan(semantic) is True
    assert has_dataplex_aspect_plan(semantic) is False
    assert render_dataplex_aspect_plan(semantic, GCPEnvironment()) == ""


def test_gcp_dataplex_quality_runtime_plan_is_non_mutating_by_default() -> None:
    contract = _contract()
    contract["quality_rules"] = {"not_null": ["order_id"], "unique_key": ["order_id"]}

    result = run_dataplex_data_quality(contract, environment=_environment())

    assert result["status"] == "PLANNED_NOT_EXECUTED"
    assert result["execution_included"] is False
    assert result["plan"]["kind"] == "contractforge.gcp.dataplex_data_quality_execution_plan.v1"
    assert result["plan"]["rest"]["create"]["method"] == "POST"
    assert result["plan"]["rest"]["run"]["url"].endswith("/dataScans/cf-bronze-orders-dq:run")


def test_gcp_dataplex_quality_runtime_executes_with_injected_clients() -> None:
    import subprocess

    contract = _contract()
    contract["quality_rules"] = {"not_null": ["order_id"], "unique_key": ["order_id"]}
    commands: list[list[str]] = []
    requests: list[tuple[str, str]] = []

    def fake_runner(command):
        commands.append(list(command))
        if command[0] == "gcloud":
            return subprocess.CompletedProcess(command, 0, stdout="token\n", stderr="")
        if command[0] == "bq":
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps([{"rule_name": "order_id_not_null", "passed": "true"}]),
                stderr="",
            )
        raise AssertionError(f"Unexpected command: {command}")

    def fake_http(method, url, headers, body):
        requests.append((method, url))
        assert headers["Authorization"] == "Bearer token"
        if method == "POST" and url.endswith("?dataScanId=cf-bronze-orders-dq"):
            assert body["dataQualitySpec"]["rules"]
            return {"name": "projects/test-project/locations/us/operations/create-dq", "done": True}
        if method == "GET" and url.endswith("/dataScans/cf-bronze-orders-dq"):
            return {"name": "projects/test-project/locations/us/dataScans/cf-bronze-orders-dq"}
        if method == "POST" and url.endswith("/dataScans/cf-bronze-orders-dq:run"):
            return {"job": {"name": "projects/test-project/locations/us/dataScans/cf-bronze-orders-dq/jobs/job-1"}}
        if method == "GET" and url.endswith("/jobs/job-1"):
            return {"name": "job-1", "state": "SUCCEEDED"}
        if method == "DELETE" and url.endswith("/dataScans/cf-bronze-orders-dq"):
            return {"done": True}
        raise AssertionError(f"Unexpected request: {method} {url}")

    result = run_dataplex_data_quality(
        contract,
        environment=_environment(),
        execute=True,
        wait=True,
        readback=True,
        cleanup=True,
        runner=fake_runner,
        http_runner=fake_http,
    )

    assert result["status"] == "SUCCEEDED"
    assert result["create"]["status"] == "SUCCEEDED"
    assert result["job"]["state"] == "SUCCEEDED"
    assert result["readback"]["row_count"] == 1
    assert result["cleanup"]["done"] is True
    assert commands[0] == ["gcloud", "auth", "print-access-token"]
    assert commands[1][:5] == ["bq", "--project_id=test-project", "--location=US", "--format=json", "query"]
    assert [method for method, _ in requests] == ["POST", "GET", "POST", "GET", "DELETE"]


def test_gcp_dataplex_lineage_aspects_runtime_executes_with_injected_clients() -> None:
    import subprocess

    contract = _contract()
    contract["annotations"] = {
        "table": {"aliases": ["sales_orders"], "tags": {"domain": "sales"}},
        "columns": {"customer_email": {"pii": {"enabled": True, "type": "email", "sensitivity": "confidential"}}},
    }
    contract["operations"] = {"criticality": "high", "expected_frequency": "daily"}
    commands: list[list[str]] = []
    requests: list[tuple[str, str, dict[str, object] | None]] = []

    def fake_runner(command):
        commands.append(list(command))
        return subprocess.CompletedProcess(command, 0, stdout="token\n", stderr="")

    def fake_http(method, url, headers, body):
        requests.append((method, url, body))
        assert headers["Authorization"] == "Bearer token"
        if method == "POST" and url.endswith(":processOpenLineageRunEvent"):
            assert body["run"]["runId"] == "run-123"
            assert body["eventTime"] != "${event_time_utc}"
            return {
                "process": "projects/test-project/locations/us/processes/process-1",
                "run": "projects/test-project/locations/us/processes/process-1/runs/run-123",
                "lineageEvents": ["projects/test-project/locations/us/processes/process-1/runs/run-123/lineageEvents/event-1"],
            }
        if method == "POST" and url.endswith(":searchLinks"):
            return {"links": [{"name": "projects/test-project/locations/us/links/link-1"}]}
        if method == "POST" and url.endswith(":batchSearchLinkProcesses"):
            assert body == {"links": ["projects/test-project/locations/us/links/link-1"]}
            return {"processLinks": [{"process": "cf-bronze-orders-scd0-overwrite"}]}
        if method == "GET" and url.endswith("/lineageEvents"):
            return {"lineageEvents": [{"name": "event-1"}]}
        if method == "POST" and "/aspectTypes?aspectTypeId=contractforge-governance" in url:
            assert body["metadataTemplate"]["name"] == "contractforge_governance"
            assert body["metadataTemplate"]["recordFields"][0]["index"] == 1
            return {"name": "projects/test-project/locations/us/aspectTypes/contractforge-governance"}
        if method == "POST" and ":searchEntries" in url:
            assert body is None
            return {
                "results": [
                    {
                        "dataplexEntry": {
                            "name": "projects/test-project/locations/us/entryGroups/@bigquery/entries/orders",
                            "fullyQualifiedName": "bigquery:test-project.bronze.orders",
                        }
                    }
                ],
                "totalSize": 1,
            }
        if method == "GET" and ":lookupEntry" in url:
            assert "entry=projects%2Ftest-project%2Flocations%2Fus%2FentryGroups%2F%40bigquery%2Fentries%2Forders" in url
            return {"name": "projects/test-project/locations/us/entryGroups/@bigquery/entries/orders", "aspects": {"test-project.us.contractforge-governance": {}}}
        if method == "POST" and url.endswith(":modifyEntry"):
            assert body["entry"]["name"] == "projects/test-project/locations/us/entryGroups/@bigquery/entries/orders"
            data = body["entry"]["aspects"]["test-project.us.contractforge-governance"]["data"]
            payload = json.loads(data["contractforge_payload_json"])
            assert data["table_aliases"] == ["sales_orders"]
            assert payload["operations"]["criticality"] == "high"
            assert json.loads(data["operations_json"])["criticality"] == "high"
            return {"entry": {"name": "entries/orders"}}
        if method == "GET" and url.endswith("/aspectTypes/contractforge-governance"):
            return {"name": "projects/test-project/locations/us/aspectTypes/contractforge-governance"}
        raise AssertionError(f"Unexpected request: {method} {url}")

    result = run_dataplex_lineage_aspects(
        contract,
        environment=_environment(),
        execute=True,
        readback=True,
        run_id="run-123",
        runner=fake_runner,
        http_runner=fake_http,
    )

    assert result["status"] == "SUCCEEDED"
    assert result["execution_included"] is True
    assert result["run_id"] == "run-123"
    assert result["lineage"]["publication"]["run"].endswith("/runs/run-123")
    assert result["lineage"]["readback"]["search_links"]["links"] == [{"name": "projects/test-project/locations/us/links/link-1"}]
    assert result["aspects"]["search_entry"]["totalSize"] == 1
    assert result["aspects"]["lookup_entry_before_modify"]["name"].endswith("/entries/orders")
    assert result["aspects"]["modify_entry"] == {"entry": {"name": "entries/orders"}}
    assert result["aspects"]["readback"]["aspect_type"]["name"].endswith("/aspectTypes/contractforge-governance")
    assert commands == [["gcloud", "auth", "print-access-token"]]
    assert [method for method, _url, _body in requests] == [
        "POST",
        "POST",
        "POST",
        "GET",
        "POST",
        "POST",
        "GET",
        "POST",
        "GET",
        "GET",
    ]


def test_gcp_dataplex_lineage_aspects_runtime_plan_is_non_mutating_by_default() -> None:
    contract = _contract()
    contract["operations"] = {"criticality": "medium"}

    result = run_dataplex_lineage_aspects(contract, environment=_environment())

    assert result["status"] == "PLANNED_NOT_EXECUTED"
    assert result["execution_included"] is False
    assert result["plans"]["lineage"]["kind"] == "contractforge.gcp.dataplex_lineage_plan.v1"
    assert result["plans"]["aspects"]["kind"] == "contractforge.gcp.dataplex_aspect_plan.v1"


def test_gcp_render_contract_emits_bigquery_annotations_artifacts() -> None:
    contract = _contract()
    contract["annotations"] = {
        "table": {
            "description": "Clean order table",
            "aliases": ["orders_curated"],
            "tags": {"domain": "sales"},
        },
        "columns": {
            "customer_email": {
                "description": "Customer's email\naddress",
                "pii": {"enabled": True, "type": "email", "sensitivity": "confidential"},
            }
        },
    }

    artifacts = render_gcp_contract(contract, environment=_environment()).artifacts
    prefix = "test-project_bronze_orders"
    sql = artifacts[f"{prefix}.gcp.annotations.sql"]
    plan = json.loads(artifacts[f"{prefix}.gcp.annotations.json"])
    evidence_sql = artifacts[f"{prefix}.gcp.annotations_evidence.sql"]

    assert "ALTER TABLE `test-project.bronze.orders`" in sql
    assert "SET OPTIONS (description = 'Clean order table');" in sql
    assert "ALTER COLUMN `customer_email`" in sql
    assert "SET OPTIONS (description = 'Customer\\'s email\\naddress');" in sql
    assert plan["apply_surface"] == "BigQuery table and column OPTIONS(description)"
    assert plan["status"] == "PLANNED"
    assert any(item["annotation_scope"] == "table" and item["annotation_type"] == "aliases" for item in plan["review_required"])
    assert any(item["annotation_scope"] == "column" and item["annotation_type"] == "pii" for item in plan["review_required"])
    assert f"{prefix}.gcp.annotations.sql" in json.loads(artifacts[f"{prefix}.gcp.manifest.json"])["artifacts"]
    assert "INSERT INTO `test-project.contractforge_ops.contractforge_annotation_evidence`" in evidence_sql
    assert "'contractforge-gcp'" in evidence_sql
    assert "'test-project.bronze.orders'" in evidence_sql
    assert "'PLANNED'" in evidence_sql


def test_gcp_annotations_noop_without_metadata() -> None:
    from contractforge_core.contracts import semantic_contract_from_mapping
    from contractforge_gcp.environment import GCPEnvironment

    contract = semantic_contract_from_mapping(_contract())

    assert has_annotations(contract) is False
    assert annotation_steps(contract) == []
    assert render_bigquery_annotations_plan(contract, GCPEnvironment()) == ""
    assert render_bigquery_annotations_sql(contract, GCPEnvironment()) == "-- No BigQuery-native annotation intent declared.\n"
    assert (
        render_bigquery_annotations_evidence_sql(contract, GCPEnvironment())
        == "-- No BigQuery-native annotation intent declared.\n"
    )


def test_gcp_render_contract_emits_policy_tag_plan_for_column_masks() -> None:
    policy_tag = "projects/test-project/locations/us-east1/taxonomies/1/policyTags/2"
    contract = _contract()
    contract["access"] = {
        "column_masks": {
            "customer_email": {
                "function": f"policy_tag:{policy_tag}",
                "applies_to": {"principals": ["analysts"]},
            }
        }
    }

    artifacts = render_gcp_contract(contract, environment=_environment()).artifacts
    payload = json.loads(artifacts["test-project_bronze_orders.gcp.policy_tags.json"])

    assert payload["apply_surface"] == "BigQuery schema update with Data Catalog policyTags"
    assert payload["apply_mode"] == "schema_update"
    assert payload["changes"] == [
        {
            "access_scope": "column",
            "access_type": "policy_tag",
            "column_name": "customer_email",
            "policy_tag": policy_tag,
            "status": "PLANNED",
        }
    ]
    assert "test-project_bronze_orders.gcp.policy_tags.json" in json.loads(
        artifacts["test-project_bronze_orders.gcp.manifest.json"]
    )["artifacts"]


def test_gcp_policy_tag_plan_noop_for_non_policy_tag_mask_function() -> None:
    from contractforge_core.contracts import semantic_contract_from_mapping
    from contractforge_gcp.environment import GCPEnvironment

    contract = semantic_contract_from_mapping(
        {
            **_contract(),
            "access": {"column_masks": {"customer_email": {"function": "mask_email"}}},
        }
    )

    assert has_policy_tag_access(contract) is False
    assert policy_tag_steps(contract) == []
    assert render_bigquery_policy_tags_plan(contract, GCPEnvironment()) == ""


def test_gcp_render_contract_emits_governance_ledger_plan_for_access_and_annotations() -> None:
    from contractforge_core.contracts import semantic_contract_from_mapping
    from contractforge_gcp.environment import GCPEnvironment

    policy_tag = "projects/test-project/locations/us-east1/taxonomies/1/policyTags/2"
    contract = _contract()
    contract["access"] = {
        "row_filters": [
            {
                "name": "paid_only",
                "function": "status = 'paid'",
                "columns": ["status"],
                "applies_to": {"principals": ["group:analysts@example.com"]},
            }
        ],
        "column_masks": {
            "customer_email": {
                "function": "mask_email",
                "applies_to": {"principals": ["group:analysts@example.com"]},
            },
            "customer_id": {
                "function": f"policy_tag:{policy_tag}",
                "applies_to": {"principals": ["group:analysts@example.com"]},
            },
        },
        "grants": [{"principal": "group:analysts@example.com", "privileges": ["SELECT"]}],
    }
    contract["annotations"] = {"table": {"description": "Orders", "tags": {"domain": "sales"}}}

    artifacts = render_gcp_contract(contract, environment=_environment()).artifacts
    payload = json.loads(artifacts["test-project_bronze_orders.gcp.governance_ledger.json"])

    assert payload["kind"] == "contractforge.gcp.bigquery_governance_ledger_plan.v1"
    assert payload["status"] == "PLANNED_WITH_REVIEW_BOUNDARIES"
    assert payload["target"] == "test-project.bronze.orders"
    assert payload["evidence"]["table"] == "contractforge_governance_evidence"
    surfaces = {item["surface"] for item in payload["actions"]}
    assert {
        "bigquery_row_access_policy",
        "bigquery_data_policy",
        "bigquery_iam",
        "bigquery_description",
        "knowledge_catalog_or_dataplex_aspect",
        "data_catalog_policy_tag",
    }.issubset(surfaces)
    assert any(item["surface"] == "bigquery_data_policy" and item["column"] == "customer_email" for item in payload["actions"])
    assert any(item["surface"] == "data_catalog_policy_tag" and item["column"] == "customer_id" for item in payload["actions"])
    assert any(
        item["surface"] == "bigquery_row_access_policy" and item["filter_expression"] == "status = 'paid'"
        for item in payload["actions"]
    )
    assert any(
        item["surface"] == "bigquery_description" and item["scope"] == "table" and item["value"] == "Orders"
        for item in payload["actions"]
    )
    assert payload["review_required"]
    reconciliation = json.loads(artifacts["test-project_bronze_orders.gcp.governance_reconciliation.json"])
    assert reconciliation["kind"] == "contractforge.gcp.bigquery_governance_reconciliation_plan.v1"
    assert reconciliation["maturity_gate"] == "GCP-BQ-17B2"
    assert reconciliation["status"] == "PLANNED_REVIEW_REQUIRED"
    assert reconciliation["execution_included"] is True
    assert reconciliation["target"] == "test-project.bronze.orders"
    assert reconciliation["actual_state_readback"]["mode"] == "non_mutating_readback"
    assert "INFORMATION_SCHEMA.ROW_ACCESS_POLICIES" in reconciliation["actual_state_readback"]["queries"]["row_access_policies"]
    assert "INFORMATION_SCHEMA.COLUMN_FIELD_PATHS" in reconciliation["actual_state_readback"]["queries"][
        "column_descriptions_and_policy_tags"
    ]
    assert reconciliation["actual_state_readback"]["api_readbacks"]["row_access_policies"]["method"] == (
        "rowAccessPolicies.list"
    )
    assert {rule["state"] for rule in reconciliation["reconciliation_rules"]} == {
        "in_sync",
        "missing_intent",
        "unmanaged_actual",
        "mismatch",
        "retained_on_overwrite",
        "requires_review",
    }
    assert "analysts@example.com" not in artifacts["test-project_bronze_orders.gcp.governance_reconciliation.json"]
    assert "REDACTED_EMAIL" in artifacts["test-project_bronze_orders.gcp.governance_reconciliation.json"]

    manifest = json.loads(artifacts["test-project_bronze_orders.gcp.manifest.json"])
    assert "test-project_bronze_orders.gcp.governance_ledger.json" in manifest["artifacts"]
    assert "test-project_bronze_orders.gcp.governance_reconciliation.json" in manifest["artifacts"]

    semantic = semantic_contract_from_mapping(contract)
    env = GCPEnvironment.from_contract(_environment())
    assert has_governance_ledger_plan(semantic) is True
    assert has_governance_reconciliation_plan(semantic) is True
    assert governance_ledger_plan(semantic, env)["evidence"]["table"] == "contractforge_governance_evidence"
    assert governance_reconciliation_plan(semantic, env)["expected_state"]["action_count"] == len(payload["actions"])
    assert json.loads(render_bigquery_governance_reconciliation_plan(semantic, env))["maturity_gate"] == "GCP-BQ-17B2"

    from contractforge_gcp.runtime import BigQueryJobEvidence

    sql = render_bigquery_governance_evidence_insert_sql(
        contract=semantic,
        environment=env,
        job=BigQueryJobEvidence(
            job_id="job-123",
            job_type="QUERY",
            state="DONE",
            finished_at_ms=1710000000000,
        ),
    )
    assert "INSERT INTO `test-project.contractforge_ops.contractforge_governance_evidence`" in sql
    assert "'job-123'" in sql
    assert "'bigquery_row_access_policy'" in sql
    assert "'bigquery_data_policy'" in sql
    assert "'data_catalog_policy_tag'" in sql
    assert "'knowledge_catalog_or_dataplex_aspect'" in sql
    assert "TIMESTAMP_MILLIS(1710000000000)" in sql
    assert "analysts@example.com" not in sql


def test_gcp_governance_reconciliation_executes_native_readback_with_injected_runner() -> None:
    import subprocess

    policy_tag = "projects/test-project/locations/us/taxonomies/1/policyTags/2"
    data_policy = "projects/test-project/locations/us/dataPolicies/mask_amount"
    contract = _contract()
    contract["access"] = {
        "row_filters": [
                {
                    "name": "paid_only",
                    "function": "status = 'paid'",
                    "columns": ["status"],
                    "applies_to": {"principals": ["serviceAccount:reader@test-project.iam.gserviceaccount.com"]},
                }
        ],
        "column_masks": {
            "amount": {"function": data_policy},
            "customer_id": {"function": f"policy_tag:{policy_tag}"},
        },
    }
    contract["annotations"] = {
        "table": {"description": "Orders"},
        "columns": {"customer_id": {"description": "Customer identifier"}},
    }
    commands: list[list[str]] = []

    def fake_runner(command: list[str], **_: object):
        commands.append(list(command))
        if command[4] == "show":
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps(
                    {
                        "schema": {
                            "fields": [
                                {"name": "amount", "type": "FLOAT", "dataPolicies": [{"name": data_policy}]},
                                {
                                    "name": "customer_id",
                                    "type": "STRING",
                                    "description": "Customer identifier",
                                    "policyTags": {"names": [policy_tag]},
                                },
                            ]
                        }
                    }
                ),
                stderr="",
            )
        if command[4] == "ls":
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps(
                    [
                        {
                            "rowAccessPolicyReference": {"policyId": "paid_only"},
                            "filterPredicate": "status = 'paid'",
                            "grantees": ["serviceAccount:reader@test-project.iam.gserviceaccount.com"],
                        }
                    ]
                ),
                stderr="",
            )
        query = command[-1]
        if "INFORMATION_SCHEMA.TABLE_OPTIONS" in query:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps([{"table_name": "orders", "option_name": "description", "option_value": "\"Orders\""}]),
                stderr="",
            )
        if "INFORMATION_SCHEMA.COLUMN_FIELD_PATHS" in query:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps(
                    [
                        {
                            "column_name": "customer_id",
                            "field_path": "customer_id",
                            "data_type": "STRING",
                            "description": "Customer identifier",
                            "policy_tags": [policy_tag],
                        }
                    ]
                ),
                stderr="",
            )
        if "contractforge_governance_evidence" in query:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps(
                    [
                        {"governance_surface": "bigquery_row_access_policy", "operation": "apply_or_validate", "subject": "paid_only", "status": "PLANNED_REVIEW_REQUIRED", "row_count": "1"},
                        {"governance_surface": "bigquery_data_policy", "operation": "apply_or_validate", "subject": "amount", "status": "PLANNED_REVIEW_REQUIRED", "row_count": "1"},
                        {"governance_surface": "data_catalog_policy_tag", "operation": "schema_update", "subject": "customer_id", "status": "PLANNED", "row_count": "1"},
                        {"governance_surface": "bigquery_description", "operation": "apply", "subject": "table", "status": "PLANNED", "row_count": "2"},
                    ]
                ),
                stderr="",
            )
        raise AssertionError(f"Unexpected command: {command}")

    result = run_bigquery_governance_reconciliation(
        contract,
        environment=_environment(),
        execute=True,
        runner=fake_runner,
    )

    assert result["status"] == "SUCCEEDED"
    assert result["execute"] is True
    assert result["summary"]["total"] == 5
    assert result["summary"]["in_sync"] == 5
    assert {item["state"] for item in result["comparisons"]} == {"in_sync"}
    assert [operation["name"] for operation in result["operations"]] == [
        "read_table_metadata",
        "read_row_access_policies",
        "read_table_descriptions",
        "read_column_descriptions_and_policy_tags",
        "read_governance_evidence",
    ]
    assert commands[0][1:5] == ["--project_id=test-project", "--location=US", "--format=json", "show"]


def test_gcp_governance_ledger_noop_without_governance_intent() -> None:
    from contractforge_core.contracts import semantic_contract_from_mapping
    from contractforge_gcp.environment import GCPEnvironment

    contract = semantic_contract_from_mapping(_contract())

    assert has_governance_ledger_plan(contract) is False
    assert render_bigquery_governance_ledger_plan(contract, GCPEnvironment()) == ""
    assert has_governance_reconciliation_plan(contract) is False
    assert render_bigquery_governance_reconciliation_plan(contract, GCPEnvironment()) == ""


def test_gcp_render_contract_emits_gcs_load_job_config() -> None:
    contract = {
        "source": {"type": "gcs", "format": "csv", "path": "gs://bucket/orders.csv"},
        "target": {"catalog": "test-project", "schema": "bronze", "table": "orders"},
        "mode": "append",
    }

    artifacts = render_gcp_contract(contract, environment=_environment()).artifacts
    load_job = json.loads(artifacts["test-project_bronze_orders.gcp.load_job.json"])

    assert load_job["source_uris"] == ["gs://bucket/orders.csv"]
    assert load_job["destination_table"] == "test-project.bronze.orders"
    assert load_job["source_format"] == "CSV"
    assert load_job["write_disposition"] == "WRITE_APPEND"
    assert load_job["autodetect"] is True

    deployment = json.loads(artifacts["test-project_bronze_orders.gcp.deployment_manifest.json"])
    apply_order = [step["name"] for step in deployment["apply_order"]]
    assert "load_source" in apply_order
    assert "write_target" not in apply_order


def test_gcp_render_contract_emits_declared_gcs_load_schema() -> None:
    contract = {
        "source": {
            "type": "gcs",
            "format": "csv",
            "path": "gs://bucket/orders.csv",
            "read": {"columns": [{"name": "order_id", "type": "STRING"}, {"name": "amount", "type": "FLOAT"}]},
        },
        "target": {"catalog": "test-project", "schema": "bronze", "table": "orders"},
        "mode": "append",
    }

    artifacts = render_gcp_contract(contract, environment=_environment()).artifacts
    load_job = json.loads(artifacts["test-project_bronze_orders.gcp.load_job.json"])

    assert "autodetect" not in load_job
    assert load_job["schema_fields"] == [{"name": "order_id", "type": "STRING"}, {"name": "amount", "type": "FLOAT64"}]


def test_gcp_render_contract_emits_ndjson_autodetect_load_job_config() -> None:
    contract = {
        "source": {"type": "gcs", "format": "ndjson", "path": "gs://bucket/orders.ndjson"},
        "target": {"catalog": "test-project", "schema": "bronze", "table": "orders"},
        "mode": "overwrite",
    }

    artifacts = render_gcp_contract(contract, environment=_environment()).artifacts
    load_job = json.loads(artifacts["test-project_bronze_orders.gcp.load_job.json"])

    assert load_job["source_format"] == "NEWLINE_DELIMITED_JSON"
    assert load_job["write_disposition"] == "WRITE_TRUNCATE"
    assert load_job["autodetect"] is True


def test_gcp_render_contract_materializes_http_text_as_line_oriented_ndjson() -> None:
    contract = {
        "source": {
            "type": "http_text",
            "request": {"url": "https://example.com/orders.txt"},
            "read": {"columns": [{"name": "line_text", "type": "STRING"}]},
        },
        "target": {"catalog": "test-project", "schema": "bronze", "table": "text_orders"},
        "mode": "overwrite",
    }

    artifacts = render_gcp_contract(contract, environment=_environment()).artifacts
    plan = json.loads(artifacts["test-project_bronze_text_orders.gcp.source_materialization.json"])
    source_review = json.loads(artifacts["test-project_bronze_text_orders.gcp.source_review.json"])

    assert plan["source_type"] == "http_text"
    assert plan["reader"] == "contractforge_core.connectors.read_http_file_payload"
    assert plan["source_format"] == "NEWLINE_DELIMITED_JSON"
    assert plan["schema_fields"] == [{"name": "line_text", "type": "STRING"}]
    assert "autodetect" not in plan
    assert source_review["status"] == "SUPPORTED_WITH_WARNINGS"
    assert source_review["promotion_path"] == {}


def test_gcp_render_contract_materializes_generic_http_file_formats() -> None:
    json_contract = {
        "source": {
            "type": "http_file",
            "format": "json",
            "request": {"url": "https://example.com/orders.json"},
            "read": {"columns": [{"name": "order_id", "type": "STRING"}]},
        },
        "target": {"catalog": "test-project", "schema": "bronze", "table": "http_file_json_orders"},
        "mode": "overwrite",
    }
    text_contract = {
        "source": {
            "type": "http_file",
            "format": "text",
            "request": {"url": "https://example.com/orders.txt"},
            "response": {"raw_column": "line_text"},
        },
        "target": {"catalog": "test-project", "schema": "bronze", "table": "http_file_text_orders"},
        "mode": "overwrite",
    }
    parquet_contract = {
        "source": {
            "type": "http_file",
            "format": "parquet",
            "request": {"url": "https://example.com/orders.parquet"},
        },
        "target": {"catalog": "test-project", "schema": "bronze", "table": "http_file_parquet_orders"},
        "mode": "overwrite",
    }
    missing_format_contract = {
        "source": {"type": "http_file", "request": {"url": "https://example.com/orders"}},
        "target": {"catalog": "test-project", "schema": "bronze", "table": "http_file_missing_format"},
        "mode": "overwrite",
    }

    json_artifacts = render_gcp_contract(json_contract, environment=_environment()).artifacts
    text_artifacts = render_gcp_contract(text_contract, environment=_environment()).artifacts
    parquet_artifacts = render_gcp_contract(parquet_contract, environment=_environment()).artifacts
    missing_artifacts = render_gcp_contract(missing_format_contract, environment=_environment()).artifacts
    json_plan = json.loads(json_artifacts["test-project_bronze_http_file_json_orders.gcp.source_materialization.json"])
    text_plan = json.loads(text_artifacts["test-project_bronze_http_file_text_orders.gcp.source_materialization.json"])
    parquet_plan = json.loads(
        parquet_artifacts["test-project_bronze_http_file_parquet_orders.gcp.source_materialization.json"]
    )
    json_review = json.loads(json_artifacts["test-project_bronze_http_file_json_orders.gcp.source_review.json"])
    parquet_review = json.loads(parquet_artifacts["test-project_bronze_http_file_parquet_orders.gcp.source_review.json"])
    missing_review = json.loads(missing_artifacts["test-project_bronze_http_file_missing_format.gcp.source_review.json"])

    assert json_plan["source_type"] == "http_file"
    assert json_plan["source_format"] == "NEWLINE_DELIMITED_JSON"
    assert json_plan["schema_fields"] == [{"name": "order_id", "type": "STRING"}]
    assert json_review["runtime_path"] == "Shared core bounded reader, temporary local materialization and BigQuery load job"
    assert json_review["promotion_path"] == {}
    assert text_plan["source_type"] == "http_file"
    assert text_plan["source_format"] == "NEWLINE_DELIMITED_JSON"
    assert text_plan["schema_fields"] == [{"name": "line_text", "type": "STRING"}]
    assert parquet_plan["source_type"] == "http_file"
    assert parquet_plan["local_format"] == "parquet"
    assert parquet_plan["source_format"] == "PARQUET"
    assert parquet_plan["reader"] == "contractforge_core.connectors.read_http_file_payload"
    assert parquet_review["runtime_path"] == "Shared core bounded reader, temporary local materialization and BigQuery load job"
    assert parquet_review["promotion_path"] == {}
    assert not any(name.endswith(".gcp.source_materialization.json") for name in missing_artifacts)
    assert missing_review["status"] == "REVIEW_REQUIRED"
    assert missing_review["promotion_path"]


def test_gcp_render_contract_reads_registered_biglake_iceberg_table_source() -> None:
    contract = {
        "source": {
            "type": "iceberg_table",
            "table": "gcp-project-redacted.contractforge_gcp_smoke.biglake_iceberg_orders",
        },
        "target": {"catalog": "test-project", "schema": "bronze", "table": "orders_from_iceberg"},
        "mode": "overwrite",
    }

    artifacts = render_gcp_contract(contract, environment=_environment()).artifacts
    sql = artifacts["test-project_bronze_orders_from_iceberg.gcp.write.sql"]
    source_review = json.loads(artifacts["test-project_bronze_orders_from_iceberg.gcp.source_review.json"])

    assert source_review["status"] == "SUPPORTED"
    assert "CREATE OR REPLACE TABLE `test-project.bronze.orders_from_iceberg` AS" in sql
    assert "SELECT * FROM `gcp-project-redacted.contractforge_gcp_smoke.biglake_iceberg_orders`" in sql


def test_gcp_render_contract_emits_upsert_merge_sql() -> None:
    contract = _contract(mode="upsert")
    contract["merge_keys"] = ["order_id"]
    contract["select_columns"] = ["order_id", "amount", "status"]

    artifacts = render_gcp_contract(contract, environment=_environment()).artifacts
    sql = artifacts["test-project_bronze_orders.gcp.write.sql"]

    assert "MERGE `test-project.bronze.orders` AS T" in sql
    assert "USING (SELECT * FROM `raw.orders`) AS S" in sql
    assert "ON T.`order_id` = S.`order_id`" in sql
    assert "UPDATE SET `amount` = S.`amount`, `status` = S.`status`" in sql
    assert "INSERT (`order_id`, `amount`, `status`) VALUES (S.`order_id`, S.`amount`, S.`status`)" in sql


def test_gcp_render_contract_requires_columns_for_executable_upsert_merge_sql() -> None:
    contract = _contract(mode="upsert")
    contract["merge_keys"] = ["order_id"]

    artifacts = render_gcp_contract(contract, environment=_environment()).artifacts
    sql = artifacts["test-project_bronze_orders.gcp.write.sql"]

    assert "upsert requires explicit source columns" in sql
    assert "__contractforge_update_required" not in sql


def test_gcp_render_contract_accepts_object_columns_for_upsert_merge_sql() -> None:
    contract = _contract(mode="upsert")
    contract["merge_keys"] = ["order_id"]
    contract["source"] = {
        "type": "table",
        "table": "raw.orders",
        "read": {
            "columns": [
                {"name": "order_id", "type": "STRING"},
                {"name": "amount", "type": "FLOAT64"},
                {"name": "status", "type": "STRING"},
            ]
        },
    }

    artifacts = render_gcp_contract(contract, environment=_environment()).artifacts
    sql = artifacts["test-project_bronze_orders.gcp.write.sql"]

    assert "UPDATE SET `amount` = S.`amount`, `status` = S.`status`" in sql
    assert "INSERT (`order_id`, `amount`, `status`) VALUES (S.`order_id`, S.`amount`, S.`status`)" in sql


def test_gcp_hash_diff_is_review_required_not_claimed_stable() -> None:
    contract = _contract(mode="hash_diff_upsert")
    contract["merge_keys"] = ["order_id"]
    contract["hash_keys"] = ["amount"]
    contract["source"] = {
        "type": "table",
        "table": "raw.orders",
        "read": {"columns": ["order_id", "amount", "status", "updated_at"]},
    }

    result = plan_gcp_contract(contract, environment=_environment())
    artifacts = render_gcp_contract(contract, environment=_environment()).artifacts
    deployment = json.loads(artifacts["test-project_bronze_orders.gcp.deployment_manifest.json"])
    review = json.loads(artifacts["test-project_bronze_orders.gcp.advanced_write_mode_review.json"])

    assert result.status == "REVIEW_REQUIRED"
    assert any("scd1_hash_diff" in warning.message for warning in result.warnings)
    assert review["kind"] == "contractforge.gcp.bigquery_advanced_write_mode_review.v1"
    assert review["status"] == "PLANNED_REVIEW_REQUIRED"
    assert review["execution"]["included"] is False
    assert review["mode"] == {"alias": "hash_diff_upsert", "canonical": "scd1_hash_diff"}
    assert review["hash_diff"]["hash_input_columns"] == ["amount"]
    assert "TO_HEX(SHA256" in review["draft_sql"]["stage"]
    assert "WHEN MATCHED AND COALESCE(T.row_hash, '') != COALESCE(S.row_hash, '') THEN" in review["draft_sql"]["merge"]
    assert deployment["status"] == "review_required"
    assert deployment["execution_ready"] is False
    assert deployment["apply_order"] == []


def test_gcp_advanced_write_sql_renders_executable_hash_diff_without_temp_table() -> None:
    from contractforge_core.contracts import semantic_contract_from_mapping
    from contractforge_gcp.environment import GCPEnvironment

    contract = _contract(mode="hash_diff_upsert")
    contract["merge_keys"] = ["order_id"]
    contract["hash_keys"] = ["amount"]
    contract["source"] = {
        "type": "table",
        "table": "raw.orders",
        "read": {"columns": ["order_id", "amount", "status"]},
    }

    artifacts = render_gcp_contract(contract, environment=_environment()).artifacts
    sql = artifacts["test-project_bronze_orders.gcp.write.sql"]

    assert sql == render_bigquery_advanced_write_sql(
        semantic_contract_from_mapping(contract),
        GCPEnvironment.from_contract(_environment()),
    )
    assert "CREATE TEMP TABLE" not in sql
    assert "CONTRACTFORGE_NULL_MERGE_KEY" in sql
    assert "CONTRACTFORGE_DUPLICATE_MERGE_KEYS" in sql
    assert "MERGE `test-project.bronze.orders` AS T" in sql
    assert "USING (\n  SELECT\n    S.*," in sql
    assert "TO_HEX(SHA256" in sql
    assert "CODE_POINTS_TO_STRING([0])" in sql
    assert "CODE_POINTS_TO_STRING([31])" in sql
    assert "\x00" not in sql
    assert "\x1f" not in sql
    assert "WHEN MATCHED AND COALESCE(T.row_hash, '') != COALESCE(S.row_hash, '') THEN" in sql


def test_gcp_advanced_write_review_renders_historical_and_snapshot_artifacts() -> None:
    historical = _contract(mode="historical")
    historical["merge_keys"] = ["order_id"]
    historical["scd2_change_columns"] = ["amount", "status"]
    historical["scd2_effective_from_column"] = "updated_at"
    historical["source"] = {
        "type": "table",
        "table": "raw.orders",
        "read": {"columns": ["order_id", "amount", "status", "updated_at"]},
    }
    snapshot = _contract(mode="snapshot_reconcile_soft_delete")
    snapshot["merge_keys"] = ["order_id"]
    snapshot["source"] = {
        "type": "table",
        "table": "raw.orders",
        "read": {"columns": ["order_id", "amount", "status"], "source_complete": True},
    }

    historical_artifacts = render_gcp_contract(historical, environment=_environment()).artifacts
    snapshot_artifacts = render_gcp_contract(snapshot, environment=_environment()).artifacts
    historical_review = json.loads(historical_artifacts["test-project_bronze_orders.gcp.advanced_write_mode_review.json"])
    snapshot_review = json.loads(snapshot_artifacts["test-project_bronze_orders.gcp.advanced_write_mode_review.json"])

    assert historical_review["mode"] == {"alias": "historical", "canonical": "scd2_historical"}
    assert historical_review["historical"]["change_columns"] == ["amount", "status"]
    assert historical_review["historical"]["effective_from_column"] == "updated_at"
    assert "UPDATE `test-project.bronze.orders` AS T" in historical_review["draft_sql"]["expire_current"]
    assert "INSERT INTO `test-project.bronze.orders`" in historical_review["draft_sql"]["insert_current"]

    assert snapshot_review["mode"] == {"alias": "snapshot_reconcile_soft_delete", "canonical": "snapshot_soft_delete"}
    assert snapshot_review["snapshot"]["source_columns"] == ["order_id", "amount", "status", "is_active", "deleted_at", "row_hash"]
    assert "WHEN MATCHED AND (T.is_active = FALSE OR COALESCE(T.row_hash, '') != COALESCE(S.row_hash, '')) THEN" in snapshot_review["draft_sql"]["merge"]
    assert "WHEN NOT MATCHED BY SOURCE AND T.is_active = TRUE THEN" in snapshot_review["draft_sql"]["merge"]
    assert snapshot_review["execution"]["included"] is False


def test_gcp_snapshot_review_blocks_incomplete_snapshot_sql() -> None:
    from contractforge_core.contracts import semantic_contract_from_mapping
    from contractforge_gcp.environment import GCPEnvironment

    snapshot = _contract(mode="snapshot_reconcile_soft_delete")
    snapshot["merge_keys"] = ["order_id"]
    snapshot["source"] = {
        "type": "table",
        "table": "raw.orders",
        "read": {"columns": ["order_id", "amount", "status"]},
    }

    review = json.loads(
        render_bigquery_advanced_write_mode_review(
            semantic_contract_from_mapping(snapshot),
            GCPEnvironment.from_contract(_environment()),
        )
    )
    sql = render_bigquery_advanced_write_sql(semantic_contract_from_mapping(snapshot), GCPEnvironment.from_contract(_environment()))

    assert {
        "code": "MISSING_SOURCE_COMPLETE",
        "message": "snapshot_reconcile_soft_delete requires source.read.source_complete=true or source.read.full_snapshot=true.",
    } in review["blockers"]
    assert review["draft_sql"] == {}
    assert "MISSING_SOURCE_COMPLETE" in sql


def test_gcp_snapshot_executable_sql_reactivates_inactive_same_hash_rows() -> None:
    from contractforge_core.contracts import semantic_contract_from_mapping
    from contractforge_gcp.environment import GCPEnvironment

    snapshot = _contract(mode="snapshot_reconcile_soft_delete")
    snapshot["merge_keys"] = ["order_id"]
    snapshot["source"] = {
        "type": "table",
        "table": "raw.orders",
        "read": {"columns": ["order_id", "amount", "status"], "source_complete": True},
    }

    sql = render_bigquery_advanced_write_sql(semantic_contract_from_mapping(snapshot), GCPEnvironment.from_contract(_environment()))

    assert "WHEN MATCHED AND (T.is_active = FALSE OR COALESCE(T.row_hash, '') != COALESCE(S.row_hash, '')) THEN" in sql
    assert "is_active = TRUE" in sql
    assert "deleted_at = NULL" in sql
    assert "WHEN NOT MATCHED BY SOURCE AND T.is_active = TRUE THEN" in sql


def test_gcp_historical_review_renders_delete_and_late_arriving_policy_sql() -> None:
    historical = _contract(mode="historical")
    historical["merge_keys"] = ["order_id"]
    historical["scd2_change_columns"] = ["amount", "status"]
    historical["scd2_effective_from_column"] = "updated_at"
    historical["scd2_sequence_by"] = "updated_at"
    historical["scd2_late_arriving_policy"] = "reject"
    historical["scd2_apply_as_deletes"] = "status = 'DELETE'"
    historical["source"] = {
        "type": "table",
        "table": "raw.orders",
        "read": {"columns": ["order_id", "amount", "status", "updated_at"]},
    }

    artifacts = render_gcp_contract(historical, environment=_environment()).artifacts
    review = json.loads(artifacts["test-project_bronze_orders.gcp.advanced_write_mode_review.json"])
    sql = artifacts["test-project_bronze_orders.gcp.write.sql"]

    assert review["historical"]["apply_as_deletes"] == "status = 'DELETE'"
    assert "COALESCE(CAST((status = 'DELETE') AS BOOL), FALSE) AS apply_as_delete" in review["draft_sql"]["stage"]
    assert "CONTRACTFORGE_LATE_ARRIVING_HISTORICAL" in review["draft_sql"]["late_arriving_guard"]
    assert "S.apply_as_delete OR COALESCE(T.row_hash, '') != COALESCE(S.row_hash, '')" in review["draft_sql"]["expire_current"]
    assert "WHERE NOT S.apply_as_delete" in review["draft_sql"]["insert_current"]
    assert "AND NOT (T.`updated_at` IS NOT NULL AND (S.__cf_sequence_by IS NULL OR S.__cf_sequence_by <= T.`updated_at`))" in review["draft_sql"]["insert_current"]

    assert "CONTRACTFORGE_LATE_ARRIVING_HISTORICAL" in sql
    assert "changed_columns = IF(S.apply_as_delete, ['DELETE'], T.changed_columns)" in sql
    assert "WHERE NOT S.apply_as_delete" in sql
    assert "AND NOT (T.`updated_at` IS NOT NULL AND (S.__cf_sequence_by IS NULL OR S.__cf_sequence_by <= T.`updated_at`))" in sql


def test_gcp_historical_late_arriving_ignore_filters_without_reject_guard() -> None:
    historical = _contract(mode="historical")
    historical["merge_keys"] = ["order_id"]
    historical["scd2_change_columns"] = ["amount"]
    historical["scd2_effective_from_column"] = "updated_at"
    historical["scd2_sequence_by"] = "updated_at"
    historical["scd2_late_arriving_policy"] = "ignore"
    historical["source"] = {
        "type": "table",
        "table": "raw.orders",
        "read": {"columns": ["order_id", "amount", "updated_at"]},
    }

    artifacts = render_gcp_contract(historical, environment=_environment()).artifacts
    review = json.loads(artifacts["test-project_bronze_orders.gcp.advanced_write_mode_review.json"])
    sql = artifacts["test-project_bronze_orders.gcp.write.sql"]

    assert "late_arriving_guard" not in review["draft_sql"]
    assert "CONTRACTFORGE_LATE_ARRIVING_HISTORICAL" not in sql
    assert "AND NOT (T.`updated_at` IS NOT NULL AND (S.__cf_sequence_by IS NULL OR S.__cf_sequence_by <= T.`updated_at`))" in sql


def test_gcp_historical_late_arriving_policy_requires_sequence_or_effective_from() -> None:
    from contractforge_core.contracts import semantic_contract_from_mapping
    from contractforge_gcp.environment import GCPEnvironment

    historical = _contract(mode="historical")
    historical["merge_keys"] = ["order_id"]
    historical["scd2_change_columns"] = ["amount"]
    historical["scd2_late_arriving_policy"] = "reject"
    historical["source"] = {
        "type": "table",
        "table": "raw.orders",
        "read": {"columns": ["order_id", "amount"]},
    }

    review = json.loads(
        render_bigquery_advanced_write_mode_review(
            semantic_contract_from_mapping(historical),
            GCPEnvironment.from_contract(_environment()),
        )
    )

    assert {
        "code": "MISSING_SCD2_SEQUENCE",
        "message": "historical late-arriving policy ignore/reject requires scd2_sequence_by.",
    } in review["blockers"]
    assert review["draft_sql"] == {}


def test_gcp_advanced_write_review_records_blockers_without_columns() -> None:
    from contractforge_core.contracts import semantic_contract_from_mapping
    from contractforge_gcp.environment import GCPEnvironment

    semantic = semantic_contract_from_mapping({**_contract(mode="hash_diff_upsert"), "merge_keys": ["order_id"]})
    review = json.loads(render_bigquery_advanced_write_mode_review(semantic, GCPEnvironment.from_contract(_environment())))

    assert review["blockers"] == [
        {
            "code": "MISSING_SOURCE_COLUMNS",
            "message": "Declare top-level select_columns or source.read.columns so review SQL has deterministic columns.",
        },
        {
            "code": "MISSING_HASH_KEYS",
            "message": "hash_diff_upsert requires hash_keys unless hash_strategy is all_columns_except.",
        },
    ]
    assert review["draft_sql"] == {}


def test_gcp_stabilization_report_is_stable_final_for_supported_surface() -> None:
    report = gcp_stabilization_report()

    assert report["adapter"] == "contractforge-gcp"
    assert report["subtarget"] == GCP_SUBTARGET_BIGQUERY
    assert report["classification"] == "STABLE_SUPPORTED_SURFACE"
    assert report["supported_surface_ready"] is True
    assert report["stable_final"] is True
    assert report["evidence_manifest"] == "docs/reports/gcp-stable-surface-evidence.json"
    assert any(gate["id"] == "GCP-BQ-20A" and gate["status"] == "PASS" for gate in report["gates"])
    assert any(gate["id"] == "GCP-BQ-20B" and gate["status"] == "PASS" for gate in report["gates"])
    assert any(gate["id"] == "GCP-BQ-20D" and gate["status"] == "PASS" for gate in report["gates"])
    assert any(gate["id"] == "GCP-BQ-20C" and gate["status"] == "PASS" for gate in report["gates"])
    assert any(gate["id"] == "GCP-BQ-20E" and gate["status"] == "PASS_WITH_REVIEW_BOUNDARY" for gate in report["gates"])
    assert any(gate["id"] == "GCP-BQ-16A1" and gate["status"] == "PASS" for gate in report["gates"])
    assert any(gate["id"] == "GCP-BQ-16A2" and gate["status"] == "PASS_WITH_REVIEW_BOUNDARY" for gate in report["gates"])
    assert any(gate["id"] == "GCP-BQ-16B0" and gate["status"] == "PASS" for gate in report["gates"])
    assert any(gate["id"] == "GCP-BQ-16B1" and gate["status"] == "PASS" for gate in report["gates"])
    assert any(gate["id"] == "GCP-BQ-16B3" and gate["status"] == "PASS" for gate in report["gates"])
    assert any(gate["id"] == "GCP-BQ-16" and gate["status"] == "PASS" for gate in report["gates"])
    assert any(gate["id"] == "GCP-BQ-17B1" and gate["status"] == "PASS_WITH_REVIEW_BOUNDARY" for gate in report["gates"])
    assert any(gate["id"] == "GCP-BQ-17B2" and gate["status"] == "PASS" for gate in report["gates"])
    assert any(gate["id"] == "GCP-BQ-17B" and gate["status"] == "PASS_WITH_REVIEW_BOUNDARY" for gate in report["gates"])
    assert any(gate["id"] == "GCP-BQ-12B" and gate["status"] == "PASS" for gate in report["gates"])
    assert any(gate["id"] == "GCP-BQ-12A" and gate["status"] == "PASS_WITH_REVIEW_BOUNDARY" for gate in report["gates"])
    assert any(gate["id"] == "GCP-BQ-12C1" and gate["status"] == "PASS_WITH_REVIEW_BOUNDARY" for gate in report["gates"])
    assert any(gate["id"] == "GCP-BQ-12C2" and gate["status"] == "PASS_WITH_REVIEW_BOUNDARY" for gate in report["gates"])
    assert any(gate["id"] == "GCP-BQ-12C3" and gate["status"] == "PASS_WITH_REVIEW_BOUNDARY" for gate in report["gates"])
    assert any(gate["id"] == "GCP-BQ-12C4" and gate["status"] == "PASS" for gate in report["gates"])
    assert any(gate["id"] == "GCP-BQ-12C" and gate["status"] == "PASS" for gate in report["gates"])
    assert any(gate["id"] == "GCP-BQ-12C5" and gate["status"] == "PASS_WITH_REVIEW_BOUNDARY" for gate in report["gates"])
    assert any(gate["id"] == "GCP-BQ-13A0" and gate["status"] == "PASS" for gate in report["gates"])
    assert any(gate["id"] == "GCP-BQ-13A" and gate["status"] == "PASS_WITH_REVIEW_BOUNDARY" for gate in report["gates"])
    assert {gate["id"] for gate in report["next_promotion_gates"]} == {
        "GCP-BQ-12D",
        "GCP-BQ-20",
    }
    assert all(gate["status"] == "FUTURE" for gate in report["next_promotion_gates"])
    assert any(boundary["code"] == "GCP_STREAMING_REVIEW" for boundary in report["accepted_review_boundaries"])
    assert any(
        boundary["code"] == "GCP_ADVANCED_WRITE_MODES_REVIEW"
        and boundary["decision"] == "HASH_DIFF_PRODUCTION_PARITY_ACCEPTED_HISTORICAL_SNAPSHOT_EXCLUDED"
        for boundary in report["accepted_review_boundaries"]
    )
    assert any(
        boundary["code"] == "GCP_AUTHENTICATED_REST_HTTP_REVIEW"
        and boundary["decision"] == "PLACEHOLDER_SECRET_MANAGER_EXECUTION_INCLUDED_INLINE_CREDENTIALS_EXCLUDED"
        for boundary in report["accepted_review_boundaries"]
    )
    assert any(
        boundary["code"] == "GCP_SOURCE_FAMILY_PROMOTION_REVIEW"
        and boundary["decision"] == "RAW_ICEBERG_REGISTRATION_INCLUDED_OTHER_EXECUTION_EXCLUDED"
        for boundary in report["accepted_review_boundaries"]
    )
    assert any(
        project["name"] == "gcp_dataplex_lineage_aspect_runtime_decision" and project["status"] == "DECIDED"
        for project in report["real_validation_projects"]
    )
    assert report["validated"]["render_bigquery_sql"] is True
    assert report["validated"]["schema_policy_artifact_planning"] is True
    assert report["validated"]["schema_policy_runtime_hook"] is True
    assert report["validated"]["schema_policy_additive_smoke"] is True
    assert report["validated"]["schema_policy_strict_negative_smoke"] is True
    assert report["validated"]["schema_policy_permissive_smoke"] is True
    assert report["validated"]["schema_policy_type_change_negative_smoke"] is True
    assert report["validated"]["schema_policy_sql_source_smoke"] is True
    assert report["validated"]["schema_policy_gcs_source_smoke"] is True
    assert report["validated"]["schema_policy_type_mutation_decision"] is True
    assert report["validated"]["single_contract_csv_smoke"] is True
    assert report["validated"]["advanced_write_mode_review_artifact_planning"] is True
    assert report["validated"]["advanced_write_mode_opt_in_smoke"] is True
    assert report["validated"]["advanced_write_hashdiff_preflight_smoke"] is True
    assert report["validated"]["advanced_write_hashdiff_production_benchmark"] is True
    assert report["validated"]["advanced_write_hashdiff_cross_adapter_production_parity"] is True
    assert report["validated"]["advanced_write_historical_snapshot_production_benchmark"] is True
    assert report["validated"]["neutral_openlineage_evidence"] is True
    assert report["validated"]["dataplex_data_quality_artifact_planning"] is True
    assert report["validated"]["dataplex_data_quality_execution_artifact_planning"] is True
    assert report["validated"]["dataplex_data_quality_execution_smoke"] is True
    assert report["validated"]["dataplex_lineage_aspect_artifact_planning"] is True
    assert report["validated"]["dataplex_lineage_aspect_command_surface"] is True
    assert report["validated"]["dataplex_lineage_aspect_runtime_decision"] is True
    assert report["validated"]["automatic_native_dataplex_lineage_aspect_emission"] is False
    assert report["validated"]["governance_ledger_artifact_planning"] is True
    assert report["validated"]["governance_ledger_evidence_write_readback"] is True
    assert report["validated"]["governance_ledger_reconciliation_artifact_planning"] is True
    assert report["validated"]["governance_ledger_reconciliation_command_surface"] is True
    assert report["validated"]["sequential_project_smoke"] is True
    assert report["validated"]["workflows_project_runner_artifact_planning"] is True
    assert report["validated"]["workflows_bigquery_job_polling_planning"] is True
    assert report["validated"]["workflows_evidence_readback_planning"] is True
    assert report["validated"]["workflows_runner_evidence_persistence"] is True
    assert report["validated"]["workflows_quality_failed_row_semantics"] is True
    assert report["validated"]["workflows_execution_scoped_evidence_ids"] is True
    assert report["validated"]["workflows_certified_runner_smoke"] is True
    assert report["validated"]["workflows_write_failure_run_evidence"] is True
    assert report["validated"]["workflows_target_evidence_cleanup"] is True
    assert report["validated"]["workflows_runner_deploy_execute_smoke"] is True
    assert report["validated"]["live_bronze_to_gold_e2e"] is True
    assert report["validated"]["row_access_policy_smoke"] is True
    assert report["validated"]["failed_run_evidence_smoke"] is True
    assert report["validated"]["data_masking_policy_smoke"] is True
    assert report["validated"]["annotations_description_smoke"] is True
    assert report["validated"]["policy_tag_access_smoke"] is True
    assert report["validated"]["biglake_iceberg_smoke"] is True
    assert report["validated"]["public_rest_http_source_materialization"] is True
    assert report["validated"]["authenticated_rest_http_secret_manager_review_artifact_planning"] is True
    assert report["validated"]["authenticated_rest_http_secret_manager_execution_smoke"] is True
    assert report["validated"]["authenticated_rest_http_secret_manager_variants_smoke"] is True
    assert report["validated"]["http_file_binary_bigquery_smoke"] is True
    assert report["validated"]["raw_iceberg_registration_command_smoke"] is True
    assert report["validated"]["non_jdbc_source_family_promotion_artifact_planning"] is True
    assert report["validated"]["streaming_scope_decision"] is True
    assert report["validated"]["dataflow_streaming_source_promotion_command_surface"] is True
    assert report["validated"]["streaming_provider_parity"] is True
    assert report["validated"]["write_mode_scope_decision"] is True
    assert report["validated"]["deployment_orchestration_scope_decision"] is True
    assert report["validated"]["dataplex_lineage_dq_scope_decision"] is True
    assert report["validated"]["governance_stable_scope_decision"] is True
    assert report["validated"]["governance_e2e"] is True
    assert report["validated"]["schema_policy_e2e"] is True
    assert report["validated"]["streaming_e2e"] is True
    dataplex_boundary = next(
        boundary for boundary in report["accepted_review_boundaries"] if boundary["code"] == "GCP_DATAPLEX_LINEAGE_DQ_REVIEW"
    )
    assert dataplex_boundary["decision"] == "EXPLICIT_COMMAND_SURFACE_INCLUDED_AUTOMATIC_EMISSION_EXCLUDED"
    assert "explicit command execution only" in dataplex_boundary["reason"]
    streaming_boundary = next(
        boundary for boundary in report["accepted_review_boundaries"] if boundary["code"] == "GCP_STREAMING_REVIEW"
    )
    assert "row ingestion, zero-DLQ reconciliation and no-input replay" in streaming_boundary["reason"]
    schema_policy_boundary = next(
        boundary for boundary in report["accepted_review_boundaries"] if boundary["code"] == "GCP_SCHEMA_POLICY_REVIEW"
    )
    assert "BigQuery table/view/SQL-source and declared-schema GCS load-source inspection" in schema_policy_boundary[
        "reason"
    ]
    assert "table-source, SQL-source" not in schema_policy_boundary["reason"]


def test_gcp_public_deployment_manifest_renderer_returns_manifest() -> None:
    from contractforge_core.contracts import semantic_contract_from_mapping
    from contractforge_gcp.environment import GCPEnvironment

    contract = semantic_contract_from_mapping(_contract())
    manifest = json.loads(
        render_gcp_deployment_manifest(
            contract=contract,
            environment=GCPEnvironment.from_contract(_environment()),
            planning=plan_gcp_contract(_contract(), environment=_environment()),
            artifacts={"test-project_bronze_orders.gcp.write.sql": "SELECT 1;\n"},
        )
    )

    assert manifest["adapter"] == "contractforge-gcp"
    assert manifest["status"] == "supported"
    assert manifest["execution_ready"] is True
    assert manifest["apply_order"][0]["name"] == "write_target"
    assert manifest["review_boundaries"][0] == "This manifest is deterministic and does not call Google Cloud APIs."
    assert any("--enforce-schema-policy is the validated live runtime path" in item for item in manifest["review_boundaries"])


def test_gcp_deployment_manifest_uses_source_classifier_review_boundaries() -> None:
    from contractforge_core.contracts import semantic_contract_from_mapping
    from contractforge_gcp.environment import GCPEnvironment

    contract_mapping = {
        **_contract(),
        "source": {"type": "delta_share", "profile_file": "profile.json", "table": "share.schema.orders"},
    }
    contract = semantic_contract_from_mapping(contract_mapping)
    source_classification = classify_gcp_source(contract.source.raw)
    manifest = json.loads(
        render_gcp_deployment_manifest(
            contract=contract,
            environment=GCPEnvironment.from_contract(_environment()),
            planning=plan_gcp_contract(contract_mapping, environment=_environment()),
            artifacts={"test-project_bronze_orders.gcp.write.sql": "SELECT 1;\n"},
        )
    )

    assert manifest["status"] == "review_required"
    assert manifest["execution_ready"] is False
    assert manifest["apply_order"] == []
    assert any(source_classification.note in item for item in manifest["review_boundaries"])


def test_gcp_deployment_manifest_blocks_apply_order_for_unsupported_source() -> None:
    from contractforge_core.contracts import semantic_contract_from_mapping
    from contractforge_gcp.environment import GCPEnvironment

    contract_mapping = {**_contract(), "source": {"type": "xml", "path": "gs://bucket/orders.xml"}}
    contract = semantic_contract_from_mapping(contract_mapping)
    manifest = json.loads(
        render_gcp_deployment_manifest(
            contract=contract,
            environment=GCPEnvironment.from_contract(_environment()),
            planning=plan_gcp_contract(contract_mapping, environment=_environment()),
            artifacts={"test-project_bronze_orders.gcp.write.sql": "SELECT 1;\n"},
        )
    )

    assert manifest["status"] == "blocked"
    assert manifest["execution_ready"] is False
    assert manifest["apply_order"] == []
    assert any("not executable by the GCP adapter" in item for item in manifest["review_boundaries"])


def test_gcp_cli_sources_and_stabilization(capsys) -> None:
    assert gcp_cli(["sources"]) == 0
    sources_output = capsys.readouterr().out
    assert '"source_type": "gcs"' in sources_output

    assert gcp_cli(["stabilization-report"]) == 0
    report_output = capsys.readouterr().out
    assert '"stable_final": true' in report_output
    assert '"classification": "STABLE_SUPPORTED_SURFACE"' in report_output

    assert gcp_cli(["stabilization-report", "--strict-final"]) == 0


def test_gcp_cli_render_writes_artifact_bundle(tmp_path, capsys) -> None:
    contract_path = tmp_path / "contract.yaml"
    environment_path = tmp_path / "environment.yaml"
    output_dir = tmp_path / "bundle"
    contract_path.write_text(
        "\n".join(
            [
                "source:",
                "  type: table",
                "  table: raw.orders",
                "target:",
                "  catalog: test-project",
                "  schema: bronze",
                "  table: orders",
                "mode: overwrite",
            ]
        ),
        encoding="utf-8",
    )
    environment_path.write_text(
        "\n".join(
            [
                "parameters:",
                "  gcp:",
                "    project_id: test-project",
                "    location: US",
                "    dataset: contractforge",
                "evidence:",
                "  dataset: contractforge_ops",
            ]
        ),
        encoding="utf-8",
    )

    assert gcp_cli(["render", str(contract_path), "--environment", str(environment_path), "--output-dir", str(output_dir)]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert "test-project_bronze_orders.gcp.deployment_manifest.json" in payload["artifacts"]
    assert (output_dir / "test-project_bronze_orders.gcp.deployment_manifest.json").exists()
    assert (output_dir / "test-project_bronze_orders.gcp.manifest.json").exists()


def test_gcp_cli_dataplex_quality_plan_writes_report(tmp_path, capsys) -> None:
    contract_path = tmp_path / "contract.yaml"
    environment_path = tmp_path / "environment.yaml"
    report_path = tmp_path / "dataplex.json"
    contract_path.write_text(
        "\n".join(
            [
                "source:",
                "  type: table",
                "  table: raw.orders",
                "target:",
                "  catalog: test-project",
                "  schema: bronze",
                "  table: orders",
                "mode: overwrite",
                "quality_rules:",
                "  not_null: [order_id]",
                "  unique_key: [order_id]",
            ]
        ),
        encoding="utf-8",
    )
    environment_path.write_text(
        "\n".join(
            [
                "parameters:",
                "  gcp:",
                "    project_id: test-project",
                "    location: us",
                "evidence:",
                "  dataset: contractforge_ops",
            ]
        ),
        encoding="utf-8",
    )

    assert gcp_cli(["dataplex-quality", str(contract_path), "--environment", str(environment_path), "--report", str(report_path)]) == 0
    output = json.loads(capsys.readouterr().out)
    payload = json.loads(report_path.read_text(encoding="utf-8"))

    assert output["status"] == "PLANNED_NOT_EXECUTED"
    assert payload["plan"]["data_scan"]["id"] == "cf-bronze-orders-dq"


def test_gcp_cli_dataplex_lineage_aspects_plan_writes_report(tmp_path, capsys) -> None:
    contract_path = tmp_path / "contract.yaml"
    environment_path = tmp_path / "environment.yaml"
    report_path = tmp_path / "dataplex-lineage.json"
    contract_path.write_text(
        "\n".join(
            [
                "source:",
                "  type: table",
                "  table: raw.orders",
                "target:",
                "  catalog: test-project",
                "  schema: bronze",
                "  table: orders",
                "mode: overwrite",
                "annotations:",
                "  table:",
                "    aliases: [sales_orders]",
                "    tags:",
                "      domain: sales",
                "operations:",
                "  criticality: high",
                "  expected_frequency: daily",
            ]
        ),
        encoding="utf-8",
    )
    environment_path.write_text(
        "\n".join(
            [
                "parameters:",
                "  gcp:",
                "    project_id: test-project",
                "    location: us",
                "evidence:",
                "  dataset: contractforge_ops",
            ]
        ),
        encoding="utf-8",
    )

    assert (
        gcp_cli(
            [
                "dataplex-lineage-aspects",
                str(contract_path),
                "--environment",
                str(environment_path),
                "--report",
                str(report_path),
            ]
        )
        == 0
    )
    output = json.loads(capsys.readouterr().out)
    payload = json.loads(report_path.read_text(encoding="utf-8"))

    assert output["status"] == "PLANNED_NOT_EXECUTED"
    assert payload["plans"]["lineage"]["kind"] == "contractforge.gcp.dataplex_lineage_plan.v1"
    assert payload["plans"]["aspects"]["aspect_type"]["id"] == "contractforge-governance"


def test_gcp_project_deployment_manifest_is_deterministic(tmp_path) -> None:
    project, _environment_path = _write_gcp_project(tmp_path)

    manifest = render_gcp_project_deployment_manifest(project)

    assert manifest["status"] == "SUCCEEDED"
    assert manifest["dry_run"] is True
    assert manifest["orchestration_included"] is True
    assert manifest["orchestration_status"] == "CERTIFIED_FOR_STABLE_SURFACE"
    assert manifest["steps"][0]["name"] == "bronze_orders"
    assert manifest["steps"][0]["planning_status"] == "SUPPORTED_WITH_WARNINGS"
    assert manifest["steps"][0]["target_table"] == "test-project.bronze.orders"
    assert manifest["steps"][0]["deployment_manifest"].endswith(".gcp.deployment_manifest.json")


def test_deploy_gcp_project_dry_run_exposes_nested_artifacts(tmp_path) -> None:
    project, _environment_path = _write_gcp_project(tmp_path)

    result = deploy_gcp_project(project, dry_run=True)

    assert result.ok is True
    assert "deployment/gcp_project_deployment_manifest.json" in result.deployment_artifacts
    assert "deployment/gcp_workflows_runner.yaml" in result.deployment_artifacts
    assert "deployment/gcp_workflows_runner_manifest.json" in result.deployment_artifacts
    assert "deployment/gcp_workflows_execution_plan.json" in result.deployment_artifacts
    assert "deployment/gcp_workflows_evidence_readback.json" in result.deployment_artifacts
    assert any(name.endswith(".gcp.write.sql") for name in result.deployment_artifacts)
    assert result.steps[0].deployment_manifest in result.deployment_artifacts
    assert result.steps[0].contract_name == "orders"
    workflow = result.deployment_artifacts["deployment/gcp_workflows_runner.yaml"]
    workflow_manifest = json.loads(result.deployment_artifacts["deployment/gcp_workflows_runner_manifest.json"])
    execution_plan = json.loads(result.deployment_artifacts["deployment/gcp_workflows_execution_plan.json"])
    readback_plan = json.loads(result.deployment_artifacts["deployment/gcp_workflows_evidence_readback.json"])
    assert "call: googleapis.bigquery.v2.jobs.insert" in workflow
    assert "call: googleapis.bigquery.v2.jobs.get" in workflow
    assert "predicate: ${http.default_retry_predicate_non_idempotent}" in workflow
    assert "predicate: ${http.default_retry_predicate}" in workflow
    assert "connector_retry_max_retries: 5" in workflow
    assert "location: ${step_001_bronze_orders_prepare_evidence_job.jobReference.location}" in workflow
    assert "call: sys.sleep" in workflow
    assert "poll_max_attempts: 30" in workflow
    assert "poll_sleep_seconds: 10" in workflow
    assert "\\\n" not in workflow
    assert "CREATE OR REPLACE TABLE `test-project.bronze.orders` AS" in workflow
    assert "INSERT INTO `test-project.contractforge_ops.contractforge_run_evidence`" in workflow
    assert "INSERT INTO `test-project.contractforge_ops.contractforge_schema_evidence`" in workflow
    assert "'contractforge-gcp-workflows'" in workflow
    assert 'contractforge_run_id: ${"workflows:" + sys.get_env("GOOGLE_CLOUD_WORKFLOW_EXECUTION_ID")}' in workflow
    assert "parameterMode: NAMED" in workflow
    assert "name: run_id" in workflow
    assert 'value: ${contractforge_run_id + ":bronze_orders:write_target"}' in workflow
    assert 'value: ${contractforge_run_id + ":bronze_orders:schema_evidence"}' in workflow
    assert workflow_manifest["status"] == "CERTIFIED_FOR_STABLE_SURFACE"
    assert workflow_manifest["workflow"]["execution_plan_artifact"] == "deployment/gcp_workflows_execution_plan.json"
    assert workflow_manifest["workflow"]["evidence_readback_artifact"] == "deployment/gcp_workflows_evidence_readback.json"
    assert workflow_manifest["workflow"]["location"] == "us-central1"
    assert workflow_manifest["wait_polling"] == {
        "api": "googleapis.bigquery.v2.jobs.get",
        "error_behavior": "raise BigQuery errorResult.message",
        "included": True,
        "timeout_behavior": "raise",
    }
    assert workflow_manifest["retry_policy"]["included"] is True
    assert workflow_manifest["retry_policy"]["job_insert_predicate"] == "http.default_retry_predicate_non_idempotent"
    assert workflow_manifest["retry_policy"]["job_get_predicate"] == "http.default_retry_predicate"
    assert workflow_manifest["retry_policy"]["certification_status"] == "CERTIFIED_FOR_STABLE_SURFACE"
    assert workflow_manifest["operation_count"] == 3
    assert [operation["operation_name"] for operation in workflow_manifest["operations"]] == [
        "prepare_evidence",
        "write_target",
        "schema_evidence",
    ]
    assert execution_plan["status"] == "ADAPTER_COMMAND_SURFACE_AVAILABLE"
    assert execution_plan["certification_status"] == "CERTIFIED_FOR_STABLE_SURFACE"
    assert execution_plan["workflow"]["evidence_readback_artifact"] == "deployment/gcp_workflows_evidence_readback.json"
    assert execution_plan["commands"]["deploy"][:4] == ["gcloud", "workflows", "deploy", "cf-gcp-deployment-smoke-runner"]
    assert execution_plan["commands"]["execute"][:4] == [
        "gcloud",
        "workflows",
        "execute",
        "cf-gcp-deployment-smoke-runner",
    ]
    assert readback_plan["kind"] == "contractforge.gcp.workflows_evidence_readback_plan.v1"
    assert readback_plan["evidence"]["dataset"] == "contractforge_ops"
    assert readback_plan["evidence"]["location"] == "US"
    assert readback_plan["targets"] == [
        {"contract_name": "orders", "step_name": "bronze_orders", "target_table": "test-project.bronze.orders"}
    ]
    assert "FROM `test-project.bronze.orders`" in readback_plan["queries"]["target_row_counts"]
    assert "FROM `test-project.contractforge_ops.contractforge_run_evidence`" in readback_plan["queries"]["run_evidence_by_target"]
    assert "target_table IN ('test-project.bronze.orders')" in readback_plan["queries"]["run_evidence_by_target"]
    assert "contract_name IN ('orders')" in readback_plan["queries"]["quality_evidence_by_contract"]


def test_gcp_workflows_renderer_persists_quality_evidence_for_quality_steps() -> None:
    workflow = render_gcp_workflows_runner_yaml(
        project_name="demo",
        project_id="test-project",
        operations=(
            GCPWorkflowOperation(
                step_name="bronze_orders",
                operation_name="quality",
                operation="QUERY",
                artifact="deployment/bronze/orders.gcp.quality.sql",
                body="SELECT 0 AS failed_rows;",
                contract_name="orders",
                target_table="test-project.bronze.orders",
                evidence_dataset="contractforge_ops",
            ),
        ),
    )

    assert "INSERT INTO `test-project.contractforge_ops.contractforge_quality_evidence`" in workflow
    assert "'workflow_quality_query'" in workflow
    assert 'value: ${contractforge_run_id + ":bronze_orders:quality"}' in workflow
    assert "'PASSED'" in workflow
    assert "call: googleapis.bigquery.v2.jobs.getQueryResults" in workflow
    assert "bronze_orders_quality_failed_rows: ${int(" in workflow
    assert "quality_failed_evidence" in workflow
    assert "'FAILED'" in workflow
    assert "Quality check failed with " in workflow


def test_gcp_workflows_renderer_persists_failed_run_evidence_before_write_raise() -> None:
    workflow = render_gcp_workflows_runner_yaml(
        project_name="demo",
        project_id="test-project",
        operations=(
            GCPWorkflowOperation(
                step_name="bronze_orders",
                operation_name="write_target",
                operation="QUERY",
                artifact="deployment/bronze/orders.gcp.write.sql",
                body="SELECT * FROM `missing.dataset.table`",
                contract_name="orders",
                target_table="test-project.bronze.orders",
                evidence_dataset="contractforge_ops",
            ),
        ),
    )

    assert "bronze_orders_write_target_error_message" in workflow
    assert "BigQuery Job failed." in workflow
    assert "status.errorResult.message" in workflow
    assert "write_target_failed_run_evidence" in workflow
    assert "&id" not in workflow
    assert "*id" not in workflow
    assert "INSERT INTO `test-project.contractforge_ops.contractforge_run_evidence`" in workflow
    assert "  'FAILED'," in workflow
    assert "  NULL, NULL, NULL, 'BigQuery Job failed.'" in workflow
    assert "name: error_message" not in workflow
    assert "raise: BigQuery Job failed." in workflow
    assert 'value: ${contractforge_run_id + ":bronze_orders:write_target"}' in workflow


def test_gcp_workflows_renderer_persists_schema_policy_evidence() -> None:
    workflow = render_gcp_workflows_runner_yaml(
        project_name="demo",
        project_id="test-project",
        operations=(
            GCPWorkflowOperation(
                step_name="bronze_orders",
                operation_name="schema_evidence",
                operation="SCHEMA_EVIDENCE",
                artifact="deployment/bronze/orders.gcp.schema_policy.json",
                body='{"policy": {"policy": "permissive"}}',
                contract_name="orders",
                target_table="test-project.bronze.orders",
                evidence_dataset="contractforge_ops",
            ),
        ),
    )

    assert "INSERT INTO `test-project.contractforge_ops.contractforge_schema_evidence`" in workflow
    assert "ARRAY<STRING>[]" in workflow
    assert "planned_no_runtime_drift" in workflow
    assert "'permissive'" in workflow
    assert 'value: ${contractforge_run_id + ":bronze_orders:schema_evidence"}' in workflow


def test_gcp_workflows_renderer_keeps_long_step_ids_unique() -> None:
    workflow = render_gcp_workflows_runner_yaml(
        project_name="demo",
        project_id="test-project",
        operations=(
            GCPWorkflowOperation(
                step_name="bronze_orders_quality_failure",
                operation_name="write_target",
                operation="QUERY",
                artifact="deployment/bronze/orders.gcp.write.sql",
                body="CREATE OR REPLACE TABLE `test-project.bronze.orders` AS SELECT 1 AS id;",
                contract_name="orders",
                target_table="test-project.bronze.orders",
                evidence_dataset="contractforge_ops",
            ),
            GCPWorkflowOperation(
                step_name="bronze_orders_quality_failure",
                operation_name="quality",
                operation="QUERY",
                artifact="deployment/bronze/orders.gcp.quality.sql",
                body="SELECT 1 AS failed_rows;",
                contract_name="orders",
                target_table="test-project.bronze.orders",
                evidence_dataset="contractforge_ops",
            ),
        ),
    )

    step_names = [line.split(":", 1)[0].strip()[2:] for line in workflow.splitlines() if line.startswith("  - ")]

    assert len(step_names) == len(set(step_names))
    assert all(len(name) <= 63 for name in step_names)


def test_gcp_project_deployment_respects_workflows_location(tmp_path) -> None:
    project, _environment_path = _write_gcp_project(tmp_path)
    project.write_text(
        project.read_text(encoding="utf-8")
        + """
deployment:
  gcp:
    workflows:
      location: southamerica-east1
""",
        encoding="utf-8",
    )

    result = deploy_gcp_project(project, dry_run=True)
    workflow_manifest = json.loads(result.deployment_artifacts["deployment/gcp_workflows_runner_manifest.json"])

    assert workflow_manifest["workflow"]["location"] == "southamerica-east1"
    assert workflow_manifest["workflow"]["name"] == "cf-gcp-deployment-smoke-runner"


def test_gcp_workflows_public_renderer_emits_bigquery_job_call() -> None:
    workflow = render_gcp_workflows_runner_yaml(
        project_name="demo",
        project_id="test-project",
        operations=(
            GCPWorkflowOperation(
                step_name="bronze",
                operation_name="write_target",
                operation="QUERY",
                artifact="deployment/bronze/write.sql",
                body="SELECT 1;",
            ),
        ),
    )

    assert workflow_name("demo") == "cf-demo-runner"
    assert "call: googleapis.bigquery.v2.jobs.insert" in workflow
    assert "call: googleapis.bigquery.v2.jobs.get" in workflow
    assert "predicate: ${http.default_retry_predicate_non_idempotent}" in workflow
    assert "predicate: ${http.default_retry_predicate}" in workflow
    assert "location: ${step_001_bronze_write_target_job.jobReference.location}" in workflow
    assert "call: sys.sleep" in workflow
    assert "wait_polling_included: true" in workflow
    assert "poll_max_attempts: 30" in workflow
    assert "poll_sleep_seconds: 10" in workflow
    assert "\\\n" not in workflow
    assert "SELECT 1;" in workflow


def test_gcp_workflows_execution_plan_documents_adapter_command_surface() -> None:
    payload = json.loads(
        render_gcp_workflows_execution_plan(
            project_name="demo",
            project_id="test-project",
            location="us-central1",
            workflow_name="cf-demo-runner",
            service_account="runner@test-project.iam.gserviceaccount.com",
        )
    )

    assert payload["kind"] == "contractforge.gcp.workflows_execution_plan.v1"
    assert payload["commands"]["deploy"] == [
        "gcloud",
        "workflows",
        "deploy",
        "cf-demo-runner",
        "--project=test-project",
        "--location=us-central1",
        "--source=deployment/gcp_workflows_runner.yaml",
        "--service-account=runner@test-project.iam.gserviceaccount.com",
        "--format=json",
        "--quiet",
    ]
    assert payload["commands"]["wait_template"][4] == "${execution_id}"
    assert payload["commands"]["cleanup"] == [
        "gcloud",
        "workflows",
        "delete",
        "cf-demo-runner",
        "--project=test-project",
        "--location=us-central1",
        "--quiet",
    ]
    assert payload["contractforge_cli"]["deploy_execute_wait"][-3:] == [
        "--deploy-orchestration",
        "--run-orchestration",
        "--wait-orchestration",
    ]
    assert payload["contractforge_cli"]["deploy_execute_wait_readback"][-4:] == [
        "--deploy-orchestration",
        "--run-orchestration",
        "--wait-orchestration",
        "--readback-orchestration",
    ]
    assert payload["contractforge_cli"]["reset_deploy_execute_wait_readback"][-5:] == [
        "--reset-orchestration-data",
        "--deploy-orchestration",
        "--run-orchestration",
        "--wait-orchestration",
        "--readback-orchestration",
    ]
    assert payload["contractforge_cli"]["cleanup"][-1] == "--cleanup-orchestration"
    assert payload["contractforge_cli"]["cleanup_data"][-1] == "--cleanup-orchestration-data"
    assert "Caller needs Workflows delete permissions for cleanup orchestration." in payload["required_permissions"]
    assert (
        "Caller needs BigQuery table delete and data update permissions for reset-orchestration-data."
        in payload["required_permissions"]
    )
    assert (
        "Caller needs BigQuery table delete and data update permissions for cleanup-orchestration-data."
        in payload["required_permissions"]
    )
    assert any("Cloud Run Jobs" in item for item in payload["promotion_blockers"])


def test_gcp_workflows_evidence_readback_plan_documents_queries() -> None:
    payload = json.loads(
        render_gcp_workflows_evidence_readback_plan(
            project_name="demo",
            project_id="test-project",
            evidence_dataset="contractforge_ops",
            targets=(
                GCPWorkflowReadbackTarget(
                    step_name="bronze_orders",
                    contract_name="orders",
                    target_table="test-project.bronze.orders",
                ),
                GCPWorkflowReadbackTarget(
                    step_name="gold_orders",
                    contract_name="orders_daily",
                    target_table="test-project.gold.orders_daily",
                ),
            ),
        )
    )

    assert payload["kind"] == "contractforge.gcp.workflows_evidence_readback_plan.v1"
    assert payload["certification_status"] == "CERTIFIED_FOR_STABLE_SURFACE"
    assert payload["evidence"]["location"] == "US"
    assert payload["evidence"]["tables"] == [
        "contractforge_run_evidence",
        "contractforge_quality_evidence",
        "contractforge_schema_evidence",
        "contractforge_annotation_evidence",
        "contractforge_governance_evidence",
        "contractforge_lineage_evidence",
    ]
    assert "UNION ALL" in payload["queries"]["target_row_counts"]
    assert "FROM `test-project.bronze.orders`" in payload["queries"]["target_row_counts"]
    assert "FROM `test-project.gold.orders_daily`" in payload["queries"]["target_row_counts"]
    assert "target_table IN ('test-project.bronze.orders', 'test-project.gold.orders_daily')" in payload["queries"][
        "run_evidence_by_target"
    ]
    assert "contract_name IN ('orders', 'orders_daily')" in payload["queries"]["quality_evidence_by_contract"]
    assert "execution_scoped_queries" in payload
    assert "run_id LIKE CONCAT('workflows:', ${workflow_execution_id_sql}, ':%')" in payload[
        "execution_scoped_queries"
    ]["run_evidence_by_target"]
    assert "run_id LIKE CONCAT('workflows:', ${workflow_execution_id_sql}, ':%')" in payload[
        "execution_scoped_queries"
    ]["quality_evidence_by_contract"]
    assert "run_id LIKE CONCAT('workflows:', ${workflow_execution_id_sql}, ':%')" in payload[
        "execution_scoped_queries"
    ]["schema_evidence_by_target"]
    assert "INFORMATION_SCHEMA.TABLES" in payload["queries"]["evidence_table_presence"]
    assert "certified for the adapter-owned Workflows runner" in payload["promotion_blockers"][0]
    assert "Non-Workflows orchestration surfaces" in payload["promotion_blockers"][1]


def test_gcp_workflows_cleanup_plan_documents_scoped_cleanup_queries() -> None:
    payload = json.loads(
        render_gcp_workflows_cleanup_plan(
            project_name="demo",
            project_id="test-project",
            evidence_dataset="contractforge_ops",
            targets=(
                GCPWorkflowReadbackTarget(
                    step_name="bronze_orders",
                    contract_name="orders",
                    target_table="test-project.bronze.orders",
                ),
                GCPWorkflowReadbackTarget(
                    step_name="gold_orders",
                    contract_name="orders_daily",
                    target_table="test-project.gold.orders_daily",
                ),
            ),
        )
    )

    assert payload["kind"] == "contractforge.gcp.workflows_cleanup_plan.v1"
    assert payload["certification_status"] == "CERTIFIED_FOR_STABLE_SURFACE"
    assert payload["queries"]["01_drop_target_bronze_orders"] == "DROP TABLE IF EXISTS `test-project.bronze.orders`;"
    assert payload["queries"]["01_drop_target_gold_orders"] == "DROP TABLE IF EXISTS `test-project.gold.orders_daily`;"
    assert "target_table IN ('test-project.bronze.orders', 'test-project.gold.orders_daily')" in payload["queries"][
        "02_delete_run_evidence_by_target"
    ]
    assert "contract_name IN ('orders', 'orders_daily')" in payload["queries"][
        "07_delete_quality_evidence_by_contract"
    ]
    assert "DROP SCHEMA" not in json.dumps(payload["queries"])
    assert all(" WHERE " in sql or sql.startswith("DROP TABLE IF EXISTS") for sql in payload["queries"].values())
    assert "deterministic and adapter-owned" in payload["promotion_blockers"][0]
    assert "--reset-orchestration-data" in payload["promotion_blockers"][1]
    assert "--cleanup-orchestration-data" in payload["promotion_blockers"][2]


def test_gcp_workflows_runtime_runs_deploy_execute_wait_with_runner(tmp_path) -> None:
    workflow_source = tmp_path / "workflow.yaml"
    workflow_source.write_text("main:\n  steps: []\n", encoding="utf-8")
    calls = []

    def fake_runner(command):
        import subprocess

        calls.append(list(command))
        if command[2] == "deploy":
            return subprocess.CompletedProcess(command, 0, stdout='{"name":"cf-demo-runner"}\n', stderr="")
        if command[2] == "execute":
            return subprocess.CompletedProcess(
                command,
                0,
                stdout='{"name":"projects/test-project/locations/us-central1/workflows/cf-demo-runner/executions/run-1"}\n',
                stderr="",
            )
        if command[2] == "executions" and command[3] == "wait":
            return subprocess.CompletedProcess(command, 0, stdout='{"state":"SUCCEEDED"}\n', stderr="")
        if command[2] == "executions" and command[3] == "describe":
            return subprocess.CompletedProcess(command, 0, stdout='{"state":"SUCCEEDED","result":"{}"}\n', stderr="")
        raise AssertionError(command)

    payload = run_gcp_workflows_orchestration(
        workflow_manifest={
            "workflow": {"name": "cf-demo-runner", "project_id": "test-project", "location": "us-central1"}
        },
        workflow_source=workflow_source,
        deploy=True,
        run=True,
        wait=True,
        runner=fake_runner,
    )

    assert payload["deployment"]["name"] == "cf-demo-runner"
    assert payload["execution"]["name"].endswith("/executions/run-1")
    assert payload["wait"]["state"] == "SUCCEEDED"
    assert payload["describe"]["state"] == "SUCCEEDED"
    assert calls[0][:4] == ["gcloud", "workflows", "deploy", "cf-demo-runner"]
    assert calls[1][:4] == ["gcloud", "workflows", "execute", "cf-demo-runner"]
    assert calls[2][4] == "run-1"


def test_gcp_workflows_runtime_runs_cleanup_and_tolerates_missing_workflow(tmp_path) -> None:
    workflow_source = tmp_path / "workflow.yaml"
    workflow_source.write_text("main:\n  steps: []\n", encoding="utf-8")
    calls = []

    def fake_runner(command):
        import subprocess

        calls.append(list(command))
        if len(calls) == 1:
            return subprocess.CompletedProcess(command, 0, stdout="Deleted workflow\n", stderr="")
        return subprocess.CompletedProcess(
            command,
            1,
            stdout="",
            stderr="NOT_FOUND: workflow does not exist. This command is authenticated as user@example.com",
        )

    manifest = {"workflow": {"name": "cf-demo-runner", "project_id": "test-project", "location": "us-central1"}}

    deleted = run_gcp_workflows_orchestration(
        workflow_manifest=manifest,
        workflow_source=workflow_source,
        cleanup=True,
        runner=fake_runner,
    )
    skipped = run_gcp_workflows_orchestration(
        workflow_manifest=manifest,
        workflow_source=workflow_source,
        cleanup=True,
        runner=fake_runner,
    )

    assert deleted["cleanup"]["status"] == "SUCCEEDED"
    assert skipped["cleanup"]["status"] == "SKIPPED"
    assert skipped["cleanup"]["reason"] == "workflow_not_found"
    assert "user@example.com" not in skipped["cleanup"]["raw"]
    assert "<redacted-email>" in skipped["cleanup"]["raw"]
    assert calls[0] == [
        "gcloud",
        "workflows",
        "delete",
        "cf-demo-runner",
        "--project=test-project",
        "--location=us-central1",
        "--quiet",
    ]


def test_gcp_workflows_runtime_runs_cleanup_data_queries_with_bq(tmp_path) -> None:
    workflow_source = tmp_path / "workflow.yaml"
    workflow_source.write_text("main:\n  steps: []\n", encoding="utf-8")
    calls = []

    def fake_runner(command):
        import subprocess

        calls.append(list(command))
        assert command[0] == "bq"
        return subprocess.CompletedProcess(command, 0, stdout="[]\n", stderr="")

    cleanup_plan = json.loads(
        render_gcp_workflows_cleanup_plan(
            project_name="demo",
            project_id="test-project",
            evidence_dataset="ops",
            location="southamerica-east1",
            targets=(
                GCPWorkflowReadbackTarget(
                    step_name="bronze",
                    contract_name="orders",
                    target_table="test-project.bronze.orders",
                ),
            ),
        )
    )

    payload = run_gcp_workflows_orchestration(
        workflow_manifest={
            "workflow": {"name": "cf-demo-runner", "project_id": "test-project", "location": "us-central1"}
        },
        workflow_source=workflow_source,
        cleanup_plan=cleanup_plan,
        cleanup_data=True,
        readback_location="us-east1",
        runner=fake_runner,
    )

    assert payload["cleanup_data"]["status"] == "SUCCEEDED"
    assert payload["cleanup_data"]["query_count"] == 7
    assert payload["commands"]["cleanup_data"]["01_drop_target_bronze"][:5] == [
        "bq",
        "--project_id=test-project",
        "--location=us-east1",
        "--format=json",
        "query",
    ]
    assert calls[0][-1] == "DROP TABLE IF EXISTS `test-project.bronze.orders`;"


def test_gcp_workflows_runtime_runs_reset_data_before_deploy_execute(tmp_path) -> None:
    workflow_source = tmp_path / "workflow.yaml"
    workflow_source.write_text("main:\n  steps: []\n", encoding="utf-8")
    calls = []

    def fake_runner(command):
        import subprocess

        calls.append(list(command))
        if command[0] == "bq":
            return subprocess.CompletedProcess(command, 0, stdout="[]\n", stderr="")
        if command[2] == "deploy":
            return subprocess.CompletedProcess(command, 0, stdout='{"name":"cf-demo-runner"}\n', stderr="")
        if command[2] == "execute":
            return subprocess.CompletedProcess(
                command,
                0,
                stdout='{"name":"projects/test-project/locations/us-central1/workflows/cf-demo-runner/executions/run-1"}\n',
                stderr="",
            )
        if command[2] == "executions" and command[3] == "wait":
            return subprocess.CompletedProcess(command, 0, stdout='{"state":"SUCCEEDED"}\n', stderr="")
        if command[2] == "executions" and command[3] == "describe":
            return subprocess.CompletedProcess(command, 0, stdout='{"state":"SUCCEEDED"}\n', stderr="")
        raise AssertionError(command)

    cleanup_plan = json.loads(
        render_gcp_workflows_cleanup_plan(
            project_name="demo",
            project_id="test-project",
            evidence_dataset="ops",
            targets=(
                GCPWorkflowReadbackTarget(
                    step_name="bronze",
                    contract_name="orders",
                    target_table="test-project.bronze.orders",
                ),
            ),
        )
    )

    payload = run_gcp_workflows_orchestration(
        workflow_manifest={
            "workflow": {"name": "cf-demo-runner", "project_id": "test-project", "location": "us-central1"}
        },
        workflow_source=workflow_source,
        cleanup_plan=cleanup_plan,
        reset_data=True,
        deploy=True,
        run=True,
        wait=True,
        runner=fake_runner,
    )

    assert payload["reset_data"]["status"] == "SUCCEEDED"
    assert payload["deployment"]["name"] == "cf-demo-runner"
    assert payload["execution"]["name"].endswith("/executions/run-1")
    assert calls[0][0] == "bq"
    assert calls[7][:4] == ["gcloud", "workflows", "deploy", "cf-demo-runner"]
    assert calls[8][:4] == ["gcloud", "workflows", "execute", "cf-demo-runner"]


def test_gcp_workflows_runtime_runs_readback_queries_with_bq(tmp_path) -> None:
    workflow_source = tmp_path / "workflow.yaml"
    workflow_source.write_text("main:\n  steps: []\n", encoding="utf-8")
    calls = []

    def fake_runner(command):
        import subprocess

        calls.append(list(command))
        assert command[0] == "bq"
        return subprocess.CompletedProcess(command, 0, stdout='[{"row_count": "2"}]\n', stderr="")

    readback_plan = json.loads(
        render_gcp_workflows_evidence_readback_plan(
            project_name="demo",
            project_id="test-project",
            evidence_dataset="ops",
            location="southamerica-east1",
            targets=(
                GCPWorkflowReadbackTarget(
                    step_name="bronze",
                    contract_name="orders",
                    target_table="test-project.bronze.orders",
                ),
            ),
        )
    )

    payload = run_gcp_workflows_orchestration(
        workflow_manifest={
            "workflow": {"name": "cf-demo-runner", "project_id": "test-project", "location": "us-central1"}
        },
        workflow_source=workflow_source,
        readback_plan=readback_plan,
        readback=True,
        readback_location="us-east1",
        execution_id="run-1",
        runner=fake_runner,
    )

    assert payload["readback"]["status"] == "SUCCEEDED"
    assert payload["readback"]["execution_scoped"] is True
    assert payload["readback"]["execution_id"] == "run-1"
    assert payload["readback"]["query_count"] == 5
    assert payload["readback"]["queries"]["target_row_counts"]["rows"] == [{"row_count": "2"}]
    assert payload["commands"]["readback"]["target_row_counts"][:5] == [
        "bq",
        "--project_id=test-project",
        "--location=us-east1",
        "--format=json",
        "query",
    ]
    assert "CONCAT('workflows:', 'run-1', ':%')" in payload["commands"]["readback"]["run_evidence_by_target"][-1]
    assert "\n" not in payload["commands"]["readback"]["evidence_table_presence"][-1]
    assert len(calls) == 5


def test_gcp_workflows_runtime_preserves_readback_error_stdout(tmp_path) -> None:
    workflow_source = tmp_path / "workflow.yaml"
    workflow_source.write_text("main:\n  steps: []\n", encoding="utf-8")

    def fake_runner(command):
        import subprocess

        return subprocess.CompletedProcess(command, 1, stdout="BigQuery location mismatch", stderr="")

    readback_plan = json.loads(
        render_gcp_workflows_evidence_readback_plan(
            project_name="demo",
            project_id="test-project",
            evidence_dataset="ops",
            targets=(
                GCPWorkflowReadbackTarget(
                    step_name="bronze",
                    contract_name="orders",
                    target_table="test-project.bronze.orders",
                ),
            ),
        )
    )

    try:
        run_gcp_workflows_orchestration(
            workflow_manifest={
                "workflow": {"name": "cf-demo-runner", "project_id": "test-project", "location": "us-central1"}
            },
            workflow_source=workflow_source,
            readback_plan=readback_plan,
            readback=True,
            runner=fake_runner,
        )
    except RuntimeError as exc:
        assert "BigQuery location mismatch" in str(exc)
    else:
        raise AssertionError("readback failure should preserve stdout error text")


def test_gcp_workflows_runtime_resolves_platform_executables(monkeypatch) -> None:
    import subprocess

    import contractforge_gcp.deployment.workflows_runtime as workflows_runtime

    calls = []

    def fake_which(executable):
        return {"gcloud": "C:/sdk/gcloud.cmd", "bq": "C:/sdk/bq.cmd"}.get(executable)

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout="{}", stderr="")

    monkeypatch.setattr(workflows_runtime.shutil, "which", fake_which)
    monkeypatch.setattr(workflows_runtime.subprocess, "run", fake_run)

    workflows_runtime._run_command(["gcloud", "workflows", "deploy", "cf-demo"])
    workflows_runtime._run_command(["bq", "query", "SELECT 1"])

    assert calls[0][0][0] == "C:/sdk/gcloud.cmd"
    assert calls[1][0][0] == "C:/sdk/bq.cmd"
    assert calls[0][1] == {"check": False, "capture_output": True, "text": True}


def test_gcp_cli_deploy_project_dry_run_outputs_summary_and_artifacts(tmp_path, capsys) -> None:
    project, _environment_path = _write_gcp_project(tmp_path)
    output_dir = tmp_path / "deployment"

    exit_code = gcp_cli(["deploy-project", str(project), "--dry-run", "--summary-only", "--output-dir", str(output_dir)])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "SUCCEEDED"
    assert payload["orchestration_status"] == "CERTIFIED_FOR_STABLE_SURFACE"
    assert payload["steps"][0]["name"] == "bronze_orders"
    assert (output_dir / "deployment" / "gcp_project_deployment_manifest.json").exists()
    assert (output_dir / "deployment" / "gcp_workflows_runner.yaml").exists()
    assert (output_dir / "deployment" / "gcp_workflows_runner_manifest.json").exists()
    assert (output_dir / "deployment" / "gcp_workflows_execution_plan.json").exists()
    assert (output_dir / "deployment" / "gcp_workflows_evidence_readback.json").exists()
    assert (output_dir / "deployment" / "gcp_workflows_cleanup_plan.json").exists()
    assert any(path.name.endswith(".gcp.write.sql") for path in output_dir.rglob("*"))


def test_gcp_cli_deploy_project_can_render_workflows_orchestration(tmp_path, capsys) -> None:
    project, _environment_path = _write_gcp_project(tmp_path)
    output_dir = tmp_path / "deployment"

    exit_code = gcp_cli(
        [
            "deploy-project",
            str(project),
            "--dry-run",
            "--render-orchestration",
            "--output-dir",
            str(output_dir),
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["orchestration"]["type"] == "workflows"
    assert payload["orchestration"]["workflow"]["name"] == "cf-gcp-deployment-smoke-runner"
    assert payload["orchestration"]["commands"]["deploy"][:4] == [
        "gcloud",
        "workflows",
        "deploy",
        "cf-gcp-deployment-smoke-runner",
    ]
    assert payload["orchestration"]["commands"]["cleanup"] == [
        "gcloud",
        "workflows",
        "delete",
        "cf-gcp-deployment-smoke-runner",
        "--project=test-project",
        "--location=us-central1",
        "--quiet",
    ]
    assert payload["orchestration"]["commands"]["readback"]["target_row_counts"][:5] == [
        "bq",
        "--project_id=test-project",
        "--location=US",
        "--format=json",
        "query",
    ]
    assert payload["orchestration"]["commands"]["cleanup_data"]["01_drop_target_bronze_orders"][:5] == [
        "bq",
        "--project_id=test-project",
        "--location=US",
        "--format=json",
        "query",
    ]
    assert payload["orchestration"]["commands"]["reset_data"]["01_drop_target_bronze_orders"][:5] == [
        "bq",
        "--project_id=test-project",
        "--location=US",
        "--format=json",
        "query",
    ]
    assert payload["orchestration"]["source"] == str(output_dir / "deployment" / "gcp_workflows_runner.yaml")


def test_gcp_cli_deploy_project_invokes_workflows_orchestration(tmp_path, monkeypatch, capsys) -> None:
    project, _environment_path = _write_gcp_project(tmp_path)
    calls = []

    def fake_orchestration(**kwargs):
        calls.append(kwargs)
        return {
            "type": "workflows",
            "workflow": kwargs["workflow_manifest"]["workflow"],
            "deployment": {"name": kwargs["workflow_manifest"]["workflow"]["name"]},
            "execution": {"name": "projects/test/locations/us-central1/workflows/cf/executions/run-1"},
            "wait": {"state": "SUCCEEDED"},
            "readback": {"status": "SUCCEEDED"},
        }

    import contractforge_gcp.cli as gcp_cli_module

    monkeypatch.setattr(gcp_cli_module, "run_gcp_workflows_orchestration", fake_orchestration)

    exit_code = gcp_cli(
        [
            "deploy-project",
            str(project),
            "--deploy-orchestration",
            "--run-orchestration",
            "--wait-orchestration",
            "--readback-orchestration",
            "--reset-orchestration-data",
            "--cleanup-orchestration",
            "--cleanup-orchestration-data",
            "--readback-location",
            "us-east1",
            "--workflow-execution-id",
            "run-existing",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["orchestration"]["wait"]["state"] == "SUCCEEDED"
    assert calls[0]["deploy"] is True
    assert calls[0]["run"] is True
    assert calls[0]["wait"] is True
    assert calls[0]["readback"] is True
    assert calls[0]["reset_data"] is True
    assert calls[0]["cleanup"] is True
    assert calls[0]["cleanup_data"] is True
    assert calls[0]["readback_location"] == "us-east1"
    assert calls[0]["execution_id"] == "run-existing"
    assert calls[0]["readback_plan"]["kind"] == "contractforge.gcp.workflows_evidence_readback_plan.v1"
    assert calls[0]["cleanup_plan"]["kind"] == "contractforge.gcp.workflows_cleanup_plan.v1"
    assert calls[0]["workflow_manifest"]["workflow"]["name"] == "cf-gcp-deployment-smoke-runner"


def test_gcp_cli_deploy_project_rejects_dry_run_apply_orchestration(tmp_path) -> None:
    project, _environment_path = _write_gcp_project(tmp_path)

    try:
        gcp_cli(["deploy-project", str(project), "--dry-run", "--deploy-orchestration"])
    except ValueError as exc:
        assert "--dry-run cannot be combined" in str(exc)
    else:
        raise AssertionError("dry-run must not execute Workflows orchestration")

    try:
        gcp_cli(["deploy-project", str(project), "--dry-run", "--readback-orchestration"])
    except ValueError as exc:
        assert "--readback-orchestration" in str(exc)
    else:
        raise AssertionError("dry-run must not execute Workflows readback")

    try:
        gcp_cli(["deploy-project", str(project), "--dry-run", "--cleanup-orchestration"])
    except ValueError as exc:
        assert "--cleanup-orchestration" in str(exc)
    else:
        raise AssertionError("dry-run must not execute Workflows cleanup")

    try:
        gcp_cli(["deploy-project", str(project), "--dry-run", "--reset-orchestration-data"])
    except ValueError as exc:
        assert "--reset-orchestration-data" in str(exc)
    else:
        raise AssertionError("dry-run must not execute Workflows target/evidence reset")

    try:
        gcp_cli(["deploy-project", str(project), "--dry-run", "--cleanup-orchestration-data"])
    except ValueError as exc:
        assert "--cleanup-orchestration-data" in str(exc)
    else:
        raise AssertionError("dry-run must not execute Workflows target/evidence cleanup")
