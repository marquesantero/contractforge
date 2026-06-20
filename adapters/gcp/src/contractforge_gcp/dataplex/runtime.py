"""Optional Dataplex DataScan runtime helpers."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from typing import Any

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_gcp.dataplex.quality import render_dataplex_data_quality_execution_plan
from contractforge_gcp.environment import GCPEnvironment

CommandRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]
HttpRunner = Callable[[str, str, dict[str, str], dict[str, Any] | None], dict[str, Any]]


def run_dataplex_data_quality(
    contract: dict[str, Any],
    *,
    environment: dict[str, Any] | None = None,
    execute: bool = False,
    wait: bool = False,
    readback: bool = False,
    cleanup: bool = False,
    timeout_seconds: int = 300,
    poll_interval_seconds: int = 10,
    runner: CommandRunner | None = None,
    http_runner: HttpRunner | None = None,
) -> dict[str, Any]:
    """Render or execute the Dataplex DataScan path for a contract."""

    env = GCPEnvironment.from_contract(environment)
    semantic = semantic_contract_from_mapping(contract)
    plan_body = render_dataplex_data_quality_execution_plan(semantic, env)
    if not plan_body:
        return {
            "type": "dataplex_data_quality",
            "status": "SKIPPED",
            "reason": "contract_has_no_quality_rules",
        }
    plan = json.loads(plan_body)
    payload: dict[str, Any] = {
        "type": "dataplex_data_quality",
        "status": "PLANNED_NOT_EXECUTED",
        "execution_included": False,
        "plan": plan,
        "review_boundaries": [
            "This command validates native Dataplex data-quality execution/readback only.",
            "Native Dataplex lineage event publication/readback and Knowledge Catalog/Dataplex aspect execution/readback are available through the explicit dataplex-lineage-aspects command.",
        ],
    }
    if not execute:
        return payload

    command_runner = runner or _run_command
    requester = http_runner or _http_json
    try:
        token = _access_token(command_runner)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        payload["status"] = "RUNNING"
        payload["execution_included"] = True
        payload["create"] = _create_data_scan(
            requester,
            headers,
            plan,
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=poll_interval_seconds,
        )
        payload["data_scan"] = requester("GET", plan["rest"]["get_data_scan"]["url"], headers, None)
        run_result = requester("POST", plan["rest"]["run"]["url"], headers, {})
        payload["run"] = run_result
        job_name = _job_name(run_result)
        if job_name:
            payload["job_name"] = job_name
        if wait:
            payload["job"] = _poll_job(
                requester,
                headers,
                _job_url(plan, job_name),
                timeout_seconds=timeout_seconds,
                poll_interval_seconds=poll_interval_seconds,
            )
        if readback:
            payload["readback"] = _read_bigquery_export(command_runner, plan)
        if cleanup:
            payload["cleanup"] = _delete_data_scan(
                requester,
                headers,
                plan,
                timeout_seconds=timeout_seconds,
                poll_interval_seconds=poll_interval_seconds,
            )
        payload["status"] = _overall_status(payload)
    except RuntimeError as exc:
        payload["status"] = "BLOCKED"
        payload["error_message"] = str(exc)
    return payload


def _create_data_scan(
    requester: HttpRunner,
    headers: dict[str, str],
    plan: dict[str, Any],
    *,
    timeout_seconds: int,
    poll_interval_seconds: int,
) -> dict[str, Any]:
    try:
        result = requester("POST", plan["rest"]["create"]["url"], headers, plan["rest"]["create"]["body"])
    except RuntimeError as exc:
        if _is_already_exists(str(exc)):
            return {"status": "SKIPPED", "reason": "data_scan_already_exists", "message": str(exc)}
        raise
    operation = _poll_operation(
        requester,
        headers,
        result,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
    )
    return {"status": "SUCCEEDED", "operation": operation}


def _poll_operation(
    requester: HttpRunner,
    headers: dict[str, str],
    operation: dict[str, Any],
    *,
    timeout_seconds: int,
    poll_interval_seconds: int,
) -> dict[str, Any]:
    name = operation.get("name")
    if operation.get("done") is True or not isinstance(name, str) or not name.strip():
        return operation
    url = f"https://dataplex.googleapis.com/v1/{name}"
    deadline = time.monotonic() + max(1, timeout_seconds)
    interval = max(1, poll_interval_seconds)
    last: dict[str, Any] = operation
    while time.monotonic() <= deadline:
        current = requester("GET", url, headers, None)
        if current.get("done") is True:
            return current
        last = current
        time.sleep(interval)
    return {"status": "UNKNOWN", "operation": operation, "last_operation": last, "reason": "operation_poll_timeout"}


def _poll_job(
    requester: HttpRunner,
    headers: dict[str, str],
    url: str,
    *,
    timeout_seconds: int,
    poll_interval_seconds: int,
) -> dict[str, Any]:
    deadline = time.monotonic() + max(1, timeout_seconds)
    interval = max(1, poll_interval_seconds)
    last: dict[str, Any] = {}
    while time.monotonic() <= deadline:
        last = requester("GET", url, headers, None)
        state = str(last.get("state") or "").upper()
        if state in {"SUCCEEDED", "FAILED", "CANCELLED", "CANCELING"}:
            return last
        time.sleep(interval)
    return {"status": "UNKNOWN", "reason": "job_poll_timeout", "last_job": last}


def _read_bigquery_export(runner: CommandRunner, plan: dict[str, Any]) -> dict[str, Any]:
    project_id = str(plan["data_scan"]["name"]).split("/")[1]
    location = str(plan["data_scan"]["location"]).upper()
    sql = str(plan["readback"]["bigquery_export_query"])
    command = [
        "bq",
        f"--project_id={project_id}",
        f"--location={location}",
        "--format=json",
        "query",
        "--use_legacy_sql=false",
        _bq_sql_argument(sql),
    ]
    completed = runner(tuple(command))
    if completed.returncode != 0:
        raise RuntimeError(_command_error(completed, fallback="Dataplex BigQuery export readback failed"))
    rows = _parse_json_rows(completed.stdout)
    return {
        "status": "SUCCEEDED",
        "row_count": len(rows),
        "query": sql,
        "rows": rows,
    }


def _delete_data_scan(
    requester: HttpRunner,
    headers: dict[str, str],
    plan: dict[str, Any],
    *,
    timeout_seconds: int,
    poll_interval_seconds: int,
) -> dict[str, Any]:
    try:
        operation = requester("DELETE", plan["rest"]["delete"]["url"], headers, None)
        return _poll_operation(
            requester,
            headers,
            operation,
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=poll_interval_seconds,
        )
    except RuntimeError as exc:
        if _is_not_found(str(exc)):
            return {"status": "SKIPPED", "reason": "data_scan_not_found", "message": str(exc)}
        raise


def _http_json(
    method: str,
    url: str,
    headers: dict[str, str],
    body: dict[str, Any] | None,
) -> dict[str, Any]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    for attempt in range(8):
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return _json_object(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="replace")
            if exc.code in {429, 500, 503} and attempt < 7:
                time.sleep(_retry_delay(exc, attempt))
                continue
            raise RuntimeError(f"Dataplex REST {method} {url} failed with HTTP {exc.code}: {_redact(message)}") from exc
        except urllib.error.URLError as exc:
            if attempt < 7:
                time.sleep(min(60, 2**attempt))
                continue
            raise RuntimeError(f"Dataplex REST {method} {url} failed: {_redact(str(exc.reason))}") from exc
    raise RuntimeError(f"Dataplex REST {method} {url} failed after retries")


def _access_token(runner: CommandRunner) -> str:
    completed = runner(("gcloud", "auth", "print-access-token"))
    if completed.returncode != 0:
        raise RuntimeError(_command_error(completed, fallback="gcloud auth print-access-token failed"))
    token = completed.stdout.strip()
    if not token:
        raise RuntimeError("gcloud auth print-access-token returned an empty token")
    return token


def _run_command(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    resolved = list(command)
    if resolved:
        resolved[0] = shutil.which(resolved[0]) or resolved[0]
    return subprocess.run(resolved, check=False, capture_output=True, text=True)


def _job_name(run_result: dict[str, Any]) -> str | None:
    job = run_result.get("job") if isinstance(run_result.get("job"), dict) else {}
    name = job.get("name")
    return str(name).strip() if name else None


def _job_url(plan: dict[str, Any], job_name: str | None) -> str:
    if job_name:
        return f"https://dataplex.googleapis.com/v1/{job_name}"
    return str(plan["rest"]["get_job_template"]["url"]).replace("{job_id}", "latest")


def _overall_status(payload: dict[str, Any]) -> str:
    job = payload.get("job") if isinstance(payload.get("job"), dict) else {}
    if str(job.get("state") or "").upper() == "FAILED":
        return "FAILED"
    if str(job.get("state") or "").upper() == "CANCELLED":
        return "FAILED"
    if payload.get("readback") and payload["readback"].get("status") != "SUCCEEDED":
        return "FAILED"
    return "SUCCEEDED"


def _json_object(value: str) -> dict[str, Any]:
    if not value.strip():
        return {}
    payload = json.loads(value)
    return payload if isinstance(payload, dict) else {"result": payload}


def _parse_json_rows(value: str) -> list[dict[str, Any]]:
    if not value.strip():
        return []
    payload = json.loads(value)
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        return [payload]
    return [{"result": payload}]


def _command_error(completed: subprocess.CompletedProcess[str], *, fallback: str) -> str:
    return _redact((completed.stderr or completed.stdout or fallback).strip())


def _redact(value: str) -> str:
    return re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "<redacted-email>", value)


def _is_already_exists(value: str) -> bool:
    normalized = value.lower()
    return "already_exists" in normalized or "already exists" in normalized or "http 409" in normalized


def _is_not_found(value: str) -> bool:
    normalized = value.lower()
    return "not_found" in normalized or "not found" in normalized or "http 404" in normalized


def _retry_delay(exc: urllib.error.HTTPError, attempt: int) -> int:
    retry_after = exc.headers.get("Retry-After")
    if retry_after and retry_after.isdigit():
        return max(1, min(90, int(retry_after)))
    if exc.code == 429:
        return 60
    return min(60, 2**attempt)


def _bq_sql_argument(sql: str) -> str:
    return " ".join(line.strip() for line in sql.splitlines() if line.strip())
