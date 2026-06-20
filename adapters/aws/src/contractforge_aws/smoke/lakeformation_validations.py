"""Validation orchestration for Lake Formation consumer-matrix smoke checks."""

from __future__ import annotations

from typing import Any

from contractforge_aws.smoke.lakeformation_athena import AthenaReadValidationConfig, validate_athena_reads
from contractforge_aws.smoke.lakeformation_contract import LakeFormationMatrixConfig
from contractforge_aws.smoke.lakeformation_glue import GlueReadValidationConfig, validate_glue_reads


def athena_validation(boto3: Any, config: LakeFormationMatrixConfig, blockers: list[str]) -> dict[str, Any]:
    if not config.validate_athena_reads:
        return {"status": "SKIPPED", "reason": "Run with --validate-athena-reads to execute consumer read checks."}
    if hard_preflight_blockers(blockers):
        return {"status": "SKIPPED", "reason": "Preflight blockers must be resolved before Athena read validation."}
    return validate_athena_reads(
        boto3,
        AthenaReadValidationConfig(
            region=config.region,
            database=config.database,
            table=config.table,
            workgroup=config.athena_workgroup,
            output_location=config.athena_output_location,
            allowed_role_arn=config.athena_allowed_role_arn,
            denied_role_arn=config.athena_denied_role_arn,
        ),
    )


def glue_validation(boto3: Any, config: LakeFormationMatrixConfig, blockers: list[str]) -> dict[str, Any]:
    if not config.validate_glue_reads:
        return {"status": "SKIPPED", "reason": "Run with --validate-glue-reads to execute Glue Spark read checks."}
    if hard_preflight_blockers(blockers):
        return {"status": "SKIPPED", "reason": "Preflight blockers must be resolved before Glue read validation."}
    return validate_glue_reads(
        boto3,
        GlueReadValidationConfig(
            region=config.region,
            database=config.database,
            table=config.table,
            script_s3_uri=config.glue_script_s3_uri,
            allowed_role_arn=config.glue_allowed_role_arn,
            denied_role_arn=config.glue_denied_role_arn,
            temp_dir=config.glue_temp_dir,
            warehouse_s3_uri=config.glue_warehouse_s3_uri,
        ),
    )


def status_with_validation(blockers: list[str], *validations: dict[str, Any]) -> str:
    if hard_preflight_blockers(blockers):
        return "BLOCKED"
    statuses = {str(item.get("status")) for item in validations}
    if "FAIL" in statuses:
        return "FAIL"
    if "READ_VALIDATION_PENDING" in statuses:
        return "READ_VALIDATION_PENDING"
    if blockers and "PASS" not in statuses:
        return "BLOCKED"
    return "PASS"


def hard_preflight_blockers(blockers: list[str]) -> list[str]:
    return [item for item in blockers if item != "No Lake Formation DataCellsFilter exists for the declared table."]


__all__ = ["athena_validation", "glue_validation", "hard_preflight_blockers", "status_with_validation"]
