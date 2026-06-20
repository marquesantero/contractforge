"""Optional Athena SQL runner for AWS runtime helpers."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from contractforge_aws.runtime.dependencies import require_boto3

_TERMINAL_STATES = {"SUCCEEDED", "FAILED", "CANCELLED"}
_MIN_POLL_INTERVAL_SECONDS = 0.5


@dataclass(frozen=True)
class AthenaQueryResult:
    query_execution_id: str
    state: str
    statement: str
    state_change_reason: str | None = None


class AthenaSqlRunner:
    """Small SQL runner compatible with ContractForge AWS runtime helpers."""

    def __init__(
        self,
        *,
        database: str | None = None,
        output_location: str | None = None,
        workgroup: str | None = None,
        wait: bool = True,
        poll_interval_seconds: float = 2.0,
        max_wait_seconds: float = 300.0,
        athena_client: Any | None = None,
    ) -> None:
        self.database = database
        self.output_location = output_location
        self.workgroup = workgroup
        self.wait = wait
        self.poll_interval_seconds = poll_interval_seconds
        self.max_wait_seconds = max_wait_seconds
        self.client = athena_client or require_boto3().client("athena")

    def sql(self, statement: str) -> AthenaQueryResult:
        query = str(statement or "").strip()
        if not query:
            raise ValueError("Athena SQL statement must not be empty")
        query_id = self._start(query)
        if not self.wait:
            return AthenaQueryResult(query_execution_id=query_id, state="SUBMITTED", statement=query)
        return self._wait(query_id, query)

    def _start(self, statement: str) -> str:
        payload: dict[str, Any] = {"QueryString": statement}
        if self.database and _uses_database_context(statement):
            payload["QueryExecutionContext"] = {"Database": self.database}
        if self.output_location:
            payload["ResultConfiguration"] = {"OutputLocation": self.output_location}
        if self.workgroup:
            payload["WorkGroup"] = self.workgroup
        response = self.client.start_query_execution(**payload)
        query_id = response.get("QueryExecutionId") if isinstance(response, dict) else None
        if not query_id:
            raise RuntimeError("Athena start_query_execution response did not include QueryExecutionId")
        return str(query_id)

    def _wait(self, query_id: str, statement: str) -> AthenaQueryResult:
        deadline = time.monotonic() + self.max_wait_seconds
        while True:
            status = self._status(query_id)
            state = status.get("State")
            reason = status.get("StateChangeReason")
            if state in _TERMINAL_STATES:
                result = AthenaQueryResult(
                    query_execution_id=query_id,
                    state=str(state),
                    statement=statement,
                    state_change_reason=str(reason) if reason else None,
                )
                if state != "SUCCEEDED":
                    raise RuntimeError(f"Athena query {query_id} ended with {state}: {reason or 'no reason provided'}")
                return result
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Athena query {query_id} did not finish within {self.max_wait_seconds} seconds")
            time.sleep(max(_MIN_POLL_INTERVAL_SECONDS, self.poll_interval_seconds))

    def query(self, statement: str) -> list[dict[str, object]]:
        result = self.sql(statement)
        if result.state != "SUCCEEDED":
            raise RuntimeError("Athena query results require a completed query")
        return self._results(result.query_execution_id)

    def _status(self, query_id: str) -> dict[str, Any]:
        response = self.client.get_query_execution(QueryExecutionId=query_id)
        execution = response.get("QueryExecution", {}) if isinstance(response, dict) else {}
        status = execution.get("Status", {}) if isinstance(execution, dict) else {}
        return dict(status) if isinstance(status, dict) else {}

    def _results(self, query_id: str) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        token: str | None = None
        columns: list[str] | None = None
        while True:
            payload: dict[str, Any] = {"QueryExecutionId": query_id}
            if token:
                payload["NextToken"] = token
            response = self.client.get_query_results(**payload)
            result_set = response.get("ResultSet", {}) if isinstance(response, dict) else {}
            result_rows = result_set.get("Rows", []) if isinstance(result_set, dict) else []
            columns, rows = _append_result_rows(result_rows, columns, rows)
            token = response.get("NextToken") if isinstance(response, dict) else None
            if not token:
                return rows


def _uses_database_context(statement: str) -> bool:
    return not statement.lstrip().upper().startswith("CREATE DATABASE")


def _append_result_rows(
    result_rows: list[Any],
    columns: list[str] | None,
    rows: list[dict[str, object]],
) -> tuple[list[str] | None, list[dict[str, object]]]:
    for raw_row in result_rows:
        values = [_cell_value(cell) for cell in raw_row.get("Data", [])]
        if columns is None:
            columns = [str(value or "") for value in values]
            continue
        rows.append({columns[index]: values[index] if index < len(values) else None for index in range(len(columns))})
    return columns, rows


def _cell_value(cell: Any) -> str | None:
    return cell.get("VarCharValue") if isinstance(cell, dict) else None
