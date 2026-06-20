"""Static contract for Lake Formation consumer-matrix smoke checks."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class LakeFormationMatrixConfig:
    account_id: str
    region: str
    database: str
    table: str
    consumer_principal: str | None
    athena_workgroup: str
    athena_output_location: str | None
    validate_athena_reads: bool = False
    athena_allowed_role_arn: str | None = None
    athena_denied_role_arn: str | None = None
    validate_glue_reads: bool = False
    glue_script_s3_uri: str | None = None
    glue_allowed_role_arn: str | None = None
    glue_denied_role_arn: str | None = None
    glue_temp_dir: str | None = None
    glue_warehouse_s3_uri: str | None = None


def dry_run_payload(config: Any) -> dict[str, Any]:
    return {
        "status": "DRY_RUN",
        "config": asdict(config),
        "required_cases": required_cases(),
        "required_prerequisites": required_prerequisites(),
    }


def required_cases() -> list[str]:
    return [
        "athena_allowed_principal_reads_declared_rows",
        "athena_denied_principal_cannot_exceed_filter",
        "glue_spark_allowed_principal_reads_declared_rows",
        "glue_spark_denied_principal_cannot_exceed_filter",
        "lakeformation_data_cells_filter_present",
        "ctrl_ingestion_access_evidence_present",
    ]


def required_prerequisites() -> list[str]:
    return [
        "Glue table is registered with Lake Formation",
        "At least one non-root consumer IAM principal is available",
        "Lake Formation DataCellsFilter exists for the declared table",
        "Athena output location is configured for consumer read checks",
        "Glue Spark consumer role can be assumed for read checks",
    ]


__all__ = ["LakeFormationMatrixConfig", "dry_run_payload", "required_cases", "required_prerequisites"]
