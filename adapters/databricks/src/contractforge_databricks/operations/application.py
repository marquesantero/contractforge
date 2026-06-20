"""Record Databricks operations metadata with an injected SQL runner."""

from __future__ import annotations

from datetime import datetime

from contractforge_core.results import OperationsRecordResult
from contractforge_core.semantic import SemanticContract
from contractforge_databricks.environment import DatabricksEnvironment
from contractforge_databricks.execution.sql_merge import SqlRunner
from contractforge_databricks.operations.sql import has_operations_metadata, render_operations_insert_sql
from contractforge_databricks.security import exception_message


def record_operations_contract(
    *,
    runner: SqlRunner,
    contract: SemanticContract,
    environment: DatabricksEnvironment | None = None,
    run_id: str = "${run_id}",
    recorded_at_utc: datetime | None = None,
) -> OperationsRecordResult:
    if not has_operations_metadata(contract):
        return OperationsRecordResult(status="NOT_CONFIGURED")
    env = environment or DatabricksEnvironment()
    statement = render_operations_insert_sql(
        contract,
        run_id=run_id,
        status="RECORDED",
        recorded_at_utc=recorded_at_utc,
        catalog=env.evidence_catalog,
        schema=env.evidence_schema,
    )
    try:
        runner.sql(statement)
    except Exception as exc:
        return OperationsRecordResult(status="FAILED", sql=statement, error=exception_message(exc))
    return OperationsRecordResult(status="RECORDED", sql=statement)
