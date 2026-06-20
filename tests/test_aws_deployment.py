from __future__ import annotations

import json

import pytest

from contractforge_aws import (
    render_aws_contract,
    render_aws_deployment_manifest,
    render_aws_glue_job_cloudformation,
    render_aws_glue_job_definition,
    render_aws_glue_job_terraform,
)


def test_rendered_contract_includes_glue_job_definition_artifact() -> None:
    artifacts = render_aws_contract(
        {
            "source": {"type": "s3", "path": "s3://landing/orders", "format": "json"},
            "target": {"catalog": "lake", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
        }
    ).artifacts

    payload = json.loads(artifacts["lake_bronze_orders.glue_job_definition.json"])

    assert payload["Name"] == "contractforge_lake_bronze_orders"
    assert payload["Role"] == "${glue_role_arn}"
    assert payload["Command"]["ScriptLocation"] == (
        "s3://${artifact_bucket}/${artifact_prefix}/runtime/contractforge_aws_runner.py"
    )
    assert payload["DefaultArguments"]["--CONTRACTFORGE_RUNTIME_MODE"] == "library_runner"
    assert payload["DefaultArguments"]["--CONTRACTFORGE_CONTRACT_URI"] == (
        "s3://${artifact_bucket}/${artifact_prefix}/runtime/lake_bronze_orders.contract.json"
    )
    assert payload["DefaultArguments"]["--datalake-formats"] == "iceberg"
    assert payload["DefaultArguments"]["--enable-glue-datacatalog"] == "true"
    assert payload["DefaultArguments"]["--job-bookmark-option"] == "job-bookmark-disable"
    assert (
        payload["DefaultArguments"]["--conf"]
        == "spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions"
    )
    assert payload["GlueVersion"] == "4.0"
    assert payload["WorkerType"] == "G.1X"
    assert "contractforge_review_notes" in payload
    assert "lake_bronze_orders.cloudformation.json" in artifacts
    assert "lake_bronze_orders.terraform.tf" in artifacts
    assert "lake_bronze_orders.deployment_manifest.json" in artifacts
    assert "runtime/contractforge_aws_runner.py" in artifacts
    assert "raise SystemExit" not in artifacts["runtime/contractforge_aws_runner.py"]
    assert "    main()" in artifacts["runtime/contractforge_aws_runner.py"]


def test_glue_job_definition_rejects_generated_script_runtime_mode() -> None:
    with pytest.raises(ValueError, match="library runner"):
        render_aws_glue_job_definition(
            {
                "source": {"type": "s3", "path": "s3://landing/orders", "format": "json"},
                "target": {"catalog": "lake", "schema": "bronze", "table": "orders"},
                "mode": "scd0_append",
                "extensions": {"aws": {"glue_job": {"runtime_mode": "generated_script"}}},
            }
        )


def test_rendered_contract_includes_deployment_manifest() -> None:
    artifacts = render_aws_contract(
        {
            "source": {"type": "s3", "path": "s3://landing/orders", "format": "json"},
            "target": {"catalog": "lake", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
        }
    ).artifacts

    manifest = json.loads(artifacts["lake_bronze_orders.deployment_manifest.json"])
    artifact_names = {artifact["name"] for artifact in manifest["artifacts"]}

    assert manifest["kind"] == "contractforge.aws.deployment_manifest.v1"
    assert manifest["subtarget"] == "aws_glue_iceberg"
    assert manifest["status"] == "supported"
    assert manifest["target"]["table"] == "glue_catalog.lake_bronze.orders"
    assert manifest["evidence_database"] == "lake_bronze_ops"
    assert manifest["artifact_summary"]["artifact_count"] == len(manifest["artifacts"])
    assert manifest["artifact_summary"]["runtime_artifact_bytes"] > 0
    assert manifest["artifact_size_budget"]["runtime_warning_bytes"] == 262144
    assert manifest["artifact_size_budget"]["runtime_status"] == "OK"
    assert manifest["artifact_size_budget"]["runtime_artifact_bytes"] == manifest["artifact_summary"]["runtime_artifact_bytes"]
    assert "lake_bronze_orders.glue_job.py" in artifact_names
    assert "lake_bronze_orders.glue_job_definition.json" in artifact_names
    assert "lake_bronze_orders.deployment_manifest.json" not in artifact_names
    assert {
        "AthenaSqlRunner",
        "ensure_aws_evidence_tables",
        "audit_evidence_tables",
        "wait_aws_glue_job_run",
        "apply_aws_lake_formation_contract",
        "apply_aws_annotations_contract",
        "record_aws_operations_contract",
    }.issubset(set(manifest["optional_runtime_helpers"]))
    assert manifest["optional_runtime_flow"] == [
        {
            "phase": "setup",
            "helpers": ["AthenaSqlRunner", "ensure_aws_evidence_tables"],
            "requires_aws_api": True,
        },
        {
            "phase": "publish",
            "helpers": ["publish_aws_contract_artifacts_to_s3"],
            "requires_aws_api": True,
        },
        {
            "phase": "register",
            "helpers": ["register_aws_glue_job", "register_aws_glue_job_definition_payload"],
            "requires_aws_api": True,
        },
        {
            "phase": "run",
            "helpers": ["start_aws_glue_job_run", "get_aws_glue_job_run_status", "wait_aws_glue_job_run"],
            "requires_aws_api": True,
        },
        {
            "phase": "governance",
            "helpers": ["apply_aws_lake_formation_contract", "apply_aws_lake_formation_plan"],
            "requires_aws_api": True,
        },
        {
            "phase": "metadata",
            "helpers": ["apply_aws_annotations_contract", "apply_aws_annotations_plan"],
            "requires_aws_api": True,
        },
        {
            "phase": "operations",
            "helpers": ["record_aws_operations_contract"],
            "requires_aws_api": False,
        },
        {
            "phase": "post_run_evidence",
            "helpers": ["reconcile_aws_glue_job_run_evidence", "render_aws_glue_job_run_evidence_sql"],
            "requires_aws_api": True,
        },
        {
            "phase": "audit",
            "helpers": ["AthenaSqlRunner", "audit_evidence_tables"],
            "requires_aws_api": True,
        },
    ]
    deployment = [artifact for artifact in manifest["artifacts"] if artifact["name"].endswith(".cloudformation.json")]
    assert deployment == [
        {
            "name": "lake_bronze_orders.cloudformation.json",
            "category": "deployment",
            "applyable": True,
            "requires_review": True,
            "bytes": deployment[0]["bytes"],
            "lines": deployment[0]["lines"],
            "order": deployment[0]["order"],
        }
    ]
    assert deployment[0]["bytes"] > 0
    assert deployment[0]["lines"] > 0
    generated_runtime = [artifact for artifact in manifest["artifacts"] if artifact["name"] == "lake_bronze_orders.glue_job.py"]
    assert generated_runtime == [
        {
            "name": "lake_bronze_orders.glue_job.py",
            "category": "runtime",
            "applyable": False,
            "requires_review": True,
            "bytes": generated_runtime[0]["bytes"],
            "lines": generated_runtime[0]["lines"],
            "order": generated_runtime[0]["order"],
        }
    ]


def test_deployment_manifest_describes_performance_profile_artifact() -> None:
    artifacts = render_aws_contract(
        {
            "source": {"type": "jdbc", "url": "jdbc:postgresql://host/db", "table": "public.customers"},
            "target": {"catalog": "lake", "schema": "silver", "table": "customers"},
            "mode": "scd1_hash_diff",
            "merge_keys": ["customer_id"],
            "hash_keys": ["name", "email"],
        }
    ).artifacts

    manifest = json.loads(artifacts["lake_silver_customers.deployment_manifest.json"])
    performance = [
        artifact for artifact in manifest["artifacts"] if artifact["name"].startswith("lake_silver_customers.performance")
    ]
    profile = [artifact for artifact in performance if artifact["name"].endswith(".performance_profile.json")]
    query = [artifact for artifact in performance if artifact["name"].endswith(".performance.sql")]

    assert profile == [
        {
            "name": "lake_silver_customers.performance_profile.json",
            "category": "performance",
            "applyable": False,
            "requires_review": True,
            "bytes": profile[0]["bytes"],
            "lines": profile[0]["lines"],
            "order": profile[0]["order"],
        }
    ]
    assert query == [
        {
            "name": "lake_silver_customers.performance.sql",
            "category": "performance",
            "applyable": False,
            "requires_review": True,
            "bytes": query[0]["bytes"],
            "lines": query[0]["lines"],
            "order": query[0]["order"],
        }
    ]
    assert profile[0]["bytes"] > 0
    assert query[0]["bytes"] > 0
    assert manifest["artifact_summary"]["total_bytes"] >= profile[0]["bytes"] + query[0]["bytes"]


def test_deployment_manifest_includes_source_specific_review_boundaries() -> None:
    artifacts = render_aws_contract(
        {
            "source": {
                "type": "postgres",
                "url": "jdbc:postgresql://db.abc.us-east-1.rds.amazonaws.com:5432/app",
                "table": "public.orders",
                "auth": {"type": "rds_iam", "username": "app_user", "region": "us-east-1"},
            },
            "target": {"catalog": "lake", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
        }
    ).artifacts

    manifest = json.loads(artifacts["lake_bronze_orders.deployment_manifest.json"])

    assert "RDS IAM db_resource_id mapping and database user grant review." in manifest["review_boundaries"]


def test_deployment_manifest_includes_connector_package_boundary() -> None:
    manifest = json.loads(
        render_aws_deployment_manifest(
            {
                "source": {"type": "kafka_bounded", "bootstrap_servers": "broker:9092", "topic": "events"},
                "target": {"catalog": "lake", "schema": "bronze", "table": "events"},
                "mode": "scd0_append",
            }
        )
    )

    assert "Glue connector jar/package availability and runtime dependency review." in manifest["review_boundaries"]


def test_public_deployment_manifest_renderer_returns_manifest() -> None:
    manifest = json.loads(
        render_aws_deployment_manifest(
            {
                "source": {"type": "s3", "path": "s3://landing/orders", "format": "json"},
                "target": {"catalog": "lake", "schema": "bronze", "table": "orders"},
                "mode": "scd0_append",
            }
        )
    )

    assert manifest["manifest_artifact"] == "lake_bronze_orders.deployment_manifest.json"


def test_glue_job_definition_honors_aws_extensions() -> None:
    payload = json.loads(
        render_aws_glue_job_definition(
            {
                "source": {"type": "incremental_files", "path": "s3://landing/orders", "format": "json"},
                "target": {"catalog": "lake", "schema": "bronze", "table": "orders"},
                "mode": "scd0_append",
                "extensions": {
                    "aws": {
                        "glue_job": {
                            "name": "cf-orders",
                            "role_arn": "arn:aws:iam::123456789012:role/ContractForgeGlueRole",
                            "script_s3_uri": "s3://artifacts/orders/glue_job.py",
                            "worker_type": "G.2X",
                            "number_of_workers": 3,
                            "timeout_minutes": 30,
                            "max_retries": 1,
                            "connection_names": ["cf-msk-vpc"],
                            "default_arguments": {"--TempDir": "s3://artifacts/tmp/"},
                        },
                        "job_bookmarks": {"enabled": True},
                        "dependencies": {"python_modules": ["contractforge-core", "requests"]},
                    }
                },
            }
        )
    )

    assert payload["Name"] == "cf-orders"
    assert payload["Role"] == "arn:aws:iam::123456789012:role/ContractForgeGlueRole"
    assert payload["Command"]["ScriptLocation"] == "s3://artifacts/orders/glue_job.py"
    assert payload["WorkerType"] == "G.2X"
    assert payload["NumberOfWorkers"] == 3
    assert payload["Timeout"] == 30
    assert payload["MaxRetries"] == 1
    assert payload["Connections"] == {"Connections": ["cf-msk-vpc"]}
    assert payload["DefaultArguments"]["--job-bookmark-option"] == "job-bookmark-enable"
    assert payload["DefaultArguments"]["--additional-python-modules"] == "contractforge-core,requests"
    assert payload["DefaultArguments"]["--TempDir"] == "s3://artifacts/tmp/"


def test_glue_job_definition_rejects_adapter_owned_argument_overrides() -> None:
    with pytest.raises(ValueError, match="adapter-owned Glue arguments"):
        render_aws_glue_job_definition(
            {
                "source": {"type": "incremental_files", "path": "s3://landing/orders", "format": "json"},
                "target": {"catalog": "lake", "schema": "bronze", "table": "orders"},
                "mode": "scd0_append",
                "extensions": {
                    "aws": {
                        "glue_job": {
                            "default_arguments": {
                                "--datalake-formats": "hudi",
                            }
                        }
                    }
                },
            }
        )


def test_glue_job_definition_rejects_dependency_argument_overrides() -> None:
    with pytest.raises(ValueError, match="--additional-python-modules"):
        render_aws_glue_job_definition(
            {
                "source": {
                    "type": "rest_api",
                    "request": {"url": "https://api.example.com/orders"},
                },
                "target": {"catalog": "lake", "schema": "bronze", "table": "api"},
                "mode": "scd0_append",
                "extensions": {
                    "aws": {
                        "glue_job": {
                            "default_arguments": {
                                "--additional-python-modules": "unsafe-override",
                            }
                        }
                    }
                },
            }
        )


def test_glue_job_definition_adds_core_dependency_for_rest_api() -> None:
    payload = json.loads(
        render_aws_glue_job_definition(
            {
                "source": {
                    "type": "rest_api",
                    "request": {"url": "https://api.example.com/orders"},
                    "auth": {"type": "bearer_token", "token": "{{ secret:api/token }}"},
                },
                "target": {"catalog": "lake", "schema": "bronze", "table": "api"},
                "mode": "scd0_append",
            }
        )
    )

    assert payload["DefaultArguments"]["--additional-python-modules"] == "contractforge-core"


def test_glue_job_definition_notes_connector_package_boundary() -> None:
    payload = json.loads(
        render_aws_glue_job_definition(
            {
                "source": {"type": "kafka_bounded", "bootstrap_servers": "broker:9092", "topic": "events"},
                "target": {"catalog": "lake", "schema": "bronze", "table": "events"},
                "mode": "scd0_append",
            }
        )
    )

    notes = "\n".join(payload["contractforge_review_notes"])
    assert "matching Spark connector jar/package" in notes
    assert "--extra-jars" not in payload["DefaultArguments"]


def test_glue_job_definition_notes_runtime_connector_config_boundary() -> None:
    payload = json.loads(
        render_aws_glue_job_definition(
            {
                "source": {"type": "gcs", "path": "gs://landing/orders", "format": "json"},
                "target": {"catalog": "lake", "schema": "bronze", "table": "orders"},
                "mode": "scd0_append",
            }
        )
    )

    notes = "\n".join(payload["contractforge_review_notes"])
    assert "runtime connector/package and credential configuration" in notes


def test_glue_job_cloudformation_scaffold_is_parameterized() -> None:
    template = json.loads(
        render_aws_glue_job_cloudformation(
            {
                "source": {"type": "parquet", "path": "s3://landing/orders"},
                "target": {"catalog": "lake", "schema": "bronze", "table": "orders"},
                "mode": "scd0_overwrite",
                "extensions": {
                    "aws": {
                        "glue_job": {
                            "name": "cf-orders",
                            "role_arn": "arn:aws:iam::123456789012:role/ContractForgeGlueRole",
                            "script_s3_uri": "s3://artifacts/orders/glue_job.py",
                        }
                    }
                },
            }
        )
    )

    assert template["AWSTemplateFormatVersion"] == "2010-09-09"
    assert template["Parameters"]["GlueRoleArn"]["Default"] == "arn:aws:iam::123456789012:role/ContractForgeGlueRole"
    assert template["Parameters"]["ScriptS3Uri"]["Default"] == "s3://artifacts/orders/glue_job.py"
    assert "ContractForgeTargetDatabase" in template["Resources"]
    assert "ContractForgeEvidenceDatabase" in template["Resources"]
    job = template["Resources"]["CfOrdersGlueJob"]["Properties"]
    assert job["Name"] == "cf-orders"
    assert job["Role"] == {"Ref": "GlueRoleArn"}
    assert job["Command"]["ScriptLocation"] == {"Ref": "ScriptS3Uri"}
    assert job["DefaultArguments"]["--datalake-formats"] == "iceberg"


def test_glue_job_terraform_scaffold_is_parameterized() -> None:
    terraform = render_aws_glue_job_terraform(
        {
            "source": {"type": "parquet", "path": "s3://landing/orders"},
            "target": {"catalog": "lake", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
            "extensions": {
                "aws": {
                    "glue_job": {
                        "name": "cf-orders",
                        "role_arn": "arn:aws:iam::123456789012:role/ContractForgeGlueRole",
                        "script_s3_uri": "s3://artifacts/orders/glue_job.py",
                    }
                }
            },
        }
    )

    assert 'resource "aws_glue_catalog_database" "target"' in terraform
    assert 'resource "aws_glue_catalog_database" "evidence"' in terraform
    assert 'resource "aws_glue_job" "contractforge"' in terraform
    assert 'default     = "arn:aws:iam::123456789012:role/ContractForgeGlueRole"' in terraform
    assert 'default     = "s3://artifacts/orders/glue_job.py"' in terraform
    assert 'name              = "cf-orders"' in terraform
    assert 'role_arn          = var.glue_role_arn' in terraform
    assert '"--datalake-formats" = "iceberg"' in terraform
