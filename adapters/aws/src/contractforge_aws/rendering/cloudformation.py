"""Render AWS CloudFormation review templates."""

from __future__ import annotations

import json
import re
from typing import Any

from contractforge_core.semantic import SemanticContract
from contractforge_aws.rendering.deployment import glue_job_definition_payload
from contractforge_aws.rendering.names import glue_database_name


def render_glue_job_cloudformation(
    contract: SemanticContract,
    *,
    evidence_database_name: str | None = None,
    environment_parameters: dict[str, Any] | None = None,
) -> str:
    return json.dumps(
        glue_job_cloudformation_template(
            contract,
            evidence_database_name=evidence_database_name,
            environment_parameters=environment_parameters,
        ),
        indent=2,
        sort_keys=True,
    ) + "\n"


def glue_job_cloudformation_template(
    contract: SemanticContract,
    *,
    evidence_database_name: str | None = None,
    environment_parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    job = glue_job_definition_payload(contract, environment_parameters=environment_parameters)
    database = glue_database_name(contract)
    evidence_database = evidence_database_name or f"{database}_ops"
    return {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Description": "ContractForge AWS Glue Iceberg ingestion scaffold.",
        "Parameters": _parameters(job),
        "Resources": {
            "ContractForgeTargetDatabase": _database_resource(database),
            "ContractForgeEvidenceDatabase": _database_resource(evidence_database),
            _job_logical_id(job["Name"]): _job_resource(job),
        },
        "Outputs": {
            "GlueJobName": {"Value": job["Name"]},
            "TargetDatabaseName": {"Value": database},
            "EvidenceDatabaseName": {"Value": evidence_database},
        },
        "Metadata": {
            "ContractForgeReviewNotes": [
                "This scaffold is generated for review and deployment automation.",
                "It does not create the IAM role; pass an existing reviewed Glue role ARN.",
                "Lake Formation grants, VPC networking, KMS keys and bucket policies remain platform-security review items.",
            ]
        },
    }


def _parameters(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "GlueRoleArn": _parameter("AWS Glue execution role ARN.", job.get("Role")),
        "ScriptS3Uri": _parameter("S3 URI of the rendered ContractForge Glue job script.", job["Command"]["ScriptLocation"]),
    }


def _parameter(description: str, default: Any) -> dict[str, Any]:
    parameter: dict[str, Any] = {"Type": "String", "Description": description}
    text = str(default or "")
    if text and "${" not in text:
        parameter["Default"] = text
    return parameter


def _database_resource(name: str) -> dict[str, Any]:
    return {
        "Type": "AWS::Glue::Database",
        "Properties": {
            "CatalogId": {"Ref": "AWS::AccountId"},
            "DatabaseInput": {"Name": name},
        },
    }


def _job_resource(job: dict[str, Any]) -> dict[str, Any]:
    command = dict(job["Command"])
    command["ScriptLocation"] = {"Ref": "ScriptS3Uri"}
    return {
        "Type": "AWS::Glue::Job",
        "Properties": {
            "Name": job["Name"],
            "Role": {"Ref": "GlueRoleArn"},
            "Command": command,
            "DefaultArguments": job["DefaultArguments"],
            "Description": job["Description"],
            "GlueVersion": job["GlueVersion"],
            "MaxRetries": job["MaxRetries"],
            "NumberOfWorkers": job["NumberOfWorkers"],
            "Timeout": job["Timeout"],
            "WorkerType": job["WorkerType"],
        },
    }


def _job_logical_id(name: str) -> str:
    parts = re.findall(r"[A-Za-z0-9]+", name)
    body = "".join(part[:1].upper() + part[1:] for part in parts) or "ContractForgeGlueJob"
    return body if body.endswith("GlueJob") else f"{body}GlueJob"
