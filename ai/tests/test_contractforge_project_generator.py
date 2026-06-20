import json
from pathlib import Path

import yaml
import contractforge_ai

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10
    import tomli as tomllib

from contractforge_ai.generators.project import (
    generate_aws_glue_iceberg_project,
    generate_classic_pyspark_project,
    generate_contractforge_python_project,
    generate_contractforge_yaml_project,
    generate_databricks_dab_project,
    generate_dbt_project,
    generate_fabric_lakehouse_project,
    generate_gcp_bigquery_project,
    generate_project_for_target,
    generate_snowflake_sql_warehouse_project,
)
from contractforge_ai.generators.targets import project_target_spec_bindings
from contractforge_ai.project_structure import validate_project_structure
from contractforge_ai.validation import validate_project_plan_artifact


def test_top_level_exports_include_adapter_project_generators():
    assert contractforge_ai.generate_databricks_dab_project is generate_databricks_dab_project
    assert contractforge_ai.generate_aws_glue_iceberg_project is generate_aws_glue_iceberg_project
    assert contractforge_ai.generate_snowflake_sql_warehouse_project is generate_snowflake_sql_warehouse_project
    assert contractforge_ai.generate_fabric_lakehouse_project is generate_fabric_lakehouse_project
    assert contractforge_ai.generate_gcp_bigquery_project is generate_gcp_bigquery_project


def test_generate_contractforge_yaml_project_creates_reviewable_artifacts(tmp_path: Path):
    schema = tmp_path / "schema.json"
    schema.write_text(
        json.dumps(
            {
                "columns": [
                    {"name": "order_id", "type": "STRING", "nullable": False},
                    {"name": "customer_email", "type": "STRING", "nullable": True},
                    {"name": "amount", "type": "DOUBLE", "nullable": True},
                ]
            }
        ),
        encoding="utf-8",
    )

    plan = generate_contractforge_yaml_project(
        schema,
        project_name="Orders Example",
        connector="files",
        source_path="/Volumes/main/landing/orders",
        target_catalog="main",
        target_schema="bronze",
        target_table="b_orders",
        owner="data-engineering",
    )

    assert plan.name == "orders_example"
    assert plan.target == "contractforge-yaml"
    assert {artifact.path for artifact in plan.artifacts} == {
        "project.yaml",
        "environments/review.environment.yaml",
        "connections/source.yaml",
        "contracts/bronze/b_orders.ingestion.yaml",
        "contracts/bronze/b_orders.annotations.yaml",
        "contracts/bronze/b_orders.operations.yaml",
        "DECISIONS.md",
        "RUNBOOK.md",
        "VALIDATION.md",
        "README.md",
    }
    assert plan.report.decisions_required
    assert plan.traceability.review_required is True


def test_generated_ingestion_contract_excludes_split_contract_sections(tmp_path: Path):
    schema = tmp_path / "schema.json"
    schema.write_text(
        json.dumps({"columns": [{"name": "id", "type": "STRING", "nullable": False}]}),
        encoding="utf-8",
    )

    plan = generate_contractforge_yaml_project(
        schema,
        project_name="Customers",
        connector="files",
        source_path="/landing/customers",
        target_catalog="main",
        target_schema="silver",
        target_table="s_customers",
        layer="silver",
    )

    ingestion = next(artifact for artifact in plan.artifacts if artifact.path.endswith(".ingestion.yaml"))
    payload = yaml.safe_load(ingestion.content)

    assert payload["_metadata"]["draft"] is True
    assert payload["source"]["type"] == "connection"
    assert payload["source"]["connection_path"] == "project://connections/source.yaml"
    assert payload["source"]["path"] == "/landing/customers"
    assert payload["mode"] == "hash_diff_upsert"
    assert payload["merge_keys"] == ["id"]
    assert "annotations" not in payload
    assert "operations" not in payload


def test_generated_annotations_and_operations_are_separate_files(tmp_path: Path):
    schema = tmp_path / "schema.json"
    schema.write_text(
        json.dumps({"columns": [{"name": "customer_email", "type": "STRING", "nullable": True}]}),
        encoding="utf-8",
    )

    plan = generate_contractforge_yaml_project(
        schema,
        project_name="Customers",
        connector="files",
        source_path="/landing/customers",
        target_catalog="main",
        target_schema="bronze",
        target_table="b_customers",
    )

    annotations = yaml.safe_load(next(artifact.content for artifact in plan.artifacts if artifact.path.endswith(".annotations.yaml")))
    operations = yaml.safe_load(next(artifact.content for artifact in plan.artifacts if artifact.path.endswith(".operations.yaml")))

    assert annotations["_metadata"]["review_required"] is True
    assert annotations["columns"]["customer_email"]["pii"]["type"] == "email"
    assert operations["technical_owner"] == "REVIEW_REQUIRED"


def test_generate_databricks_dab_project_creates_bundle_artifacts(tmp_path: Path):
    schema = tmp_path / "schema.json"
    schema.write_text(
        json.dumps({"columns": [{"name": "order_id", "type": "STRING", "nullable": False}]}),
        encoding="utf-8",
    )

    plan = generate_databricks_dab_project(
        schema,
        project_name="Orders DAB",
        connector="files",
        source_path="/landing/orders",
        target_catalog="main",
        target_schema="bronze",
        target_table="b_orders",
    )

    paths = {artifact.path for artifact in plan.artifacts}
    assert plan.target == "databricks-dab"
    assert "databricks.yml" in paths
    assert "resources/jobs.yml" in paths
    assert "notebooks/run_bronze_b_orders.py" in paths
    assert "contracts/bronze/b_orders.ingestion.yaml" in paths
    assert "connections/source.yaml" in paths
    assert "environments/review.environment.yaml" in paths
    assert "DECISIONS.md" in paths
    assert "RUNBOOK.md" in paths
    assert "VALIDATION.md" in paths
    assert "README.md" in paths
    assert any(decision.path == "variables.existing_cluster_id" for decision in plan.report.decisions_required)


def test_generated_dab_files_use_placeholders_without_credentials(tmp_path: Path):
    schema = tmp_path / "schema.json"
    schema.write_text(
        json.dumps({"columns": [{"name": "id", "type": "STRING", "nullable": False}]}),
        encoding="utf-8",
    )

    plan = generate_databricks_dab_project(
        schema,
        project_name="Customers",
        connector="files",
        source_path="/landing/customers",
        target_catalog="main",
        target_schema="silver",
        target_table="s_customers",
        layer="silver",
    )

    databricks_yml = yaml.safe_load(next(artifact.content for artifact in plan.artifacts if artifact.path == "databricks.yml"))
    jobs_yml = yaml.safe_load(next(artifact.content for artifact in plan.artifacts if artifact.path == "resources/jobs.yml"))
    notebook = next(artifact.content for artifact in plan.artifacts if artifact.path.endswith(".py"))

    assert databricks_yml["bundle"]["name"] == "cf-silver-customers"
    assert databricks_yml["variables"]["existing_cluster_id"]["default"] == "REVIEW_REQUIRED"
    task = jobs_yml["resources"]["jobs"]["cf_silver_customers"]["tasks"][0]
    assert jobs_yml["resources"]["jobs"]["cf_silver_customers"]["name"] == "[${bundle.target}] cf_silver_customers"
    assert task["task_key"] == "cf_silver_customers"
    assert task["notebook_task"]["notebook_path"] == "./notebooks/run_silver_s_customers.py"
    assert task["existing_cluster_id"] == "${var.existing_cluster_id}"
    assert "secret" not in yaml.safe_dump(jobs_yml).lower()
    assert "from contractforge_databricks import ingest_databricks_bundle" in notebook
    assert "ingest_databricks_bundle(CONTRACT_PATH, spark=spark, runner=spark)" in notebook


def test_generated_dab_files_use_serverless_when_explicit(tmp_path: Path):
    schema = tmp_path / "schema.json"
    schema.write_text(
        json.dumps({"columns": [{"name": "id", "type": "STRING", "nullable": False}]}),
        encoding="utf-8",
    )

    plan = generate_databricks_dab_project(
        schema,
        project_name="Customers",
        connector="files",
        source_path="/landing/customers",
        target_catalog="main",
        target_schema="bronze",
        target_table="b_customers",
        compute={"type": "serverless"},
    )

    databricks_yml = yaml.safe_load(next(artifact.content for artifact in plan.artifacts if artifact.path == "databricks.yml"))
    jobs_yml = yaml.safe_load(next(artifact.content for artifact in plan.artifacts if artifact.path == "resources/jobs.yml"))
    job = jobs_yml["resources"]["jobs"]["cf_bronze_customers"]
    task = job["tasks"][0]

    assert "variables" not in databricks_yml
    assert task["environment_key"] == "default"
    assert "existing_cluster_id" not in task
    assert job["environments"][0]["environment_key"] == "default"
    assert not any(decision.path == "variables.existing_cluster_id" for decision in plan.report.decisions_required)


def test_generate_aws_glue_iceberg_project_creates_adapter_scaffold(tmp_path: Path):
    schema = tmp_path / "schema.json"
    schema.write_text(
        json.dumps({"columns": [{"name": "order_id", "type": "STRING", "nullable": False}]}),
        encoding="utf-8",
    )

    plan = generate_aws_glue_iceberg_project(
        schema,
        project_name="Orders AWS",
        connector="s3",
        source_path="s3://landing/orders",
        target_catalog="analytics",
        target_schema="bronze",
        target_table="b_orders",
    )

    paths = {artifact.path for artifact in plan.artifacts}
    assert plan.target == "aws-glue-iceberg"
    assert "project.yaml" in paths
    assert "environments/aws.environment.yaml" in paths
    assert "connections/source.yaml" in paths
    assert "contracts/aws/bronze/b_orders/b_orders.ingestion.yaml" in paths
    assert "contracts/aws/bronze/b_orders/b_orders.annotations.yaml" in paths
    assert "contracts/aws/bronze/b_orders/b_orders.operations.yaml" in paths
    assert "databricks.yml" not in paths
    assert "resources/jobs.yml" not in paths

    project = yaml.safe_load(next(artifact.content for artifact in plan.artifacts if artifact.path == "project.yaml"))
    environment = yaml.safe_load(next(artifact.content for artifact in plan.artifacts if artifact.path == "environments/aws.environment.yaml"))
    ingestion = yaml.safe_load(next(artifact.content for artifact in plan.artifacts if artifact.path.endswith(".ingestion.yaml")))
    readme = next(artifact.content for artifact in plan.artifacts if artifact.path == "README.md")

    assert project["environments"] == {"aws": "environments/aws.environment.yaml"}
    assert project["execution_order"][0]["contracts"]["aws"] == "contracts/aws/bronze/b_orders/b_orders.ingestion.yaml"
    assert environment["adapter"] == "aws"
    assert environment["runtime"]["runtime"] == "aws_glue_spark"
    assert environment["artifacts"]["uri"].startswith("s3://review-required-")
    assert environment["parameters"]["aws"]["iceberg"]["warehouse"].startswith("s3://review-required-")
    assert environment["parameters"]["aws"]["glue_job"]["role_arn"] == "REVIEW_REQUIRED"
    assert "job_bookmarks" not in environment["parameters"]["aws"]
    assert set(environment["parameters"]["aws"]["glue_job"]) == {"role_arn"}
    assert ingestion["source"]["type"] == "connection"
    assert ingestion["source"]["connection_path"] == "project://connections/source.yaml"
    assert "contractforge-aws deploy" in readme
    assert any(decision.path == "environments/aws.environment.yaml.artifacts.uri" for decision in plan.report.decisions_required)


def test_generated_aws_project_structure_validates_with_aws_adapter(tmp_path: Path):
    schema = tmp_path / "schema.json"
    schema.write_text(
        json.dumps({"columns": [{"name": "order_id", "type": "STRING", "nullable": False}]}),
        encoding="utf-8",
    )

    plan = generate_aws_glue_iceberg_project(
        schema,
        project_name="Orders AWS",
        connector="s3",
        source_path="s3://landing/orders",
        target_catalog="analytics",
        target_schema="bronze",
        target_table="b_orders",
    )
    for artifact in plan.artifacts:
        target = tmp_path / artifact.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(artifact.content, encoding="utf-8")

    result = validate_project_structure(tmp_path, adapters=("aws",))

    assert result.status in {"READY", "READY_WITH_WARNINGS", "NEEDS_DECISIONS"}
    assert all(finding.code != "project_structure.ingestion_bundle.invalid" for finding in result.findings)
    assert any(file.adapter == "aws" for file in result.files if file.kind == "ingestion_bundle")


def test_generate_cloud_adapter_projects_use_same_deterministic_contract_surface(tmp_path: Path):
    schema = tmp_path / "schema.json"
    schema.write_text(
        json.dumps({"columns": [{"name": "order_id", "type": "STRING", "nullable": False}]}),
        encoding="utf-8",
    )
    cases = [
        ("snowflake-sql-warehouse", "snowflake", "Snowflake SQL Warehouse"),
        ("fabric-lakehouse", "fabric", "Microsoft Fabric Lakehouse"),
        ("gcp-bigquery", "gcp", "GCP BigQuery"),
    ]

    for target, adapter, display_name in cases:
        plan = generate_project_for_target(
            target,
            schema,
            project_name=f"Orders {adapter}",
            connector="rest_api",
            source_path="https://example.com/orders.json",
            target_catalog="analytics",
            target_schema="bronze",
            target_table="b_orders",
        )

        paths = {artifact.path for artifact in plan.artifacts}
        contract_path = f"contracts/{adapter}/bronze/b_orders/b_orders.ingestion.yaml"

        assert plan.target == target
        assert "project.yaml" in paths
        assert f"environments/{adapter}.environment.yaml" in paths
        assert "connections/source.yaml" in paths
        assert contract_path in paths
        assert f"contracts/{adapter}/bronze/b_orders/b_orders.annotations.yaml" in paths
        assert f"contracts/{adapter}/bronze/b_orders/b_orders.operations.yaml" in paths

        project = yaml.safe_load(next(artifact.content for artifact in plan.artifacts if artifact.path == "project.yaml"))
        environment = yaml.safe_load(
            next(artifact.content for artifact in plan.artifacts if artifact.path == f"environments/{adapter}.environment.yaml")
        )
        ingestion = yaml.safe_load(next(artifact.content for artifact in plan.artifacts if artifact.path == contract_path))
        decisions = next(artifact.content for artifact in plan.artifacts if artifact.path == "DECISIONS.md")
        readme = next(artifact.content for artifact in plan.artifacts if artifact.path == "README.md")

        assert project["environments"] == {adapter: f"environments/{adapter}.environment.yaml"}
        assert project["execution_order"][0]["contracts"][adapter] == contract_path
        assert environment["adapter"] == adapter
        assert environment["parameters"][adapter]
        assert ingestion["source"]["type"] == "connection"
        assert ingestion["source"]["connection_path"] == "project://connections/source.yaml"
        assert ingestion["mode"] == "append"
        assert "REVIEW_REQUIRED" in yaml.safe_dump(environment)
        assert display_name in decisions
        assert "validate-project-structure . --adapter" in readme


def test_databricks_dab_target_binds_dab_compute_from_enriched_spec():
    bindings = project_target_spec_bindings("databricks-dab")

    assert [(binding.spec_field, binding.kwarg) for binding in bindings] == [("dab_compute", "compute")]


def test_generate_dbt_project_creates_source_model_and_tests(tmp_path: Path):
    schema = tmp_path / "schema.json"
    schema.write_text(
        json.dumps(
            {
                "columns": [
                    {"name": "order_id", "type": "STRING", "nullable": False},
                    {"name": "status", "type": "STRING", "nullable": True, "profile": {"distinct_values": ["open", "closed"]}},
                    {"name": "amount", "type": "DOUBLE", "nullable": True},
                ]
            }
        ),
        encoding="utf-8",
    )

    plan = generate_dbt_project(
        schema,
        project_name="Orders Analytics",
        connector="files",
        source_path="/landing/orders",
        target_catalog="main",
        target_schema="bronze",
        target_table="b_orders",
    )

    paths = {artifact.path for artifact in plan.artifacts}
    assert plan.target == "dbt"
    assert paths == {
        "dbt_project.yml",
        "models/sources.yml",
        "models/staging/stg_b_orders.sql",
        "models/staging/stg_b_orders.yml",
        "DECISIONS.md",
        "RUNBOOK.md",
        "VALIDATION.md",
        "README.md",
    }

    dbt_project = yaml.safe_load(next(artifact.content for artifact in plan.artifacts if artifact.path == "dbt_project.yml"))
    sources = yaml.safe_load(next(artifact.content for artifact in plan.artifacts if artifact.path == "models/sources.yml"))
    model_yml = yaml.safe_load(next(artifact.content for artifact in plan.artifacts if artifact.path.endswith("stg_b_orders.yml")))
    model_sql = next(artifact.content for artifact in plan.artifacts if artifact.path.endswith("stg_b_orders.sql"))

    assert dbt_project["profile"] == "REVIEW_REQUIRED"
    assert sources["sources"][0]["database"] == "main"
    assert sources["sources"][0]["schema"] == "bronze"
    assert sources["sources"][0]["tables"][0]["name"] == "b_orders"
    assert "{{ source('bronze_bronze', 'b_orders') }}" in model_sql
    tests_by_column = {column["name"]: column["data_tests"] for column in model_yml["models"][0]["columns"]}
    assert "not_null" in tests_by_column["order_id"]
    assert {"accepted_values": {"arguments": {"values": ["open", "closed"]}}} in tests_by_column["status"]
    assert plan.report.decisions_required


def test_generate_contractforge_python_project_creates_execution_wrapper_and_contracts(tmp_path: Path):
    schema = tmp_path / "schema.json"
    schema.write_text(
        json.dumps({"columns": [{"name": "order_id", "type": "STRING", "nullable": False}]}),
        encoding="utf-8",
    )

    plan = generate_contractforge_python_project(
        schema,
        project_name="Orders Python",
        connector="files",
        source_path="/landing/orders",
        target_catalog="main",
        target_schema="bronze",
        target_table="b_orders",
    )

    paths = {artifact.path for artifact in plan.artifacts}
    assert plan.target == "contractforge-python"
    assert "pyproject.toml" in paths
    assert "src/orders_python/config.py" in paths
    assert "src/orders_python/run_ingestion.py" in paths
    assert "notebooks/run_bronze_b_orders.py" in paths
    assert "contracts/bronze/b_orders.ingestion.yaml" in paths
    assert "contracts/bronze/b_orders.annotations.yaml" in paths
    assert "contracts/bronze/b_orders.operations.yaml" in paths
    assert "connections/source.yaml" in paths
    assert "environments/review.environment.yaml" in paths
    assert "RUNBOOK.md" in paths
    assert "VALIDATION.md" in paths

    runner = next(artifact.content for artifact in plan.artifacts if artifact.path.endswith("run_ingestion.py"))
    pyproject = next(artifact.content for artifact in plan.artifacts if artifact.path == "pyproject.toml")
    readme = next(artifact.content for artifact in plan.artifacts if artifact.path == "README.md")
    notebook = next(artifact.content for artifact in plan.artifacts if artifact.path == "notebooks/run_bronze_b_orders.py")

    assert "from contractforge_core.contracts import load_contract_bundle, semantic_contract_from_mapping" in runner
    assert "from contractforge_databricks import ingest_databricks_bundle" in runner
    assert "from contractforge_aws.api import plan_aws_contract" in runner
    assert "ACTIONS: dict[str, Action]" in runner
    assert '"plan-aws": plan_aws' in runner
    assert "if adapter ==" not in runner
    assert "DEFAULT_CONTRACT_PATH" in runner
    assert 'parser.add_argument("--action"' in runner
    assert 'result = run(action="run-databricks")' in notebook
    assert "contractforge-core" in pyproject
    assert "contractforge-databricks" in pyproject
    assert "contractforge-aws" in pyproject
    assert "orders-python-ingest --action plan-aws" in readme
    assert "orders_python-ingest" not in readme
    assert 'orders-python-ingest = "orders_python.run_ingestion:main"' in pyproject
    assert tomllib.loads(pyproject)["project"]["scripts"]["orders-python-ingest"] == "orders_python.run_ingestion:main"
    assert any(decision.path == "pyproject.toml.project.dependencies" for decision in plan.report.decisions_required)


def test_project_generation_uses_contractforge_naming_overrides(tmp_path: Path):
    schema = tmp_path / "schema.json"
    schema.write_text(
        json.dumps({"columns": [{"name": "order_id", "type": "STRING", "nullable": False}]}),
        encoding="utf-8",
    )

    naming = {
        "policy": "caf_default",
        "logical_name": "orders_platform",
        "contract_basename": "orders_contract",
        "bundle_name": "orders-bundle",
        "job_name": "Orders Ingestion",
        "task_key": "orders_ingestion_task",
    }

    plan = generate_databricks_dab_project(
        schema,
        project_name="Orders",
        connector="files",
        source_path="/landing/orders",
        target_catalog="main",
        target_schema="bronze",
        target_table="b_orders",
        naming=naming,
    )

    paths = {artifact.path for artifact in plan.artifacts}
    assert plan.name == "orders-bundle"
    assert "contracts/bronze/orders_contract.ingestion.yaml" in paths
    assert "notebooks/run_bronze_orders_contract.py" in paths

    ingestion = yaml.safe_load(
        next(artifact.content for artifact in plan.artifacts if artifact.path == "contracts/bronze/orders_contract.ingestion.yaml")
    )
    databricks_yml = yaml.safe_load(next(artifact.content for artifact in plan.artifacts if artifact.path == "databricks.yml"))
    jobs_yml = yaml.safe_load(next(artifact.content for artifact in plan.artifacts if artifact.path == "resources/jobs.yml"))

    assert ingestion["target"]["table"] == "b_orders"
    assert ingestion["naming"]["logical_name"] == "orders_platform"
    assert databricks_yml["bundle"]["name"] == "orders-bundle"
    job = jobs_yml["resources"]["jobs"]["orders_ingestion"]
    assert job["name"] == "[${bundle.target}] Orders Ingestion"
    assert job["tasks"][0]["task_key"] == "orders_ingestion_task"


def test_generate_classic_pyspark_project_creates_comparison_artifacts(tmp_path: Path):
    schema = tmp_path / "schema.json"
    schema.write_text(
        json.dumps({"columns": [{"name": "order_id", "type": "STRING", "nullable": False}]}),
        encoding="utf-8",
    )

    plan = generate_classic_pyspark_project(
        schema,
        project_name="Orders Classic",
        connector="files",
        source_path="/landing/orders",
        target_catalog="main",
        target_schema="bronze",
        target_table="b_orders",
    )

    paths = {artifact.path for artifact in plan.artifacts}
    assert plan.target == "classic-pyspark"
    assert "classic_pyspark/run_bronze_b_orders.py" in paths
    assert "notebooks/classic_run_bronze_b_orders.py" in paths
    assert "contracts/bronze/b_orders.ingestion.yaml" in paths
    assert "connections/source.yaml" in paths
    assert "MIGRATION.md" in paths
    assert "DECISIONS.md" in paths
    assert "RUNBOOK.md" in paths
    assert "VALIDATION.md" in paths
    assert "README.md" in paths

    script = next(artifact.content for artifact in plan.artifacts if artifact.path == "classic_pyspark/run_bronze_b_orders.py")
    migration = next(artifact.content for artifact in plan.artifacts if artifact.path == "MIGRATION.md")

    assert "spark.read.format(\"REVIEW_REQUIRED\")" in script
    assert "Use the generated ContractForge contract as the production reference" in script
    assert "not attempt to recreate all ContractForge behavior" in migration
    assert any(decision.path == "classic_pyspark/run_bronze_b_orders.py" for decision in plan.report.decisions_required)


def test_generated_project_runbooks_include_operational_sections(tmp_path: Path):
    schema = tmp_path / "schema.json"
    schema.write_text(
        json.dumps({"columns": [{"name": "order_id", "type": "STRING", "nullable": False}]}),
        encoding="utf-8",
    )

    plans = [
        generate_contractforge_yaml_project(
            schema,
            project_name="Orders YAML",
            connector="files",
            source_path="/landing/orders",
            target_catalog="main",
            target_schema="bronze",
            target_table="b_orders",
        ),
        generate_databricks_dab_project(
            schema,
            project_name="Orders DAB",
            connector="files",
            source_path="/landing/orders",
            target_catalog="main",
            target_schema="bronze",
            target_table="b_orders",
        ),
        generate_dbt_project(
            schema,
            project_name="Orders dbt",
            connector="files",
            source_path="/landing/orders",
            target_catalog="main",
            target_schema="bronze",
            target_table="b_orders",
        ),
        generate_contractforge_python_project(
            schema,
            project_name="Orders Python",
            connector="files",
            source_path="/landing/orders",
            target_catalog="main",
            target_schema="bronze",
            target_table="b_orders",
        ),
        generate_classic_pyspark_project(
            schema,
            project_name="Orders Classic",
            connector="files",
            source_path="/landing/orders",
            target_catalog="main",
            target_schema="bronze",
            target_table="b_orders",
        ),
    ]

    for plan in plans:
        runbook = next(artifact.content for artifact in plan.artifacts if artifact.path == "RUNBOOK.md")
        assert "## Pre-Run Checklist" in runbook
        assert "## Validation Commands" in runbook
        assert "## Operational Review" in runbook
        assert "## Incident Notes" in runbook


def test_generated_project_validation_artifacts_include_contractforge_adapter_result(tmp_path: Path):
    schema = tmp_path / "schema.json"
    schema.write_text(
        json.dumps({"columns": [{"name": "order_id", "type": "STRING", "nullable": False}]}),
        encoding="utf-8",
    )

    plan = generate_contractforge_yaml_project(
        schema,
        project_name="Orders YAML",
        connector="files",
        source_path="/landing/orders",
        target_catalog="main",
        target_schema="bronze",
        target_table="b_orders",
    )

    validation = next(artifact.content for artifact in plan.artifacts if artifact.path == "VALIDATION.md")

    assert "## Deterministic Generated-Artifact Validation" in validation
    assert "## ContractForge Validation" in validation
    assert "ContractForge" in validation


def test_generated_contractforge_yaml_project_plan_validation_resolves_connection(tmp_path: Path):
    schema = tmp_path / "schema.json"
    schema.write_text(
        json.dumps({"columns": [{"name": "order_id", "type": "STRING", "nullable": False}]}),
        encoding="utf-8",
    )

    plan = generate_contractforge_yaml_project(
        schema,
        project_name="Orders YAML",
        connector="files",
        source_path="/landing/orders",
        target_catalog="main",
        target_schema="bronze",
        target_table="b_orders",
    )

    result = validate_project_plan_artifact(plan)

    assert all(
        finding.code != "contractforge.validation.contract_rejected"
        for check in result.checks
        for finding in check.findings
    )
