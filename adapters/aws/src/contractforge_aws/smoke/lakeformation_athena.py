"""Athena read checks for the Lake Formation consumer matrix."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Any

from contractforge_core.security import redact_value


@dataclass(frozen=True)
class AthenaReadValidationConfig:
    region: str
    database: str
    table: str
    workgroup: str
    output_location: str | None
    allowed_role_arn: str | None
    denied_role_arn: str | None
    poll_interval_seconds: float = 2.0
    max_wait_seconds: float = 60.0


def validate_athena_reads(boto3: Any, config: AthenaReadValidationConfig) -> dict[str, Any]:
    cases: dict[str, Any] = {}
    if not config.output_location:
        return {
            "status": "READ_VALIDATION_PENDING",
            "config": asdict(config),
            "cases": cases,
            "pending": ["Athena output location is required for read validation."],
        }
    cases["allowed_role_count"] = _run_case(boto3, config, role_arn=config.allowed_role_arn, expect_success=True)
    cases["denied_role_count"] = _run_case(boto3, config, role_arn=config.denied_role_arn, expect_success=False)
    pending = [
        case.get("reason")
        for case in cases.values()
        if case.get("status") == "READ_VALIDATION_PENDING" and case.get("reason")
    ]
    failures = [case for case in cases.values() if case.get("status") == "FAIL"]
    if failures:
        status = "FAIL"
    elif pending:
        status = "READ_VALIDATION_PENDING"
    else:
        status = "PASS"
    return {"status": status, "config": asdict(config), "cases": cases, "pending": pending}


def _run_case(boto3: Any, config: AthenaReadValidationConfig, *, role_arn: str | None, expect_success: bool) -> dict[str, Any]:
    if not role_arn:
        return {"status": "READ_VALIDATION_PENDING", "reason": "No role ARN provided for this read case."}
    try:
        athena = _athena_client_for_role(boto3, config.region, role_arn)
        query_id = _start_query(athena, config)
        execution = _wait_for_query(athena, query_id, config)
        state = ((execution.get("QueryExecution") or {}).get("Status") or {}).get("State")
        if state == "SUCCEEDED":
            row_count = _row_count(athena, query_id)
            return _success_result(query_id, row_count, expect_success=expect_success)
        return _terminal_failure_result(execution, query_id, expect_success=expect_success)
    except Exception as exc:  # pragma: no cover - live AWS diagnostic path
        return _exception_result(exc, expect_success=expect_success)


def _athena_client_for_role(boto3: Any, region: str, role_arn: str) -> Any:
    sts = boto3.client("sts", region_name=region)
    response = sts.assume_role(RoleArn=role_arn, RoleSessionName="contractforge-lf-athena-smoke")
    credentials = response["Credentials"]
    session = boto3.Session(
        aws_access_key_id=credentials["AccessKeyId"],
        aws_secret_access_key=credentials["SecretAccessKey"],
        aws_session_token=credentials["SessionToken"],
        region_name=region,
    )
    return session.client("athena", region_name=region)


def _start_query(athena: Any, config: AthenaReadValidationConfig) -> str:
    response = athena.start_query_execution(
        QueryString=f'SELECT COUNT(*) AS c FROM "{_quote(config.database)}"."{_quote(config.table)}"',
        WorkGroup=config.workgroup,
        ResultConfiguration={"OutputLocation": config.output_location},
    )
    return str(response["QueryExecutionId"])


def _wait_for_query(athena: Any, query_id: str, config: AthenaReadValidationConfig) -> dict[str, Any]:
    deadline = time.monotonic() + config.max_wait_seconds
    while True:
        execution = athena.get_query_execution(QueryExecutionId=query_id)
        state = ((execution.get("QueryExecution") or {}).get("Status") or {}).get("State")
        if state in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return execution
        if time.monotonic() >= deadline:
            return {
                "QueryExecution": {
                    "QueryExecutionId": query_id,
                    "Status": {"State": "TIMEOUT", "StateChangeReason": "Timed out waiting for Athena query."},
                }
            }
        time.sleep(config.poll_interval_seconds)


def _row_count(athena: Any, query_id: str) -> int | None:
    response = athena.get_query_results(QueryExecutionId=query_id, MaxResults=2)
    rows = (response.get("ResultSet") or {}).get("Rows") or []
    if len(rows) < 2:
        return None
    value = ((rows[1].get("Data") or [{}])[0]).get("VarCharValue")
    return int(value) if value is not None else None


def _success_result(query_id: str, row_count: int | None, *, expect_success: bool) -> dict[str, Any]:
    if expect_success:
        return {"status": "PASS", "query_id": query_id, "state": "SUCCEEDED", "row_count": row_count}
    return {
        "status": "FAIL",
        "query_id": query_id,
        "state": "SUCCEEDED",
        "row_count": row_count,
        "reason": "Denied role query succeeded; Lake Formation filter/isolation was not proven.",
    }


def _terminal_failure_result(execution: dict[str, Any], query_id: str, *, expect_success: bool) -> dict[str, Any]:
    status = (execution.get("QueryExecution") or {}).get("Status") or {}
    state = status.get("State")
    reason = redact_value(status.get("StateChangeReason") or "Athena query did not succeed.")
    if expect_success:
        return {"status": "FAIL", "query_id": query_id, "state": state, "reason": reason}
    return {"status": "PASS", "query_id": query_id, "state": state, "expected_failure": True, "reason": reason}


def _exception_result(exc: Exception, *, expect_success: bool) -> dict[str, Any]:
    reason = redact_value(str(exc))
    if "AssumeRole" in str(exc) and "root accounts" in str(exc):
        return {"status": "READ_VALIDATION_PENDING", "error_type": type(exc).__name__, "reason": reason}
    status = "FAIL" if expect_success else "PASS"
    payload = {"status": status, "error_type": type(exc).__name__, "reason": reason}
    if not expect_success:
        payload["expected_failure"] = True
    return payload


def _quote(identifier: str) -> str:
    return identifier.replace('"', '""')


__all__ = ["AthenaReadValidationConfig", "validate_athena_reads"]
