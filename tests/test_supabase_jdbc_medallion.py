"""Real-world Supabase/PostgreSQL JDBC medallion contracts for Databricks and AWS."""

from __future__ import annotations

from pathlib import Path

import yaml

from contractforge_aws import plan_aws_contract, render_aws_contract
from contractforge_databricks import plan_databricks_contract, render_databricks_contract, render_databricks_project_bundle
from contractforge_core.contracts import load_contract_bundle

PROJECT = Path("examples/real-world/supabase-jdbc-medallion")


def test_supabase_jdbc_project_declares_parallel_platform_contracts() -> None:
    project = _load_yaml(PROJECT / "project.yaml")

    assert list(project["environments"]) == ["databricks", "aws"]
    assert project["source_system"]["seed_schema"] == "cf_supabase_newcore_demo"
    assert [step["name"] for step in project["execution_order"]] == [
        "bronze_supabase_products",
        "bronze_supabase_movements",
        "silver_supabase_product_tags",
        "silver_supabase_movements_current",
        "gold_supabase_brand_inventory",
    ]
    for step in project["execution_order"]:
        for platform, relative_path in step["contracts"].items():
            assert platform in {"databricks", "aws"}
            assert (PROJECT / relative_path).exists()
    assert project["schedule"]["adapters"]["databricks"]["pause_status"] == "PAUSED"
    assert project["execution_order"][0]["depends_on"] == ["verify_supabase_source"]
    assert project["execution_order"][1]["depends_on"] == ["bronze_supabase_products"]


def test_supabase_jdbc_bundles_resolve_project_connection_yaml() -> None:
    ingestion_files = sorted((PROJECT / "contracts").glob("*/*/*/*.ingestion.yaml"))

    assert len(ingestion_files) == 10
    for path in ingestion_files:
        bundle = load_contract_bundle(path)
        assert bundle.semantic.target.name
        assert "annotations" in bundle.contract
        assert "operations" in bundle.contract
        source = bundle.contract["source"]
        if path.name.startswith("bronze_supabase_"):
            assert source["type"] == "connector"
            assert source["connector"] == "postgres"
            assert source["connection"] == "project://connections/supabase.yaml"
            assert source["url"] == "{{ secret:contractforge-secrets/supabase-jdbc-url }}"


def test_supabase_jdbc_contracts_plan_on_databricks_and_aws() -> None:
    for path in sorted((PROJECT / "contracts/databricks").glob("*/*/*.ingestion.yaml")):
        result = plan_databricks_contract(
            load_contract_bundle(path).contract,
            runtime_type="serverless",
            spark_conf={"spark.databricks.serverless.enabled": "true"},
        )
        assert result.status in {"SUPPORTED", "SUPPORTED_WITH_WARNINGS"}
    for path in sorted((PROJECT / "contracts/aws").glob("*/*/*.ingestion.yaml")):
        result = plan_aws_contract(load_contract_bundle(path).contract)
        assert result.status in {"SUPPORTED", "SUPPORTED_WITH_WARNINGS"}


def test_supabase_jdbc_contracts_render_runtime_artifacts() -> None:
    databricks_contract = load_contract_bundle(
        PROJECT / "contracts/databricks/bronze/bronze_supabase_products/bronze_supabase_products.ingestion.yaml"
    ).contract
    aws_contract = load_contract_bundle(
        PROJECT / "contracts/aws/bronze/bronze_supabase_products/bronze_supabase_products.ingestion.yaml"
    ).contract
    aws_environment = _load_yaml(PROJECT / "environments/aws.environment.yaml")

    dbx_artifacts = render_databricks_contract(databricks_contract, runtime_type="serverless").artifacts
    aws_artifacts = render_aws_contract(aws_contract, environment=aws_environment).artifacts

    assert any(name.endswith(".source_jdbc.py") for name in dbx_artifacts)
    assert any(name.endswith(".databricks.yml") for name in dbx_artifacts)
    aws_job = next(body for name, body in aws_artifacts.items() if name.endswith(".glue_job.py"))
    aws_iam = next(body for name, body in aws_artifacts.items() if name.endswith(".iam_policy.json"))
    assert "spark.read" in aws_job
    assert "_cf_resolve_secret" in aws_job
    assert "s3://replace-with-artifact-bucket" not in aws_job
    assert "s3://contractforge-aws-smoke-000000000000-us-east-1/warehouse/supabase-jdbc-v2/" in aws_job
    assert "arn:aws:s3:::contractforge-aws-smoke-000000000000-us-east-1/contractforge-supabase-jdbc-v2/*" in aws_iam
    assert "arn:aws:s3:::contractforge-aws-smoke-000000000000-us-east-1/artifacts/contractforge/libs/contractforge_core-0.1.0-py3-none-any.whl" in aws_iam
    assert "arn:aws:s3:::contractforge-aws-smoke-000000000000-us-east-1/artifacts/contractforge/libs/contractforge_aws-0.1.0-py3-none-any.whl" in aws_iam


def test_supabase_jdbc_logical_table_refs_render_to_platform_qualified_names() -> None:
    databricks_contract = load_contract_bundle(
        PROJECT / "contracts/databricks/silver/silver_supabase_product_tags/silver_supabase_product_tags.ingestion.yaml"
    ).contract
    aws_contract = load_contract_bundle(
        PROJECT / "contracts/aws/gold/gold_supabase_brand_inventory/gold_supabase_brand_inventory.ingestion.yaml"
    ).contract
    aws_environment = _load_yaml(PROJECT / "environments/aws.environment.yaml")

    dbx_artifacts = render_databricks_contract(databricks_contract, runtime_type="serverless").artifacts
    aws_artifacts = render_aws_contract(aws_contract, environment=aws_environment).artifacts

    dbx_source = next(body for name, body in dbx_artifacts.items() if name.endswith(".source_catalog.py"))
    aws_job = next(body for name, body in aws_artifacts.items() if name.endswith(".glue_job.py"))
    assert "workspace.cf_supabase_jdbc_e2e_v2_bronze.b_products_jdbc" in dbx_source
    assert "glue_catalog.contractforge_cf_supabase_jdbc_e2e_v2_silver.s_product_tags" in aws_job
    assert "glue_catalog.contractforge_cf_supabase_jdbc_e2e_v2_silver.s_movements_current" in aws_job
    assert "{{ table_ref:" not in dbx_source
    assert "{{ table_ref:" not in aws_job


def test_supabase_jdbc_dab_project_is_declared() -> None:
    dab = _load_yaml(PROJECT / "databricks.yml")
    tasks = dab["resources"]["jobs"]["supabase_jdbc_medallion"]["tasks"]

    assert dab["bundle"]["name"] == "contractforge_supabase_jdbc_medallion"
    assert [task["task_key"] for task in tasks] == [
        "verify_supabase_source",
        "bronze_products",
        "bronze_movements",
        "silver_product_tags",
        "silver_movements_current",
        "gold_brand_inventory",
        "validate_results",
    ]
    assert tasks[-1]["notebook_task"]["notebook_path"] == "./notebooks/validate_results.py"


def test_supabase_jdbc_project_can_render_databricks_bundle_from_schedule_metadata() -> None:
    project = _load_yaml(PROJECT / "project.yaml")
    rendered = render_databricks_project_bundle(project)
    job = rendered["resources"]["jobs"]["supabase_jdbc_medallion"]
    tasks = job["tasks"]

    assert job["name"] == "contractforge_supabase_jdbc_medallion"
    assert job["schedule"]["pause_status"] == "PAUSED"
    assert job["queue"] == {"enabled": True}
    assert [task["task_key"] for task in tasks] == [
        "verify_supabase_source",
        "bronze_products",
        "bronze_movements",
        "silver_product_tags",
        "silver_movements_current",
        "gold_brand_inventory",
        "validate_results",
    ]
    assert tasks[1]["depends_on"] == [{"task_key": "verify_supabase_source"}]
    assert tasks[-2]["notebook_task"]["base_parameters"]["contract"].endswith(
        "contracts/databricks/gold/gold_supabase_brand_inventory/gold_supabase_brand_inventory.ingestion.yaml"
    )
    assert tasks[-1]["depends_on"] == [{"task_key": "gold_brand_inventory"}]
    assert tasks[-1]["notebook_task"]["notebook_path"] == "./notebooks/validate_results.py"


def _load_yaml(path: Path) -> dict:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload
