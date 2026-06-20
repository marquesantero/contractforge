import json
from pathlib import Path

from contractforge_ai.cli import main
from contractforge_ai.explainers.failure import explain_failure


def test_explain_failure_classifies_dns_and_egress():
    explanation = explain_failure(
        {
            "run": {
                "run_id": "run-1",
                "status": "FAILED",
                "target_table": "main.bronze.orders",
                "source_connector": "http_file",
                "runtime_type": "serverless",
                "error_message": "urllib.error.URLError: <urlopen error [Errno -3] Temporary failure in name resolution>",
            }
        }
    )

    assert explanation.status == "EXPLAINED"
    assert explanation.primary_category == "network_or_egress"
    assert explanation.risk == "high"
    assert explanation.evidence["run_id"] == "run-1"
    assert explanation.traceability.confidence_level == "high"
    assert explanation.findings[0].evidence


def test_explain_failure_classifies_storage_access_and_redacts_secret():
    explanation = explain_failure(
        {
            "run": {
                "run_id": "run-2",
                "status": "FAILED",
                "source_connector": "azure_blob",
                "error_message": "AuthorizationPermissionMismatch: This request is not authorized, 403, abfss path",
                "source_auth": {"sas_token": "{{ secret:scope/blob_sas_token }}"},
            },
            "errors": [
                {
                    "stack_trace": "PERMISSION_DENIED: Service Principal does not have WRITE, DELETE permissions "
                    "on cloud storage external location"
                }
            ],
        }
    )

    assert explanation.status == "EXPLAINED"
    assert explanation.primary_category in {"authentication_or_authorization", "storage_access"}
    assert any(finding.code == "failure.storage_access" for finding in explanation.findings)
    assert "[REDACTED" not in json.dumps(explanation.to_dict())


def test_explain_failure_classifies_missing_dependency():
    explanation = explain_failure(
        {
            "run": {
                "run_id": "run-3",
                "status": "FAILED",
                "source_connector": "jdbc",
            },
            "errors": [{"error_message": "java.lang.ClassNotFoundException: org.postgresql.Driver"}],
        }
    )

    assert explanation.primary_category == "dependency_or_driver"
    assert explanation.recommended_actions


def test_explain_failure_returns_unknown_when_no_pattern_matches():
    explanation = explain_failure({"run": {"run_id": "run-4", "status": "FAILED", "error_message": "Unexpected"}})

    assert explanation.status == "UNKNOWN"
    assert explanation.primary_category == "unknown"
    assert explanation.recommended_actions
    assert explanation.traceability.review_required is True
    assert explanation.traceability.confidence == 0.0


def test_explain_run_cli_json_output(tmp_path: Path, capsys):
    payload = tmp_path / "failure.json"
    payload.write_text(
        json.dumps(
            {
                "run": {
                    "run_id": "run-5",
                    "status": "FAILED",
                    "error_message": "Library installation failed: ModuleNotFoundError: No module named paramiko",
                }
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(["explain-run", "--input", str(payload), "--format", "json"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"status": "EXPLAINED"' in output
    assert "dependency_or_driver" in output


def test_explain_run_cli_collects_databricks_evidence(monkeypatch, capsys):
    def fake_collect_databricks_run_evidence(*, run_id, catalog, ctrl_schema, limit):
        assert run_id == "run-6"
        assert catalog == "main"
        assert ctrl_schema == "ops"
        assert limit == 10
        return {
            "run": {
                "run_id": run_id,
                "status": "FAILED",
                "error_message": "Permission denied on storage credential",
                "source_connector": "azure_blob",
            }
        }

    monkeypatch.setattr("contractforge_ai.cli.collect_databricks_run_evidence", fake_collect_databricks_run_evidence)

    exit_code = main(
        [
            "explain-run",
            "--run-id",
            "run-6",
            "--catalog",
            "main",
            "--ctrl-schema",
            "ops",
            "--limit",
            "10",
            "--format",
            "json",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"status": "EXPLAINED"' in output
    assert "storage_access" in output

