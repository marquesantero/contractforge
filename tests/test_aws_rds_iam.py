"""AWS RDS IAM JDBC rendering (runtime token, no baked credential)."""

from __future__ import annotations

from contractforge_aws import render_aws_contract
from contractforge_aws.sources import source_requires_rds_iam
from contractforge_aws.sources.rds_iam import render_rds_iam_token_helper


def _rds_iam_contract() -> dict:
    return {
        "source": {
            "type": "postgres",
            "url": "jdbc:postgresql://db.cluster-x.us-east-1.rds.amazonaws.com:5432/app",
            "table": "public.customers",
            "auth": {"type": "rds_iam", "username": "iam_reader", "region": "us-east-1"},
        },
        "target": {"catalog": "lake", "schema": "silver", "table": "customers"},
        "mode": "scd1_upsert",
        "merge_keys": ["customer_id"],
    }


def test_rds_iam_renders_runtime_token_not_placeholder() -> None:
    artifacts = render_aws_contract(_rds_iam_contract())
    glue_job = artifacts.artifacts["lake_silver_customers.glue_job.py"]

    assert "import boto3" in glue_job
    assert "def _cf_rds_iam_token(host, port, region, username):" in glue_job
    assert "generate_db_auth_token(" in glue_job
    assert (
        ".option('password', _cf_rds_iam_token('db.cluster-x.us-east-1.rds.amazonaws.com', 5432, 'us-east-1', 'iam_reader'))"
        in glue_job
    )
    # The core placeholder and metadata options must not survive into the script.
    assert "{{rds_iam_token}}" not in glue_job
    assert "contractforge.rdsIam" not in glue_job
    compile(glue_job, "glue_job.py", "exec")


def test_rds_iam_source_is_detected() -> None:
    assert source_requires_rds_iam(_rds_iam_contract()["source"]) is True
    assert (
        source_requires_rds_iam(
            {"type": "postgres", "url": "jdbc:postgresql://h/db", "table": "public.t"}
        )
        is False
    )


def test_rds_iam_review_comment_redacts_password() -> None:
    artifacts = render_aws_contract(_rds_iam_contract())
    glue_job = artifacts.artifacts["lake_silver_customers.glue_job.py"]

    review_line = next(line for line in glue_job.splitlines() if line.lstrip().startswith("# {"))
    assert "***REDACTED***" in review_line


def test_rds_iam_does_not_inject_secret_resolver() -> None:
    # RDS IAM needs boto3 but not the Secrets Manager resolver (which imports json at top level).
    artifacts = render_aws_contract(_rds_iam_contract())
    glue_job = artifacts.artifacts["lake_silver_customers.glue_job.py"]

    assert "import boto3" in glue_job
    # no top-level json import (the evidence helper has its own local import json)
    assert "\nimport json\n" not in glue_job
    assert "_cf_resolve_secret" not in glue_job


def test_rds_iam_token_helper_is_valid_python() -> None:
    compile(render_rds_iam_token_helper(), "helper.py", "exec")
