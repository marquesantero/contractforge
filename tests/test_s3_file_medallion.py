"""Real-world AWS S3 file medallion contracts."""

from __future__ import annotations

from pathlib import Path

import yaml

from contractforge_aws import plan_aws_contract, render_aws_contract
from contractforge_core.contracts import load_contract_bundle

PROJECT = Path("examples/real-world/s3-file-medallion")


def test_s3_file_project_declares_aws_execution_order() -> None:
    project = _load_yaml(PROJECT / "project.yaml")

    assert list(project["environments"]) == ["aws"]
    assert project["source_system"]["provider"] == "s3"
    assert [step["name"] for step in project["execution_order"]] == [
        "bronze_s3_orders_files",
        "silver_s3_orders_daily",
        "gold_s3_revenue_by_status",
    ]
    for step in project["execution_order"]:
        relative_path = step["contracts"]["aws"]
        assert (PROJECT / relative_path).exists()


def test_s3_file_bundles_load_annotations_and_operations() -> None:
    ingestion_files = sorted((PROJECT / "contracts/aws").glob("*/*/*.ingestion.yaml"))

    assert len(ingestion_files) == 3
    for path in ingestion_files:
        bundle = load_contract_bundle(path)
        assert bundle.semantic.target.name
        assert bundle.metadata["paths"]["ingestion"].endswith(".ingestion.yaml")
        assert "annotations" in bundle.contract
        assert "operations" in bundle.contract


def test_s3_file_contracts_plan_on_aws() -> None:
    for path in sorted((PROJECT / "contracts/aws").glob("*/*/*.ingestion.yaml")):
        result = plan_aws_contract(load_contract_bundle(path).contract)

        assert result.status in {"SUPPORTED", "SUPPORTED_WITH_WARNINGS"}


def test_s3_file_contracts_render_runtime_artifacts() -> None:
    environment = _load_yaml(PROJECT / "environments/aws.environment.yaml")
    bronze = load_contract_bundle(
        PROJECT / "contracts/aws/bronze/bronze_s3_orders_files/bronze_s3_orders_files.ingestion.yaml"
    ).contract
    silver = load_contract_bundle(
        PROJECT / "contracts/aws/silver/silver_s3_orders_daily/silver_s3_orders_daily.ingestion.yaml"
    ).contract
    gold = load_contract_bundle(
        PROJECT / "contracts/aws/gold/gold_s3_revenue_by_status/gold_s3_revenue_by_status.ingestion.yaml"
    ).contract

    bronze_artifacts = render_aws_contract(bronze, environment=environment).artifacts
    silver_artifacts = render_aws_contract(silver, environment=environment).artifacts
    gold_artifacts = render_aws_contract(gold, environment=environment).artifacts

    bronze_job = next(body for name, body in bronze_artifacts.items() if name.endswith(".glue_job.py"))
    silver_job = next(body for name, body in silver_artifacts.items() if name.endswith(".glue_job.py"))
    gold_job = next(body for name, body in gold_artifacts.items() if name.endswith(".glue_job.py"))
    bronze_definition = next(body for name, body in bronze_artifacts.items() if name.endswith(".glue_job_definition.json"))
    bronze_iam = next(body for name, body in bronze_artifacts.items() if name.endswith(".iam_policy.json"))

    assert "create_dynamic_frame.from_options" in bronze_job
    assert "transformation_ctx='cf_incremental_files'" in bronze_job
    assert "job-bookmark-enable" in bronze_definition
    assert "contractforge_cf_s3_file_e2e_bronze.b_orders_files" in silver_job
    assert "contractforge_cf_s3_file_e2e_silver.s_orders_daily" in gold_job
    assert "s3://contractforge-aws-smoke-000000000000-us-east-1/warehouse/s3-file-e2e/" in bronze_job
    assert "arn:aws:s3:::contractforge-aws-smoke-000000000000-us-east-1/contractforge-s3-file-e2e/*" in bronze_iam
    assert "arn:aws:s3:::contractforge-aws-smoke-000000000000-us-east-1/artifacts/contractforge/libs/contractforge_core-0.1.0-py3-none-any.whl" in bronze_iam
    assert "arn:aws:s3:::contractforge-aws-smoke-000000000000-us-east-1/artifacts/contractforge/libs/contractforge_aws-0.1.0-py3-none-any.whl" in bronze_iam
    assert any(name.endswith(".deployment_manifest.json") for name in bronze_artifacts)


def test_s3_file_seed_data_is_present() -> None:
    data_files = sorted((PROJECT / "data/orders").glob("*.csv"))

    assert [path.name for path in data_files] == ["orders_incremental.csv", "orders_initial.csv"]
    assert all("order_id,customer_id,order_ts,order_status,amount,updated_at" in path.read_text() for path in data_files)


def _load_yaml(path: Path) -> dict:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload
