"""Render AWS IAM review policies for generated Glue jobs."""

from __future__ import annotations

import json
from typing import Any

from contractforge_core.semantic import SemanticContract
from contractforge_aws.rendering.iam_s3 import bucket_arn, s3_policy_uris
from contractforge_aws.rendering.names import glue_database_name, glue_table_name
from contractforge_aws.security import secret_placeholder_refs
from contractforge_aws.sources import source_requires_rds_iam, source_requires_secret_resolver


def render_glue_job_iam_policy(
    contract: SemanticContract,
    *,
    evidence_database_name: str | None = None,
    environment_parameters: dict[str, Any] | None = None,
    artifact_uri: str | None = None,
) -> str:
    """Render a review policy for the Glue job role.

    The policy intentionally uses account/region placeholders because rendering
    must stay deterministic and SDK-free. Reviewers should narrow S3 prefixes,
    KMS keys and Glue resources before applying.
    """

    source = contract.source.raw or {}
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            _glue_catalog_statement(contract, evidence_database_name=evidence_database_name),
            _logs_statement(),
            *_s3_statements(contract, environment_parameters=environment_parameters, artifact_uri=artifact_uri),
            *_secret_statements(source),
            *_rds_iam_statements(source),
        ],
        "contractforge_review_notes": [
            "Replace ${region}, ${account_id}, artifact bucket and optional KMS placeholders before applying.",
            "Keep this as a job-role policy. Lake Formation consumer grants are rendered separately.",
            "Generated permissions are a starting point; production roles should be narrowed by platform security review.",
        ],
    }
    return json.dumps(policy, indent=2, sort_keys=True) + "\n"


def _glue_catalog_statement(contract: SemanticContract, *, evidence_database_name: str | None = None) -> dict[str, object]:
    database = glue_database_name(contract)
    evidence_database = evidence_database_name or f"{database}_ops"
    table = glue_table_name(contract)
    return {
        "Sid": "GlueCatalogForIcebergTarget",
        "Effect": "Allow",
        "Action": [
            "glue:GetDatabase",
            "glue:CreateDatabase",
            "glue:GetTable",
            "glue:CreateTable",
            "glue:UpdateTable",
            "glue:DeleteTable",
            "glue:GetPartitions",
        ],
        "Resource": [
            "arn:aws:glue:${region}:${account_id}:catalog",
            f"arn:aws:glue:${{region}}:${{account_id}}:database/{database}",
            f"arn:aws:glue:${{region}}:${{account_id}}:table/{database}/{table}",
            f"arn:aws:glue:${{region}}:${{account_id}}:database/{evidence_database}",
            f"arn:aws:glue:${{region}}:${{account_id}}:table/{evidence_database}/*",
        ],
    }


def _logs_statement() -> dict[str, object]:
    return {
        "Sid": "GlueJobLogs",
        "Effect": "Allow",
        "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
        "Resource": "arn:aws:logs:${region}:${account_id}:log-group:/aws-glue/*",
    }


def _s3_statements(
    contract: SemanticContract,
    *,
    environment_parameters: dict[str, Any] | None,
    artifact_uri: str | None,
) -> list[dict[str, object]]:
    uris = _s3_uris(contract, environment_parameters=environment_parameters, artifact_uri=artifact_uri)
    if not uris:
        return [_s3_placeholder_statement("ContractForgeArtifactAndWarehouseAccess")]
    buckets = sorted({uri.bucket for uri in uris})
    objects = sorted({uri.object_arn for uri in uris})
    return [
        {"Sid": "S3ListContractForgeBuckets", "Effect": "Allow", "Action": ["s3:ListBucket"], "Resource": [bucket_arn(bucket) for bucket in buckets]},
        {
            "Sid": "S3ReadWriteContractForgeObjects",
            "Effect": "Allow",
            "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:AbortMultipartUpload", "s3:ListMultipartUploadParts"],
            "Resource": objects,
        },
    ]


def _secret_statements(source: dict) -> list[dict[str, object]]:
    if not source_requires_secret_resolver(source):
        return []
    resources = _secret_resources(source)
    return [
        {
            "Sid": "ReadDeclaredSecrets",
            "Effect": "Allow",
            "Action": ["secretsmanager:GetSecretValue"],
            "Resource": resources,
        }
    ]


def _secret_resources(value: object) -> list[str]:
    scopes = sorted(set(_secret_scopes(value)))
    if not scopes:
        return ["arn:aws:secretsmanager:${region}:${account_id}:secret:contractforge/*"]
    return [_secret_resource(scope) for scope in scopes]


def _secret_scopes(value: object) -> list[str]:
    if isinstance(value, dict):
        return [scope for item in value.values() for scope in _secret_scopes(item)]
    if isinstance(value, (list, tuple)):
        return [scope for item in value for scope in _secret_scopes(item)]
    if isinstance(value, str):
        return [scope for scope, _key in secret_placeholder_refs(value)]
    return []


def _secret_resource(scope: str) -> str:
    if scope.startswith("arn:aws:secretsmanager:"):
        return scope
    return f"arn:aws:secretsmanager:${{region}}:${{account_id}}:secret:{scope}*"


def _rds_iam_statements(source: dict) -> list[dict[str, object]]:
    if not source_requires_rds_iam(source):
        return []
    user = _rds_iam_user(source)
    return [
        {
            "Sid": "RdsIamConnect",
            "Effect": "Allow",
            "Action": ["rds-db:connect"],
            "Resource": f"arn:aws:rds-db:${{region}}:${{account_id}}:dbuser:${{db_resource_id}}/{user}",
        }
    ]


def _rds_iam_user(source: dict) -> str:
    auth = source.get("auth") if isinstance(source.get("auth"), dict) else {}
    user = str(auth.get("username") or source.get("user") or source.get("options", {}).get("user") or "").strip()
    return user or "${db_user}"


def _s3_placeholder_statement(sid: str) -> dict[str, object]:
    return {
        "Sid": sid,
        "Effect": "Allow",
        "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"],
        "Resource": ["arn:aws:s3:::${contractforge_bucket}", "arn:aws:s3:::${contractforge_bucket}/*"],
    }


def _s3_uris(contract: SemanticContract, *, environment_parameters: dict[str, Any] | None, artifact_uri: str | None):
    return s3_policy_uris(contract, environment_parameters=environment_parameters, artifact_uri=artifact_uri)
