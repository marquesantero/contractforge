"""AWS resource setup for the minimal smoke test."""

from __future__ import annotations

import json
from typing import Any

from contractforge_aws.smoke.models import SmokeConfig


def ensure_environment(config: SmokeConfig, *, session: Any) -> None:
    s3 = session.client("s3")
    iam = session.client("iam")
    sts = session.client("sts")
    identity = sts.get_caller_identity()
    if str(identity.get("Account")) != config.account_id:
        raise RuntimeError(f"Expected AWS account {config.account_id}, got {identity.get('Account')}")
    ensure_bucket(config, s3=s3)
    put_seed_data(config, s3=s3)
    ensure_role(config, iam=iam)


def ensure_bucket(config: SmokeConfig, *, s3: Any) -> None:
    buckets = {item["Name"] for item in s3.list_buckets().get("Buckets", [])}
    if config.bucket not in buckets:
        if config.region == "us-east-1":
            s3.create_bucket(Bucket=config.bucket)
        else:
            s3.create_bucket(Bucket=config.bucket, CreateBucketConfiguration={"LocationConstraint": config.region})
    s3.put_public_access_block(
        Bucket=config.bucket,
        PublicAccessBlockConfiguration={
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True,
        },
    )
    s3.put_bucket_tagging(Bucket=config.bucket, Tagging={"TagSet": tags()})


def put_seed_data(config: SmokeConfig, *, s3: Any) -> None:
    payload = "\n".join(
        [
            '{"order_id":1,"customer_id":"C001","status":"NEW","amount":10.5}',
            '{"order_id":2,"customer_id":"C002","status":"PAID","amount":20.0}',
            '{"order_id":3,"customer_id":"C003","status":"PAID","amount":30.25}',
            "",
        ]
    )
    s3.put_object(
        Bucket=config.bucket,
        Key="data/orders/orders.json",
        Body=payload.encode("utf-8"),
        ContentType="application/x-ndjson",
    )


def ensure_role(config: SmokeConfig, *, iam: Any) -> None:
    try:
        iam.get_role(RoleName=config.role_name)
    except Exception as exc:  # service-specific exception classes are created dynamically.
        code = getattr(exc, "response", {}).get("Error", {}).get("Code")
        if code != "NoSuchEntity":
            raise
        iam.create_role(RoleName=config.role_name, AssumeRolePolicyDocument=json.dumps(_trust_policy()), Tags=tags())
    iam.attach_role_policy(
        RoleName=config.role_name,
        PolicyArn="arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole",
    )
    iam.put_role_policy(
        RoleName=config.role_name,
        PolicyName="ContractForgeGlueSmokeAccess",
        PolicyDocument=json.dumps(inline_policy(config.bucket)),
    )


def tags() -> list[dict[str, str]]:
    return [
        {"Key": "project", "Value": "contractforge"},
        {"Key": "purpose", "Value": "aws-adapter-smoke"},
        {"Key": "managed-by", "Value": "contractforge-aws"},
    ]


def inline_policy(bucket: str) -> dict[str, Any]:
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "ContractForgeSmokeBucketAccess",
                "Effect": "Allow",
                "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
                "Resource": f"arn:aws:s3:::{bucket}/*",
            },
            {
                "Sid": "ContractForgeSmokeBucketList",
                "Effect": "Allow",
                "Action": ["s3:ListBucket", "s3:GetBucketLocation"],
                "Resource": f"arn:aws:s3:::{bucket}",
            },
            {
                "Sid": "ContractForgeSmokeGlueCatalog",
                "Effect": "Allow",
                "Action": [
                    "glue:CreateDatabase",
                    "glue:GetDatabase",
                    "glue:GetDatabases",
                    "glue:UpdateDatabase",
                    "glue:CreateTable",
                    "glue:GetTable",
                    "glue:GetTables",
                    "glue:UpdateTable",
                    "glue:DeleteTable",
                    "glue:CreatePartition",
                    "glue:GetPartition",
                    "glue:GetPartitions",
                    "glue:UpdatePartition",
                    "glue:BatchCreatePartition",
                    "glue:BatchUpdatePartition",
                    "glue:BatchDeletePartition",
                ],
                "Resource": "*",
            },
        ],
    }


def _trust_policy() -> dict[str, Any]:
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "glue.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    }
