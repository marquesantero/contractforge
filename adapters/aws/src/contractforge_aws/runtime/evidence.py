"""Optional AWS evidence table setup helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from contractforge_core.security import redact_text
from contractforge_aws.evidence import (
    render_create_evidence_tables_athena_sql,
    render_create_evidence_tables_sql,
    render_create_state_tables_athena_sql,
    render_create_state_tables_sql,
)


class SqlRunner(Protocol):
    def sql(self, statement: str) -> object:
        ...


@dataclass(frozen=True)
class EvidenceSetupResult:
    database: str
    status: str
    statements_executed: int = 0
    error: str | None = None


def ensure_evidence_tables(
    *,
    runner: SqlRunner,
    database: str = "contractforge_ops",
    include_state: bool = True,
    dialect: str = "spark",
    warehouse_uri: str | None = None,
) -> EvidenceSetupResult:
    executed = 0
    try:
        statements = _ddl_statements(
            database=database,
            include_state=include_state,
            dialect=dialect,
            warehouse_uri=warehouse_uri,
        )
        for statement in statements:
            result = runner.sql(statement)
            if getattr(result, "state", None) == "SUBMITTED":
                raise RuntimeError("Evidence setup requires a waiting SQL runner because DDL statements are ordered")
            executed += 1
    except Exception as exc:
        return EvidenceSetupResult(
            database=database,
            status="FAILED",
            statements_executed=executed,
            error=redact_text(str(exc)),
        )
    return EvidenceSetupResult(database=database, status="READY", statements_executed=executed)


def _ddl_statements(
    *,
    database: str,
    include_state: bool,
    dialect: str = "spark",
    warehouse_uri: str | None = None,
) -> tuple[str, ...]:
    renderer = _DDL_RENDERERS.get(dialect)
    if renderer is None:
        raise ValueError(f"unsupported evidence DDL dialect: {dialect}")
    sql = renderer(database=database, include_state=include_state, warehouse_uri=warehouse_uri)
    return tuple(statement.strip() for statement in sql.split(";") if statement.strip())


def _render_athena_ddl(*, database: str, include_state: bool, warehouse_uri: str | None) -> str:
    if not warehouse_uri:
        raise ValueError("Athena evidence setup requires warehouse_uri for Iceberg table locations")
    sql = render_create_evidence_tables_athena_sql(database=database, warehouse_uri=warehouse_uri)
    if include_state:
        sql += "\n" + render_create_state_tables_athena_sql(database=database, warehouse_uri=warehouse_uri)
    return sql


def _render_spark_ddl(*, database: str, include_state: bool, warehouse_uri: str | None) -> str:
    sql = render_create_evidence_tables_sql(database=database)
    if include_state:
        sql += "\n" + render_create_state_tables_sql(database=database)
    return sql


_DdlRenderer = Callable[..., str]

_DDL_RENDERERS: dict[str, _DdlRenderer] = {
    "athena": _render_athena_ddl,
    "spark": _render_spark_ddl,
}
