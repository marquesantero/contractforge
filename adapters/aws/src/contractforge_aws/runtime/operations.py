"""Optional AWS operations evidence recording helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from contractforge_core.security import redact_text


class SqlRunner(Protocol):
    def sql(self, statement: str) -> object:
        ...


@dataclass(frozen=True)
class OperationsRecordResult:
    status: str
    sql: str | None = None
    error: str | None = None


def record_operations_sql(*, runner: SqlRunner, statement: str) -> OperationsRecordResult:
    sql = statement.strip()
    if not sql or sql.startswith("-- No operations metadata declared."):
        return OperationsRecordResult(status="NOT_CONFIGURED")
    try:
        result = runner.sql(sql)
    except Exception as exc:
        return OperationsRecordResult(status="FAILED", sql=sql, error=redact_text(str(exc)))
    if getattr(result, "state", None) == "SUBMITTED":
        return OperationsRecordResult(status="SUBMITTED", sql=sql)
    return OperationsRecordResult(status="RECORDED", sql=sql)
