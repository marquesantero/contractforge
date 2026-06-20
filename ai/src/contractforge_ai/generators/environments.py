"""Shared adapter environment payloads for generated ContractForge projects."""

from __future__ import annotations

from typing import Any


def databricks_environment_payload(
    *,
    catalog: str = "main",
    evidence_schema: str = "ops",
) -> dict[str, Any]:
    """Return a Databricks environment scaffold with review-safe defaults."""

    return {
        "name": "databricks",
        "adapter": "databricks",
        "runtime": {
            "kind": "classic_cluster",
        },
        "evidence": {
            "catalog": catalog,
            "schema": evidence_schema,
        },
    }


def aws_glue_iceberg_environment_payload(project_slug: str, *, evidence_database: str | None = None) -> dict[str, Any]:
    """Return an AWS Glue/Iceberg environment scaffold with review-safe placeholders."""

    safe_slug = project_slug.strip().strip("/") or "project"
    return {
        "name": "aws",
        "adapter": "aws",
        "runtime": {
            "runtime": "aws_glue_spark",
        },
        "evidence": {
            "database": evidence_database or f"{safe_slug}_ops",
        },
        "artifacts": {
            "uri": f"s3://review-required-contractforge-artifacts/{safe_slug}/",
            "layout": "contractforge-v1",
            "include_contract_bundle": True,
            "include_normalized_contract": True,
        },
        "parameters": {
            "aws": {
                "region": "REVIEW_REQUIRED",
                "iceberg": {
                    "warehouse": f"s3://review-required-contractforge-warehouse/{safe_slug}/",
                },
                "dependencies": {
                    "additional_python_modules": "pydantic>=2.7,eval-type-backport,PyYAML>=6",
                    "extra_py_files": ["s3://review-required-contractforge-artifacts/libs/contractforge_aws.whl"],
                },
                "glue_job": {
                    "role_arn": "REVIEW_REQUIRED",
                },
            }
        },
    }


def snowflake_sql_warehouse_environment_payload(project_slug: str, *, evidence_schema: str = "OPS") -> dict[str, Any]:
    """Return a Snowflake SQL warehouse environment scaffold with review-safe placeholders."""

    safe_slug = project_slug.strip().strip("/") or "project"
    return {
        "name": "snowflake",
        "adapter": "snowflake",
        "runtime": {
            "kind": "snowflake_sql_warehouse",
        },
        "evidence": {
            "database": "REVIEW_REQUIRED",
            "schema": evidence_schema,
        },
        "artifacts": {
            "stage": f"@REVIEW_REQUIRED_CONTRACTFORGE_ARTIFACTS/{safe_slug}/",
            "layout": "contractforge-v1",
            "include_contract_bundle": True,
            "include_normalized_contract": True,
        },
        "parameters": {
            "snowflake": {
                "warehouse": "REVIEW_REQUIRED",
                "role": "REVIEW_REQUIRED",
                "database": "REVIEW_REQUIRED",
                "schema": "REVIEW_REQUIRED",
            }
        },
    }


def fabric_lakehouse_environment_payload(project_slug: str, *, evidence_schema: str = "ops") -> dict[str, Any]:
    """Return a Microsoft Fabric Lakehouse environment scaffold with review-safe placeholders."""

    safe_slug = project_slug.strip().strip("/") or "project"
    return {
        "name": "fabric",
        "adapter": "fabric",
        "runtime": {
            "kind": "fabric_lakehouse",
        },
        "evidence": {
            "lakehouse": "REVIEW_REQUIRED",
            "schema": evidence_schema,
        },
        "artifacts": {
            "path": f"Files/contractforge/{safe_slug}/",
            "layout": "contractforge-v1",
            "include_contract_bundle": True,
            "include_normalized_contract": True,
        },
        "parameters": {
            "fabric": {
                "workspace_id": "REVIEW_REQUIRED",
                "lakehouse_id": "REVIEW_REQUIRED",
                "lakehouse_name": "REVIEW_REQUIRED",
            }
        },
    }


def gcp_bigquery_environment_payload(project_slug: str, *, evidence_dataset: str | None = None) -> dict[str, Any]:
    """Return a GCP BigQuery environment scaffold with review-safe placeholders."""

    safe_slug = project_slug.strip().strip("/") or "project"
    return {
        "name": "gcp",
        "adapter": "gcp",
        "runtime": {
            "kind": "gcp_bigquery",
        },
        "evidence": {
            "dataset": evidence_dataset or f"{safe_slug}_ops",
        },
        "artifacts": {
            "gcs_uri": f"gs://review-required-contractforge-artifacts/{safe_slug}/",
            "layout": "contractforge-v1",
            "include_contract_bundle": True,
            "include_normalized_contract": True,
        },
        "parameters": {
            "gcp": {
                "project_id": "REVIEW_REQUIRED",
                "location": "REVIEW_REQUIRED",
                "staging_bucket": "REVIEW_REQUIRED",
            }
        },
    }
