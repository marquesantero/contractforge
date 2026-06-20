"""Lake Formation consumer-matrix smoke preflight."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from typing import Any

from contractforge_aws.runtime.dependencies import require_boto3
from contractforge_aws.smoke.lakeformation_contract import (
    LakeFormationMatrixConfig,
    dry_run_payload,
    required_cases,
    required_prerequisites,
)
from contractforge_aws.smoke.lakeformation_permissions import permission_blockers
from contractforge_aws.smoke.lakeformation_validations import (
    athena_validation,
    glue_validation,
    status_with_validation,
)

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="contractforge-aws smoke-lakeformation-consumer-matrix")
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--database", required=True)
    parser.add_argument("--table", required=True)
    parser.add_argument("--consumer-principal")
    parser.add_argument("--athena-workgroup", default="primary")
    parser.add_argument("--athena-output-location")
    parser.add_argument("--validate-athena-reads", action="store_true")
    parser.add_argument("--athena-allowed-role-arn")
    parser.add_argument("--athena-denied-role-arn")
    parser.add_argument("--validate-glue-reads", action="store_true")
    parser.add_argument("--glue-script-s3-uri")
    parser.add_argument("--glue-allowed-role-arn")
    parser.add_argument("--glue-denied-role-arn")
    parser.add_argument("--glue-temp-dir")
    parser.add_argument("--glue-warehouse-s3-uri")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)

    config = LakeFormationMatrixConfig(
        account_id=args.account_id,
        region=args.region,
        database=args.database,
        table=args.table,
        consumer_principal=args.consumer_principal,
        athena_workgroup=args.athena_workgroup,
        athena_output_location=args.athena_output_location,
        validate_athena_reads=args.validate_athena_reads,
        athena_allowed_role_arn=args.athena_allowed_role_arn,
        athena_denied_role_arn=args.athena_denied_role_arn,
        validate_glue_reads=args.validate_glue_reads,
        glue_script_s3_uri=args.glue_script_s3_uri,
        glue_allowed_role_arn=args.glue_allowed_role_arn,
        glue_denied_role_arn=args.glue_denied_role_arn,
        glue_temp_dir=args.glue_temp_dir,
        glue_warehouse_s3_uri=args.glue_warehouse_s3_uri,
    )
    payload = execute_preflight(config) if args.execute else dry_run_payload(config)
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0 if payload["status"] in {"DRY_RUN", "PASS", "BLOCKED", "READ_VALIDATION_PENDING"} else 1

def execute_preflight(config: LakeFormationMatrixConfig) -> dict[str, Any]:
    boto3 = require_boto3()
    glue = boto3.client("glue", region_name=config.region)
    lakeformation = boto3.client("lakeformation", region_name=config.region)
    athena = boto3.client("athena", region_name=config.region)
    findings = {
        "caller_identity": _caller_identity(boto3, config.region),
        "glue_table": _glue_table(glue, config),
        "lakeformation_table_permissions": _lakeformation_permissions(lakeformation, config),
        "lakeformation_data_cells_filters": _data_cells_filters(lakeformation, config),
        "athena_workgroup": _athena_workgroup(athena, config),
        "athena_output": _athena_output(config),
        "consumer_principal": _consumer_principal(config),
    }
    blockers = _blockers(findings)
    athena = athena_validation(boto3, config, blockers)
    glue = glue_validation(boto3, config, blockers)
    status = status_with_validation(blockers, athena, glue)
    return {
        "status": status,
        "config": asdict(config),
        "required_cases": required_cases(),
        "required_prerequisites": required_prerequisites(),
        "findings": findings,
        "athena_read_validation": athena,
        "glue_read_validation": glue,
        "blockers": blockers,
    }

def _caller_identity(boto3: Any, region: str) -> dict[str, Any]:
    return _safe(lambda: boto3.client("sts", region_name=region).get_caller_identity())


def _glue_table(glue: Any, config: LakeFormationMatrixConfig) -> dict[str, Any]:
    def load() -> dict[str, Any]:
        table = glue.get_table(DatabaseName=config.database, Name=config.table).get("Table", {})
        return {
            "exists": True,
            "database": table.get("DatabaseName"),
            "name": table.get("Name"),
            "is_registered_with_lakeformation": bool(table.get("IsRegisteredWithLakeFormation")),
            "table_type": table.get("TableType"),
            "location": (table.get("StorageDescriptor") or {}).get("Location"),
        }

    return _safe(load, missing={"exists": False})


def _lakeformation_permissions(lakeformation: Any, config: LakeFormationMatrixConfig) -> dict[str, Any]:
    def load() -> dict[str, Any]:
        response = lakeformation.list_permissions(
            Resource={"Table": {"CatalogId": config.account_id, "DatabaseName": config.database, "Name": config.table}},
            MaxResults=100,
        )
        permissions = response.get("PrincipalResourcePermissions", [])
        return {"count": len(permissions), "permissions": permissions}

    return _safe(load, missing={"count": 0, "permissions": []})


def _data_cells_filters(lakeformation: Any, config: LakeFormationMatrixConfig) -> dict[str, Any]:
    def load() -> dict[str, Any]:
        response = lakeformation.list_data_cells_filter(
            Table={"CatalogId": config.account_id, "DatabaseName": config.database, "Name": config.table}
        )
        filters = response.get("DataCellsFilters", [])
        return {"count": len(filters), "filters": filters}

    return _safe(load, missing={"count": 0, "filters": []})


def _athena_workgroup(athena: Any, config: LakeFormationMatrixConfig) -> dict[str, Any]:
    def load() -> dict[str, Any]:
        workgroup = athena.get_work_group(WorkGroup=config.athena_workgroup).get("WorkGroup", {})
        result_config = workgroup.get("Configuration", {}).get("ResultConfiguration", {})
        return {
            "exists": True,
            "name": workgroup.get("Name"),
            "state": workgroup.get("State"),
            "output_location": result_config.get("OutputLocation"),
        }

    return _safe(load, missing={"exists": False})


def _athena_output(config: LakeFormationMatrixConfig) -> dict[str, Any]:
    return {"configured": bool(config.athena_output_location), "output_location": config.athena_output_location}


def _consumer_principal(config: LakeFormationMatrixConfig) -> dict[str, Any]:
    principal = config.consumer_principal
    return {
        "present": bool(principal),
        "principal": principal,
        "is_root": bool(principal and principal.endswith(":root")),
    }


def _blockers(findings: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    glue_table = findings["glue_table"]
    if not glue_table.get("exists"):
        blockers.append("Glue table does not exist.")
    elif not glue_table.get("is_registered_with_lakeformation"):
        blockers.append("Glue table is not registered with Lake Formation.")
    principal = findings["consumer_principal"]
    if not principal.get("present"):
        blockers.append("No non-root consumer principal was provided.")
    elif principal.get("is_root"):
        blockers.append("Consumer principal is root; matrix requires a non-root consumer principal.")
    if not findings["lakeformation_data_cells_filters"].get("count"):
        blockers.append("No Lake Formation DataCellsFilter exists for the declared table.")
    if not findings["athena_workgroup"].get("exists"):
        blockers.append("Athena workgroup does not exist.")
    elif not (
        findings["athena_output"].get("output_location")
        or findings["athena_workgroup"].get("output_location")
    ):
        blockers.append("No Athena output location is configured for consumer read checks.")
    for blocker in permission_blockers(findings):
        blockers.append(blocker)
    return blockers

def _safe(loader: Any, *, missing: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        return loader()
    except Exception as exc:  # pragma: no cover - live diagnostic path
        payload = dict(missing or {})
        payload.update({"error_type": type(exc).__name__, "error_message": str(exc)})
        return payload


__all__ = ["LakeFormationMatrixConfig", "dry_run_payload", "execute_preflight", "main"]


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
