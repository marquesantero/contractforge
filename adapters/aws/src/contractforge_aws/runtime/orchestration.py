"""Optional AWS project orchestration runtime helpers."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any

from contractforge_aws.runtime.dependencies import require_boto3
from contractforge_aws.validation import required_text


@dataclass(frozen=True)
class StepFunctionsDeployment:
    name: str
    arn: str
    action: str


@dataclass(frozen=True)
class EventBridgeScheduleDeployment:
    name: str
    arn: str | None
    action: str


@dataclass(frozen=True)
class StepFunctionsExecution:
    execution_arn: str
    start_date: str | None = None


@dataclass(frozen=True)
class StepFunctionsExecutionStatus:
    execution_arn: str
    status: str
    start_date: str | None = None
    stop_date: str | None = None
    error: str | None = None
    cause: str | None = None
    output: str | None = None


def create_or_update_state_machine_payload(
    payload: dict[str, Any],
    *,
    state_machine_arn: str | None = None,
    stepfunctions_client: Any | None = None,
) -> StepFunctionsDeployment:
    client = stepfunctions_client or require_boto3().client("stepfunctions")
    arn = state_machine_arn or _find_state_machine_arn(client, str(payload["name"]))
    return _update_state_machine(client, arn, payload) if arn else _create_state_machine(client, payload)


def create_or_update_schedule_payload(
    payload: dict[str, Any],
    *,
    scheduler_client: Any | None = None,
) -> EventBridgeScheduleDeployment:
    client = scheduler_client or require_boto3().client("scheduler")
    action = "updated" if _schedule_exists(client, payload) else "created"
    response = _schedule_operation(client, action)(**payload)
    arn = response.get("ScheduleArn") if isinstance(response, dict) else None
    return EventBridgeScheduleDeployment(name=str(payload["Name"]), arn=arn, action=action)


def start_state_machine_execution(
    *,
    state_machine_arn: str,
    name: str | None = None,
    input_payload: str | None = None,
    stepfunctions_client: Any | None = None,
) -> StepFunctionsExecution:
    client = stepfunctions_client or require_boto3().client("stepfunctions")
    request = {
        "stateMachineArn": required_text(state_machine_arn, "state_machine_arn"),
        **({"name": name} if name else {}),
        **({"input": input_payload} if input_payload else {}),
    }
    response = client.start_execution(**request)
    arn = str(response.get("executionArn") or "")
    if not arn:
        raise RuntimeError("AWS Step Functions start_execution response did not include executionArn")
    return StepFunctionsExecution(execution_arn=arn, start_date=_optional_text(response.get("startDate")))


def get_state_machine_execution_status(
    *,
    execution_arn: str,
    stepfunctions_client: Any | None = None,
) -> StepFunctionsExecutionStatus:
    client = stepfunctions_client or require_boto3().client("stepfunctions")
    response = client.describe_execution(executionArn=required_text(execution_arn, "execution_arn"))
    return StepFunctionsExecutionStatus(
        execution_arn=str(response.get("executionArn") or execution_arn),
        status=str(response.get("status") or "UNKNOWN"),
        start_date=_optional_text(response.get("startDate")),
        stop_date=_optional_text(response.get("stopDate")),
        error=_optional_text(response.get("error")),
        cause=_optional_text(response.get("cause")),
        output=_optional_text(response.get("output")),
    )


def wait_state_machine_execution(
    *,
    execution_arn: str,
    stepfunctions_client: Any | None = None,
    poll_interval_seconds: float = 10.0,
    max_wait_seconds: float = 3600.0,
) -> StepFunctionsExecutionStatus:
    client = stepfunctions_client or require_boto3().client("stepfunctions")
    deadline = time.monotonic() + max_wait_seconds
    while True:
        status = get_state_machine_execution_status(execution_arn=execution_arn, stepfunctions_client=client)
        if status.status in _TERMINAL_EXECUTION_STATES:
            return _raise_for_failed_execution(status)
        if time.monotonic() >= deadline:
            raise TimeoutError(f"AWS Step Functions execution {execution_arn} did not finish within {max_wait_seconds} seconds")
        time.sleep(max(1.0, poll_interval_seconds))


def _create_state_machine(client: Any, payload: dict[str, Any]) -> StepFunctionsDeployment:
    response = client.create_state_machine(**payload)
    arn = str(response.get("stateMachineArn") or "")
    if not arn:
        raise RuntimeError("AWS Step Functions create_state_machine response did not include stateMachineArn")
    return StepFunctionsDeployment(name=str(payload["name"]), arn=arn, action="created")


def _update_state_machine(client: Any, arn: str, payload: dict[str, Any]) -> StepFunctionsDeployment:
    client.update_state_machine(
        stateMachineArn=arn,
        definition=str(payload["definition"]),
        roleArn=str(payload["roleArn"]),
    )
    return StepFunctionsDeployment(name=str(payload["name"]), arn=arn, action="updated")


def _find_state_machine_arn(client: Any, name: str) -> str | None:
    token: str | None = None
    while True:
        request = {"maxResults": 1000, **({"nextToken": token} if token else {})}
        response = client.list_state_machines(**request)
        for item in response.get("stateMachines", []):
            if item.get("name") == name:
                return str(item.get("stateMachineArn"))
        token = response.get("nextToken")
        if not token:
            return None


def _schedule_exists(client: Any, payload: dict[str, Any]) -> bool:
    try:
        client.get_schedule(**_schedule_identity(payload))
        return True
    except Exception as exc:
        if _is_resource_not_found(exc):
            return False
        raise


def _schedule_operation(client: Any, action: str):
    return {"created": client.create_schedule, "updated": client.update_schedule}[action]


def _schedule_identity(payload: dict[str, Any]) -> dict[str, Any]:
    identity = {"Name": payload["Name"]}
    group_name = payload.get("GroupName")
    return {**identity, **({"GroupName": group_name} if group_name else {})}


def _is_resource_not_found(exc: Exception) -> bool:
    code = getattr(exc, "response", {}).get("Error", {}).get("Code") if hasattr(exc, "response") else None
    return code in {"ResourceNotFoundException", "ResourceNotFound"}


def _raise_for_failed_execution(status: StepFunctionsExecutionStatus) -> StepFunctionsExecutionStatus:
    if status.status == "SUCCEEDED":
        return status
    details = f": {status.error or status.cause}" if status.error or status.cause else ""
    raise RuntimeError(f"AWS Step Functions execution {status.execution_arn} ended with {status.status}{details}")


def _optional_text(value: Any) -> str | None:
    return None if value is None else str(value)


_TERMINAL_EXECUTION_STATES = {"SUCCEEDED", "FAILED", "TIMED_OUT", "ABORTED"}
