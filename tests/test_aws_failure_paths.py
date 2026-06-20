"""Real-world AWS failure-path contracts."""

from __future__ import annotations

from pathlib import Path

import yaml

from contractforge_aws import plan_aws_contract, render_aws_contract
from contractforge_core.contracts import load_contract_bundle

PROJECT = Path("examples/real-world/aws-failure-paths")


def test_failure_path_project_declares_expected_failures() -> None:
    project = _load_yaml(PROJECT / "project.yaml")

    assert list(project["environments"]) == ["aws"]
    assert project["source_system"]["provider"] == "s3"
    assert [step["name"] for step in project["execution_order"]] == [
        "quality_abort_orders",
        "missing_s3_source",
    ]
    assert all(step["expected_result"] == "failed" for step in project["execution_order"])
    for step in project["execution_order"]:
        relative_path = step["contracts"]["aws"]
        assert (PROJECT / relative_path).exists()


def test_failure_path_bundles_load_annotations_and_operations() -> None:
    ingestion_files = sorted((PROJECT / "contracts/aws").glob("*/*.ingestion.yaml"))

    assert len(ingestion_files) == 2
    for path in ingestion_files:
        bundle = load_contract_bundle(path)
        assert bundle.semantic.target.name
        assert bundle.metadata["paths"]["ingestion"].endswith(".ingestion.yaml")
        assert "annotations" in bundle.contract
        assert "operations" in bundle.contract


def test_failure_path_contracts_plan_on_aws() -> None:
    for path in sorted((PROJECT / "contracts/aws").glob("*/*.ingestion.yaml")):
        result = plan_aws_contract(load_contract_bundle(path).contract)

        assert result.status in {"SUPPORTED", "SUPPORTED_WITH_WARNINGS"}


def test_quality_abort_contract_renders_failed_evidence_path() -> None:
    environment = _load_yaml(PROJECT / "environments/aws.environment.yaml")
    contract = load_contract_bundle(
        PROJECT / "contracts/aws/quality_abort_orders/quality_abort_orders.ingestion.yaml"
    ).contract

    artifacts = render_aws_contract(contract, environment=environment).artifacts
    job = next(body for name, body in artifacts.items() if name.endswith(".glue_job.py"))

    compile(job, "quality_abort_orders.glue_job.py", "exec")
    assert "raise ValueError('Data quality expression failed: impossible_amount_threshold')" in job
    assert "_cf_update_quality_status('FAILED')" in job
    assert "ctrl_ingestion_quality" in job
    assert "ctrl_ingestion_errors" in job
    assert "# Persist failed run evidence after error evidence is recorded." in job
    assert "'status': 'FAILED'" in job
    assert "'write_committed': False" in job
    assert "_cf_redact_error_text" in job


def test_missing_source_contract_renders_protected_failure_path() -> None:
    environment = _load_yaml(PROJECT / "environments/aws.environment.yaml")
    contract = load_contract_bundle(
        PROJECT / "contracts/aws/missing_s3_source/missing_s3_source.ingestion.yaml"
    ).contract

    artifacts = render_aws_contract(contract, environment=environment).artifacts
    job = next(body for name, body in artifacts.items() if name.endswith(".glue_job.py"))

    compile(job, "missing_s3_source.glue_job.py", "exec")
    assert "s3://contractforge-aws-smoke-449112696824-us-east-1/data/aws-failure-paths/missing/orders.csv" in job
    assert "ctrl_ingestion_errors" in job
    assert "# Persist failed run evidence after error evidence is recorded." in job
    assert "'status': 'FAILED'" in job
    assert "'write_committed': False" in job
    assert "_cf_redact_error_text" in job


def test_failure_path_environment_binds_artifacts_and_evidence() -> None:
    environment = _load_yaml(PROJECT / "environments/aws.environment.yaml")

    assert environment["evidence"]["database"] == "contractforge_cf_aws_failure_paths_ops"
    assert environment["artifacts"]["uri"].startswith("s3://contractforge-aws-smoke-449112696824-us-east-1/")
    assert (
        environment["parameters"]["aws"]["iceberg"]["warehouse"]
        == "s3://contractforge-aws-smoke-449112696824-us-east-1/warehouse/aws-failure-paths/"
    )


def _load_yaml(path: Path) -> dict:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload

