import json

import pytest

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_aws import (
    AWSAdapter,
    AWSEnvironment,
    render_aws_contract,
    render_aws_annotations_evidence_sql,
    render_aws_deployment_manifest,
    render_aws_glue_job_cloudformation,
    render_aws_glue_job_definition,
    render_aws_glue_job_iam_policy,
    render_aws_glue_job_terraform,
    render_aws_lake_formation_evidence_sql,
    render_aws_operational_cost_query,
    render_aws_operations_evidence_sql,
)


def _contract() -> dict:
    return {
        "source": {"type": "parquet", "path": "s3://landing/orders"},
        "target": {"catalog": "lake", "schema": "bronze", "table": "orders"},
        "mode": "scd0_append",
    }


def test_aws_environment_from_core_contract() -> None:
    environment = AWSEnvironment.from_contract(
        {
            "environment": {
                "name": "prod",
                "adapter": "aws",
                "evidence": {"database": "cf_ops_prod"},
                "parameters": {"aws": {"glue.default_worker_type": "G.1X"}},
            }
        }
    )

    assert environment.name == "prod"
    assert environment.evidence_database == "cf_ops_prod"
    assert environment.parameters == {"glue.default_worker_type": "G.1X"}


def test_aws_environment_accepts_schema_alias_for_evidence_database() -> None:
    environment = AWSEnvironment.from_contract({"name": "prod", "adapter": "aws", "evidence": {"schema": "ops"}})

    assert environment.evidence_database == "ops"


def test_aws_environment_accepts_s3_artifact_uri() -> None:
    environment = AWSEnvironment.from_contract(
        {
            "name": "prod",
            "adapter": "aws",
            "artifacts": {
                "uri": "s3://contractforge-artifacts/prod/orders/",
                "include_contract_bundle": True,
            },
        }
    )

    assert environment.artifact_uri == "s3://contractforge-artifacts/prod/orders/"
    assert environment.artifact_options == {
        "uri": "s3://contractforge-artifacts/prod/orders/",
        "include_contract_bundle": True,
    }


def test_aws_environment_rejects_non_s3_artifact_uri() -> None:
    with pytest.raises(ValueError, match="environment.artifacts.uri"):
        AWSEnvironment.from_contract({"name": "prod", "adapter": "aws", "artifacts": {"uri": "dbfs:/artifacts"}})


def test_aws_environment_rejects_wrong_adapter() -> None:
    with pytest.raises(ValueError, match="environment.adapter='aws'"):
        AWSEnvironment.from_contract({"name": "prod", "adapter": "databricks"})


def test_aws_rendering_uses_environment_evidence_database() -> None:
    artifacts = render_aws_contract(
        _contract(),
        environment={"name": "prod", "adapter": "aws", "evidence": {"database": "cf_ops_prod"}},
    ).artifacts

    assert "CREATE DATABASE IF NOT EXISTS glue_catalog.`cf_ops_prod`" in artifacts["lake_bronze_orders.evidence_ddl.sql"]
    assert "FROM glue_catalog.`cf_ops_prod`.`ctrl_ingestion_runs`" in artifacts["lake_bronze_orders.cost.sql"]
    assert "glue_catalog.`cf_ops_prod`" in artifacts["lake_bronze_orders.glue_job.py"]
    assert "lake_bronze_ops" not in artifacts["lake_bronze_orders.glue_job.py"]
    assert "database/cf_ops_prod" in artifacts["lake_bronze_orders.iam_policy.json"]
    assert "lake_bronze_ops" not in artifacts["lake_bronze_orders.terraform.tf"]
    cloudformation = json.loads(artifacts["lake_bronze_orders.cloudformation.json"])
    assert cloudformation["Outputs"]["EvidenceDatabaseName"]["Value"] == "cf_ops_prod"
    manifest = artifacts["lake_bronze_orders.deployment_manifest.json"]
    assert '"evidence_database": "cf_ops_prod"' in manifest


def test_aws_deployment_manifest_accepts_environment() -> None:
    manifest = render_aws_deployment_manifest(
        _contract(),
        environment={"name": "prod", "adapter": "aws", "evidence": {"database": "cf_ops_prod"}},
    )

    assert '"evidence_database": "cf_ops_prod"' in manifest


def test_aws_public_deployment_helpers_accept_environment() -> None:
    environment = {"name": "prod", "adapter": "aws", "evidence": {"database": "cf_ops_prod"}}

    iam = render_aws_glue_job_iam_policy(_contract(), environment=environment)
    cloudformation = json.loads(render_aws_glue_job_cloudformation(_contract(), environment=environment))
    terraform = render_aws_glue_job_terraform(_contract(), environment=environment)

    assert "database/cf_ops_prod" in iam
    assert cloudformation["Outputs"]["EvidenceDatabaseName"]["Value"] == "cf_ops_prod"
    assert 'name = "cf_ops_prod"' in terraform


def test_aws_environment_parameters_feed_deployment_defaults() -> None:
    environment = {
        "name": "prod",
        "adapter": "aws",
        "parameters": {
            "aws": {
                "glue_job": {
                    "role_arn": "arn:aws:iam::123456789012:role/ContractForgeGlueRole",
                    "worker_type": "G.2X",
                    "number_of_workers": 5,
                    "default_arguments": {"--TempDir": "s3://artifacts/tmp/"},
                },
                "dependencies": {"python_modules": ["contractforge-core", "requests"]},
            }
        },
    }

    artifacts = render_aws_contract(_contract(), environment=environment).artifacts
    payload = json.loads(artifacts["lake_bronze_orders.glue_job_definition.json"])

    assert payload["Role"] == "arn:aws:iam::123456789012:role/ContractForgeGlueRole"
    assert payload["WorkerType"] == "G.2X"
    assert payload["NumberOfWorkers"] == 5
    assert payload["DefaultArguments"]["--TempDir"] == "s3://artifacts/tmp/"
    assert payload["DefaultArguments"]["--additional-python-modules"] == "contractforge-core,requests"
    assert 'worker_type       = "G.2X"' in artifacts["lake_bronze_orders.terraform.tf"]


def test_aws_environment_parameters_feed_glue_iceberg_warehouse() -> None:
    environment = {
        "name": "prod",
        "adapter": "aws",
        "parameters": {"aws": {"iceberg": {"warehouse": "s3://contractforge-warehouse/prod/"}}},
    }

    artifacts = render_aws_contract(_contract(), environment=environment).artifacts

    assert "spark.sql.catalog.glue_catalog.warehouse" in artifacts["lake_bronze_orders.glue_job.py"]
    assert "s3://contractforge-warehouse/prod/" in artifacts["lake_bronze_orders.glue_job.py"]
    assert (
        "CREATE DATABASE IF NOT EXISTS glue_catalog.`lake_bronze` LOCATION "
        "'s3://contractforge-warehouse/prod/lake_bronze.db/'"
    ) in artifacts["lake_bronze_orders.glue_job.py"]


def test_aws_rendering_rejects_unresolved_iceberg_warehouse_placeholder() -> None:
    contract = {
        **_contract(),
        "extensions": {
            "aws": {"iceberg": {"warehouse": "s3://replace-with-artifact-bucket/contractforge/warehouse/"}}
        },
    }

    with pytest.raises(ValueError, match="unresolved placeholder"):
        render_aws_contract(contract)


def test_aws_contract_extensions_override_environment_parameters() -> None:
    contract = {
        **_contract(),
        "extensions": {"aws": {"glue_job": {"worker_type": "G.4X", "number_of_workers": 7}}},
    }
    environment = {
        "name": "prod",
        "adapter": "aws",
        "parameters": {"aws": {"glue_job": {"worker_type": "G.2X", "number_of_workers": 5}}},
    }

    payload = json.loads(render_aws_glue_job_definition(contract, environment=environment))

    assert payload["WorkerType"] == "G.4X"
    assert payload["NumberOfWorkers"] == 7


def test_aws_public_evidence_helpers_accept_environment() -> None:
    contract = {
        **_contract(),
        "annotations": {"table": {"description": "Orders"}},
        "access": {"grants": [{"principal": "analyst", "privileges": ["SELECT"]}]},
        "operations": {"criticality": "high", "ownership": {"technical_owner": "platform"}},
    }
    environment = {"name": "prod", "adapter": "aws", "evidence": {"database": "cf_ops_prod"}}

    annotations_sql = render_aws_annotations_evidence_sql(contract, environment=environment)
    governance_sql = render_aws_lake_formation_evidence_sql(contract, environment=environment)
    operations_sql = render_aws_operations_evidence_sql(contract, environment=environment)
    cost_sql = render_aws_operational_cost_query(environment=environment)

    assert "glue_catalog.`cf_ops_prod`.`ctrl_ingestion_annotations`" in annotations_sql
    assert "glue_catalog.`cf_ops_prod`.`ctrl_ingestion_access`" in governance_sql
    assert "glue_catalog.`cf_ops_prod`.`ctrl_ingestion_operations`" in operations_sql
    assert "FROM glue_catalog.`cf_ops_prod`.`ctrl_ingestion_runs`" in cost_sql


def test_aws_public_evidence_helpers_prefer_explicit_database_over_environment() -> None:
    environment = {"name": "prod", "adapter": "aws", "evidence": {"database": "cf_ops_prod"}}
    contract = {**_contract(), "operations": {"criticality": "high"}}

    sql = render_aws_operations_evidence_sql(contract, database="cf_ops_override", environment=environment)

    assert "glue_catalog.`cf_ops_override`.`ctrl_ingestion_operations`" in sql
    assert "cf_ops_prod" not in sql


def test_aws_adapter_environment_is_preserved() -> None:
    adapter = AWSAdapter.glue_iceberg(environment={"name": "prod", "adapter": "aws"})
    contract = semantic_contract_from_mapping(_contract())

    assert adapter.environment.name == "prod"
    assert adapter.plan(contract).status == "SUPPORTED"
