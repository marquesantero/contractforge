from __future__ import annotations

import json

from contractforge_aws import render_aws_contract, render_aws_glue_job_iam_policy


def _contract(**source_overrides) -> dict:
    source = {"type": "parquet", "path": "s3://landing-bucket/raw/orders"}
    source.update(source_overrides)
    return {
        "source": source,
        "target": {"catalog": "lake", "schema": "bronze", "table": "orders"},
        "mode": "scd0_append",
        "extensions": {"aws": {"iceberg": {"warehouse": "s3://lake-bucket/warehouse/"}}},
    }


def test_render_glue_job_iam_policy_includes_catalog_s3_and_logs_permissions() -> None:
    policy = json.loads(render_aws_glue_job_iam_policy(_contract()))

    statements = {statement["Sid"]: statement for statement in policy["Statement"]}
    assert "GlueCatalogForIcebergTarget" in statements
    assert "GlueJobLogs" in statements
    assert "S3ReadWriteContractForgeObjects" in statements
    assert "arn:aws:glue:${region}:${account_id}:database/lake_bronze" in statements["GlueCatalogForIcebergTarget"]["Resource"]
    assert "arn:aws:s3:::landing-bucket/raw/orders/*" in statements["S3ReadWriteContractForgeObjects"]["Resource"]
    assert "arn:aws:s3:::lake-bucket/warehouse/*" in statements["S3ReadWriteContractForgeObjects"]["Resource"]
    assert policy["contractforge_review_notes"]


def test_render_glue_job_iam_policy_adds_secret_and_rds_iam_permissions() -> None:
    policy = json.loads(
        render_aws_glue_job_iam_policy(
            _contract(
                type="postgres",
                path=None,
                url="jdbc:postgresql://db.abc.us-east-1.rds.amazonaws.com:5432/app",
                table="public.orders",
                auth={"type": "rds_iam", "username": "app_user", "region": "us-east-1"},
            )
        )
    )

    sids = {statement["Sid"] for statement in policy["Statement"]}
    assert "RdsIamConnect" in sids
    statements = {statement["Sid"]: statement for statement in policy["Statement"]}
    assert statements["RdsIamConnect"]["Resource"] == (
        "arn:aws:rds-db:${region}:${account_id}:dbuser:${db_resource_id}/app_user"
    )


def test_render_glue_job_iam_policy_adds_secret_manager_permissions() -> None:
    policy = json.loads(
        render_aws_glue_job_iam_policy(
            _contract(
                type="jdbc",
                path=None,
                url="jdbc:postgresql://db.abc.us-east-1.rds.amazonaws.com:5432/app",
                table="public.orders",
                auth={"password": "{{ secret:contractforge/rds_password }}"},
            )
        )
    )

    statements = {statement["Sid"]: statement for statement in policy["Statement"]}
    assert "ReadDeclaredSecrets" in statements
    assert statements["ReadDeclaredSecrets"]["Resource"] == [
        "arn:aws:secretsmanager:${region}:${account_id}:secret:contractforge*"
    ]


def test_render_glue_job_iam_policy_lists_declared_secret_scopes() -> None:
    policy = json.loads(
        render_aws_glue_job_iam_policy(
            _contract(
                type="http_json",
                path=None,
                request={"url": "https://api.example.com/orders"},
                auth={"type": "bearer_token", "token": "{{ secret:api-prod/token }}"},
                options={"client_secret": "{{ secret:oauth-client/value }}"},
            )
        )
    )

    statements = {statement["Sid"]: statement for statement in policy["Statement"]}
    assert statements["ReadDeclaredSecrets"]["Resource"] == [
        "arn:aws:secretsmanager:${region}:${account_id}:secret:api-prod*",
        "arn:aws:secretsmanager:${region}:${account_id}:secret:oauth-client*",
    ]


def test_aws_contract_publishes_iam_policy_artifact() -> None:
    artifacts = render_aws_contract(_contract()).artifacts

    assert "lake_bronze_orders.iam_policy.json" in artifacts
    assert "GlueCatalogForIcebergTarget" in artifacts["lake_bronze_orders.iam_policy.json"]


def test_render_glue_job_iam_policy_includes_environment_artifacts_and_dependencies() -> None:
    environment = {
        "name": "prod",
        "adapter": "aws",
        "artifacts": {"uri": "s3://contractforge-artifacts/prod/orders/"},
        "parameters": {
            "aws": {
                "dependencies": {
                    "extra_py_files": "s3://contractforge-artifacts/libs/core.whl",
                    "extra_jars": ["s3://contractforge-artifacts/jars/postgres.jar"],
                },
                "glue_job": {"script_s3_uri": "s3://contractforge-artifacts/scripts/orders.py"},
            }
        },
    }

    policy = json.loads(render_aws_glue_job_iam_policy(_contract(), environment=environment))
    statements = {statement["Sid"]: statement for statement in policy["Statement"]}
    s3_resources = statements["S3ReadWriteContractForgeObjects"]["Resource"]

    assert "arn:aws:s3:::contractforge-artifacts/prod/orders/*" in s3_resources
    assert "arn:aws:s3:::contractforge-artifacts/libs/core.whl" in s3_resources
    assert "arn:aws:s3:::contractforge-artifacts/jars/postgres.jar" in s3_resources
    assert "arn:aws:s3:::contractforge-artifacts/scripts/orders.py" in s3_resources
