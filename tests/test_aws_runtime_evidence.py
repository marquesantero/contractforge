from __future__ import annotations

import pytest

from contractforge_aws import AthenaSqlRunner, ensure_aws_evidence_tables
from contractforge_aws.runtime import audit_evidence_tables
import contractforge_aws.runtime.athena as athena_runtime
from contractforge_aws.runtime.athena import AthenaQueryResult


class RecordingRunner:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.statements: list[str] = []

    def sql(self, statement: str) -> None:
        self.statements.append(statement)
        if self.fail:
            raise RuntimeError("query engine unavailable")


class FakeAthenaClient:
    def __init__(self, states: list[dict] | None = None) -> None:
        self.states = states or [{"State": "SUCCEEDED"}]
        self.started: list[dict] = []
        self.status_calls: list[str] = []

    def start_query_execution(self, **kwargs: dict) -> dict:
        self.started.append(kwargs)
        return {"QueryExecutionId": "q-1"}

    def get_query_execution(self, QueryExecutionId: str) -> dict:
        self.status_calls.append(QueryExecutionId)
        status = self.states.pop(0) if len(self.states) > 1 else self.states[0]
        return {"QueryExecution": {"Status": status}}


def test_ensure_aws_evidence_tables_executes_evidence_and_state_ddl() -> None:
    runner = RecordingRunner()

    result = ensure_aws_evidence_tables(runner=runner, database="lake_ops")

    assert result.status == "READY"
    assert result.database == "lake_ops"
    assert result.statements_executed == len(runner.statements)
    assert any("CREATE DATABASE IF NOT EXISTS glue_catalog.`lake_ops`" in statement for statement in runner.statements)
    assert any("ctrl_ingestion_runs" in statement for statement in runner.statements)
    assert any("ctrl_ingestion_state" in statement for statement in runner.statements)
    assert all(statement.strip() and not statement.strip().endswith(";") for statement in runner.statements)


def test_ensure_aws_evidence_tables_can_render_athena_iceberg_ddl() -> None:
    runner = RecordingRunner()

    result = ensure_aws_evidence_tables(
        runner=runner,
        database="lake_ops",
        dialect="athena",
        warehouse_uri="s3://warehouse/evidence",
    )

    assert result.status == "READY"
    assert any("CREATE DATABASE IF NOT EXISTS lake_ops" in statement for statement in runner.statements)
    assert any("lake_ops.ctrl_ingestion_runs" in statement for statement in runner.statements)
    assert not any("`" in statement for statement in runner.statements)
    assert any("LOCATION 's3://warehouse/evidence/lake_ops.db/ctrl_ingestion_runs/'" in statement for statement in runner.statements)
    assert any("TBLPROPERTIES ('table_type'='ICEBERG', 'format'='parquet')" in statement for statement in runner.statements)
    assert not any("NOT NULL" in statement for statement in runner.statements)
    assert not any("glue_catalog" in statement for statement in runner.statements)
    assert not any("USING iceberg" in statement for statement in runner.statements)


def test_ensure_aws_evidence_tables_requires_warehouse_for_athena_ddl() -> None:
    result = ensure_aws_evidence_tables(runner=RecordingRunner(), database="lake_ops", dialect="athena")

    assert result.status == "FAILED"
    assert result.statements_executed == 0
    assert "warehouse_uri" in str(result.error)


def test_ensure_aws_evidence_tables_can_skip_state_tables() -> None:
    runner = RecordingRunner()

    result = ensure_aws_evidence_tables(runner=runner, database="lake_ops", include_state=False)

    assert result.status == "READY"
    assert result.statements_executed == len(runner.statements)
    assert any("ctrl_ingestion_runs" in statement for statement in runner.statements)
    assert not any("ctrl_ingestion_state" in statement for statement in runner.statements)


def test_ensure_aws_evidence_tables_reports_runner_failure() -> None:
    result = ensure_aws_evidence_tables(runner=RecordingRunner(fail=True), database="lake_ops")

    assert result.status == "FAILED"
    assert result.error == "query engine unavailable"


def test_ensure_aws_evidence_tables_rejects_async_runner() -> None:
    class AsyncRunner:
        def __init__(self) -> None:
            self.statements: list[str] = []

        def sql(self, statement: str) -> AthenaQueryResult:
            self.statements.append(statement)
            return AthenaQueryResult(query_execution_id="q-1", state="SUBMITTED", statement=statement)

    runner = AsyncRunner()
    result = ensure_aws_evidence_tables(runner=runner, database="lake_ops", include_state=False)

    assert result.status == "FAILED"
    assert result.statements_executed == 0
    assert "requires a waiting SQL runner" in str(result.error)


def test_athena_sql_runner_starts_and_waits_for_query(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeAthenaClient(states=[{"State": "RUNNING"}, {"State": "SUCCEEDED"}])
    sleeps: list[float] = []
    monkeypatch.setattr(athena_runtime.time, "sleep", sleeps.append)
    runner = AthenaSqlRunner(
        database="lake_ops",
        output_location="s3://query-results/",
        workgroup="contractforge",
        poll_interval_seconds=0,
        athena_client=client,
    )

    result = runner.sql("CREATE DATABASE IF NOT EXISTS lake_ops")

    assert result.query_execution_id == "q-1"
    assert result.state == "SUCCEEDED"
    assert client.started == [
        {
            "QueryString": "CREATE DATABASE IF NOT EXISTS lake_ops",
            "ResultConfiguration": {"OutputLocation": "s3://query-results/"},
            "WorkGroup": "contractforge",
        }
    ]
    assert client.status_calls == ["q-1", "q-1"]
    assert sleeps == [0.5]


def test_athena_sql_runner_uses_context_for_non_database_bootstrap_queries() -> None:
    client = FakeAthenaClient()
    runner = AthenaSqlRunner(database="lake_ops", output_location="s3://query-results/", athena_client=client)

    runner.sql("CREATE TABLE IF NOT EXISTS glue_catalog.`lake_ops`.`ctrl_ingestion_runs` (id STRING)")

    assert client.started[0]["QueryExecutionContext"] == {"Database": "lake_ops"}


def test_athena_sql_runner_can_submit_without_waiting() -> None:
    client = FakeAthenaClient()
    runner = AthenaSqlRunner(wait=False, athena_client=client)

    result = runner.sql("SELECT 1")

    assert result.state == "SUBMITTED"
    assert client.status_calls == []


def test_athena_sql_runner_raises_on_failed_query() -> None:
    runner = AthenaSqlRunner(
        poll_interval_seconds=0,
        athena_client=FakeAthenaClient(states=[{"State": "FAILED", "StateChangeReason": "bad sql"}]),
    )

    with pytest.raises(RuntimeError, match="bad sql"):
        runner.sql("SELECT broken")


def test_audit_evidence_tables_includes_cost_signal_check() -> None:
    class Runner:
        def __init__(self) -> None:
            self.queries: list[str] = []

        def query(self, statement: str):
            self.queries.append(statement)
            return []

    runner = Runner()
    result = audit_evidence_tables(runner=runner, database="lake_ops")
    checks = {check.name: check.statement for check in result.checks}

    assert "cost_by_target" in checks
    assert '"lake_ops"."ctrl_ingestion_cost"' in checks["cost_by_target"]
    assert '"lake_ops"."ctrl_ingestion_runs"' in checks["cost_by_target"]
    assert "INNER JOIN" in checks["cost_by_target"]
    assert "sum(cost.signal_value) AS glue_dpu_seconds" in checks["cost_by_target"]
