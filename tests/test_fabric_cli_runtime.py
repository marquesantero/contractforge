from __future__ import annotations

import json
from types import SimpleNamespace

import yaml

import contractforge_fabric.cli as fabric_cli_module
from contractforge_fabric import fabric_stabilization_report
from contractforge_fabric.runtime import FabricPreflightCheck, FabricWorkspacePreflight


def test_fabric_cli_preflight_prints_runtime_evidence(tmp_path, monkeypatch, capsys) -> None:
    environment_path = tmp_path / "fabric.env.yaml"
    environment_path.write_text(
        yaml.safe_dump({"parameters": {"fabric": {"workspace_id": "workspace-1"}}}),
        encoding="utf-8",
    )

    def fake_preflight(
        environment,
        *,
        require_lakehouse,
        require_notebook,
        check_spark_settings,
        check_notebook_jobs,
    ):
        assert environment["parameters"]["fabric"]["workspace_id"] == "workspace-1"
        assert require_lakehouse is True
        assert require_notebook is True
        assert check_spark_settings is True
        assert check_notebook_jobs is True
        return FabricWorkspacePreflight(
            status="OK",
            workspace={"id": "workspace-1", "capacityId": "capacity-1"},
            items={"lakehouse": {"id": "lakehouse-1"}, "notebook": {"id": "notebook-1"}},
            checks=(
                FabricPreflightCheck(
                    code="FABRIC_WORKSPACE_READABLE",
                    status="OK",
                    message="Fabric workspace metadata is readable.",
                    details={"workspace_id": "workspace-1"},
                ),
            ),
        )

    monkeypatch.setattr(fabric_cli_module, "check_fabric_workspace_preflight", fake_preflight)

    rc = fabric_cli_module.main(
        [
            "preflight",
            "--environment",
            str(environment_path),
            "--require-lakehouse",
            "--require-notebook",
            "--check-spark-settings",
            "--check-notebook-jobs",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["status"] == "OK"
    assert payload["ok"] is True
    assert payload["workspace"]["capacityId"] == "capacity-1"
    assert payload["checks"][0]["code"] == "FABRIC_WORKSPACE_READABLE"


def test_fabric_cli_preflight_returns_nonzero_when_blocked(tmp_path, monkeypatch, capsys) -> None:
    environment_path = tmp_path / "fabric.env.yaml"
    environment_path.write_text(
        yaml.safe_dump({"parameters": {"fabric": {"workspace_id": "workspace-1"}}}),
        encoding="utf-8",
    )

    def fake_preflight(
        environment,
        *,
        require_lakehouse,
        require_notebook,
        check_spark_settings,
        check_notebook_jobs,
    ):
        assert check_spark_settings is False
        assert check_notebook_jobs is False
        return FabricWorkspacePreflight(
            status="BLOCKED",
            workspace={"id": "workspace-1", "type": "Personal"},
            items={},
            checks=(
                FabricPreflightCheck(
                    code="FABRIC_WORKSPACE_CAPACITY_REQUIRED",
                    status="BLOCKED",
                    message="Fabric workspace is not assigned to a supported capacity.",
                ),
            ),
        )

    monkeypatch.setattr(fabric_cli_module, "check_fabric_workspace_preflight", fake_preflight)

    rc = fabric_cli_module.main(["preflight", "--environment", str(environment_path)])

    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert payload["status"] == "BLOCKED"
    assert payload["ok"] is False


def test_fabric_cli_smoke_prints_contract_smoke_evidence(tmp_path, monkeypatch, capsys) -> None:
    contract_path = tmp_path / "contract.yaml"
    contract_path.write_text(
        yaml.safe_dump(
            {
                "source": {"type": "sql", "query": "SELECT 1 AS id"},
                "target": {"schema": "default", "table": "cf_smoke_sql"},
                "mode": "overwrite",
            }
        ),
        encoding="utf-8",
    )
    environment_path = tmp_path / "fabric.env.yaml"
    environment_path.write_text(
        yaml.safe_dump({"parameters": {"fabric": {"workspace_id": "workspace-1", "lakehouse_id": "lakehouse-1"}}}),
        encoding="utf-8",
    )
    seen: dict[str, object] = {}

    def fake_smoke(contract, environment, *, wait, max_attempts, retry_after_seconds):
        seen.update(
            {
                "contract": contract,
                "environment": environment,
                "wait": wait,
                "max_attempts": max_attempts,
                "retry_after_seconds": retry_after_seconds,
            }
        )
        return SimpleNamespace(
            ok=True,
            status="SUCCEEDED",
            to_dict=lambda: {
                "status": "SUCCEEDED",
                "ok": True,
                "outcome": {"code": "FABRIC_NOTEBOOK_RUN_SUCCEEDED"},
            },
        )

    monkeypatch.setattr(fabric_cli_module, "run_fabric_contract_smoke", fake_smoke)

    rc = fabric_cli_module.main(
        [
            "smoke",
            str(contract_path),
            "--environment",
            str(environment_path),
            "--no-wait",
            "--max-attempts",
            "7",
            "--retry-after-seconds",
            "0",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["status"] == "SUCCEEDED"
    assert seen["wait"] is False
    assert seen["max_attempts"] == 7
    assert seen["retry_after_seconds"] == 0
    assert seen["contract"]["source"]["type"] == "sql"


def test_fabric_cli_smoke_returns_blocked_code(tmp_path, monkeypatch, capsys) -> None:
    contract_path = tmp_path / "contract.yaml"
    contract_path.write_text(yaml.safe_dump({"source": {"type": "sql"}, "target": {"table": "t"}}), encoding="utf-8")
    environment_path = tmp_path / "fabric.env.yaml"
    environment_path.write_text(yaml.safe_dump({"parameters": {"fabric": {"workspace_id": "workspace-1"}}}), encoding="utf-8")

    monkeypatch.setattr(
        fabric_cli_module,
        "run_fabric_contract_smoke",
        lambda *args, **kwargs: SimpleNamespace(
            ok=False,
            status="BLOCKED",
            to_dict=lambda: {"status": "BLOCKED", "ok": False},
        ),
    )

    rc = fabric_cli_module.main(["smoke", str(contract_path), "--environment", str(environment_path)])

    payload = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert payload == {"status": "BLOCKED", "ok": False}


def test_fabric_cli_smoke_project_prints_project_evidence(tmp_path, monkeypatch, capsys) -> None:
    project_path = tmp_path / "project.yaml"
    project_path.write_text(yaml.safe_dump({"execution_order": []}), encoding="utf-8")
    environment_path = tmp_path / "fabric.env.yaml"
    environment_path.write_text(yaml.safe_dump({"parameters": {"fabric": {"workspace_id": "workspace-1"}}}), encoding="utf-8")
    seen: dict[str, object] = {}

    def fake_project_smoke(
        project,
        *,
        environment,
        environment_key,
        wait,
        max_attempts,
        retry_after_seconds,
        stop_on_failure,
        start_at,
    ):
        seen.update(
            {
                "project": project,
                "environment": environment,
                "environment_key": environment_key,
                "wait": wait,
                "max_attempts": max_attempts,
                "retry_after_seconds": retry_after_seconds,
                "stop_on_failure": stop_on_failure,
                "start_at": start_at,
            }
        )
        return SimpleNamespace(
            ok=True,
            status="SUCCEEDED",
            to_dict=lambda: {"status": "SUCCEEDED", "ok": True, "steps": [{"name": "bronze"}]},
        )

    monkeypatch.setattr(fabric_cli_module, "run_fabric_project_smoke", fake_project_smoke)

    rc = fabric_cli_module.main(
        [
            "run-project",
            str(project_path),
            "--environment",
            str(environment_path),
            "--environment-key",
            "fabric",
            "--no-wait",
            "--max-attempts",
            "9",
            "--retry-after-seconds",
            "0",
            "--continue-on-failure",
            "--start-at",
            "quality_abort_failure",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["steps"][0]["name"] == "bronze"
    assert seen["project"] == project_path
    assert seen["environment"] == environment_path
    assert seen["environment_key"] == "fabric"
    assert seen["wait"] is False
    assert seen["max_attempts"] == 9
    assert seen["retry_after_seconds"] == 0
    assert seen["stop_on_failure"] is False
    assert seen["start_at"] == "quality_abort_failure"


def test_fabric_cli_stabilization_report_is_stable_final_for_supported_surface(capsys) -> None:
    rc = fabric_cli_module.main(["stabilization-report"])

    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["adapter"] == "contractforge-fabric"
    assert payload["subtarget"] == "fabric_lakehouse"
    assert payload["classification"] == "STABLE_SUPPORTED_SURFACE"
    assert payload["supported_surface_ready"] is True
    assert payload["stable_final"] is True
    assert payload["stability_criteria"] == "docs/adapters/fabric.md"
    assert set(payload["evidence_manifests"]) == {
        "docs/reports/fabric-usgs-rest-e2e-smoke.json",
        "docs/reports/fabric-stable-surface-evidence.json",
        "docs/reports/fabric-platform-parity.json",
        "docs/reports/fabric-source-expansion-stable-scope-decision.json",
        "docs/reports/fabric-project-deploy-smoke.json",
        "docs/reports/fabric-onelake-data-access-role-smoke.json",
        "docs/reports/fabric-onelake-row-column-policy-smoke.json",
        "docs/reports/fabric-deployment-pipeline-read-probe.json",
        "docs/reports/fabric-deployment-pipeline-lifecycle-smoke.json",
        "docs/reports/fabric-deployment-pipeline-stage-promotion-smoke.json",
        "docs/reports/fabric-http-json-source-smoke.json",
        "docs/reports/fabric-http-csv-source-smoke.json",
        "docs/reports/fabric-http-text-source-smoke.json",
        "docs/reports/fabric-lakehouse-text-source-smoke.json",
        "docs/reports/fabric-lakehouse-file-formats-source-smoke.json",
        "docs/reports/fabric-onelake-shortcut-source-smoke.json",
        "docs/reports/fabric-auth-rest-source-smoke.json",
        "docs/reports/fabric-auth-rest-variants-source-smoke.json",
        "docs/reports/fabric-auth-rest-oauth-source-smoke.json",
        "docs/reports/fabric-auth-http-json-source-smoke.json",
        "docs/reports/fabric-auth-http-json-variants-source-smoke.json",
        "docs/reports/fabric-auth-http-csv-variants-source-smoke.json",
        "docs/reports/fabric-auth-http-text-basic-source-smoke.json",
        "docs/reports/fabric-auth-http-text-bearer-source-smoke.json",
        "docs/reports/fabric-auth-http-text-api-key-source-smoke.json",
        "docs/reports/fabric-sqlserver-jdbc-source-smoke.json",
        "docs/reports/fabric-postgres-jdbc-source-smoke.json",
        "docs/reports/fabric-azure-blob-source-smoke.json",
        "docs/reports/fabric-private-azure-blob-source-smoke.json",
        "docs/reports/fabric-external-azure-blob-shortcut-source-smoke.json",
        "docs/reports/fabric-adls-shortcut-source-smoke.json",
        "docs/reports/fabric-gcs-shortcut-source-smoke.json",
        "docs/reports/fabric-external-s3-shortcut-source-smoke.json",
        "docs/reports/fabric-s3-compatible-shortcut-source-smoke.json",
        "docs/reports/fabric-iceberg-table-shortcut-source-smoke.json",
        "docs/reports/fabric-adls-iceberg-table-shortcut-source-smoke.json",
        "docs/reports/fabric-gcs-iceberg-table-shortcut-source-smoke.json",
        "docs/reports/fabric-confluent-kafka-bounded-source-smoke.json",
        "docs/reports/fabric-confluent-kafka-available-now-source-smoke.json",
        "docs/reports/fabric-eventhubs-kafka-available-now-source-smoke.json",
    }
    assert {project["name"] for project in payload["real_validation_projects"]} == {
        "fabric_usgs_rest_medallion",
        "fabric_stable_surface_sql_suite",
        "fabric_http_json_source_expansion",
        "fabric_http_csv_source_expansion",
        "fabric_http_text_source_expansion",
        "fabric_lakehouse_text_source_expansion",
        "fabric_lakehouse_file_formats_source_expansion",
        "fabric_onelake_shortcut_source_expansion",
        "fabric_authenticated_rest_source_expansion",
        "fabric_authenticated_rest_variants_source_expansion",
        "fabric_authenticated_rest_oauth_source_expansion",
        "fabric_authenticated_http_json_source_expansion",
        "fabric_authenticated_http_json_variants_source_expansion",
        "fabric_authenticated_http_csv_variants_source_expansion",
        "fabric_endpoint_enforced_http_text_basic_source_expansion",
        "fabric_endpoint_enforced_http_text_bearer_source_expansion",
        "fabric_endpoint_enforced_http_text_api_key_source_expansion",
        "fabric_sqlserver_jdbc_source_expansion",
        "fabric_postgres_jdbc_source_expansion",
        "fabric_azure_blob_source_expansion",
        "fabric_private_azure_blob_source_expansion",
        "fabric_external_azure_blob_shortcut_source_expansion",
        "fabric_adls_shortcut_source_expansion",
        "fabric_gcs_shortcut_source_expansion",
        "fabric_external_s3_shortcut_source_expansion",
        "fabric_s3_compatible_shortcut_source_expansion",
        "fabric_iceberg_table_shortcut_source_expansion",
        "fabric_adls_iceberg_table_shortcut_source_expansion",
        "fabric_gcs_iceberg_table_shortcut_source_expansion",
        "fabric_confluent_kafka_bounded_source_expansion",
        "fabric_confluent_kafka_available_now_source_expansion",
        "fabric_eventhubs_kafka_available_now_source_expansion",
        "fabric_governance_review_evidence",
        "fabric_onelake_data_access_role_apply",
        "fabric_onelake_row_column_policy_apply",
        "fabric_project_deploy_only_promotion",
        "fabric_deployment_pipeline_read_probe",
        "fabric_deployment_pipeline_lifecycle",
        "fabric_deployment_pipeline_stage_promotion",
    }
    assert {gate["status"] for gate in payload["next_promotion_gates"] if "status" in gate} == set()
    gates = {gate["id"]: gate["status"] for gate in payload["gates"]}
    assert gates["F11"] == "PASS"
    assert gates["F12"] == "PASS"
    assert gates["F13"] == "PASS"
    assert {boundary["decision"] for boundary in payload["accepted_review_boundaries"]} == {
        "ACCEPTED_STABLE_SCOPE",
        "EXCLUDED_FROM_STABLE_FINAL",
    }


def test_fabric_cli_stabilization_report_strict_final_passes(capsys) -> None:
    rc = fabric_cli_module.main(["stabilization-report", "--strict-final"])

    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["stable_final"] is True
    assert payload["next_promotion_gates"] == []


def test_fabric_stabilization_report_is_public_api() -> None:
    payload = fabric_stabilization_report()

    assert payload["adapter"] == "contractforge-fabric"
    assert payload["stable_final"] is True
