"""AWS evidence audit helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class QueryRunner(Protocol):
    def query(self, statement: str) -> list[dict[str, object]]:
        ...


@dataclass(frozen=True)
class EvidenceAuditCheck:
    name: str
    statement: str
    rows: tuple[dict[str, object], ...]


@dataclass(frozen=True)
class EvidenceAuditResult:
    database: str
    status: str
    checks: tuple[EvidenceAuditCheck, ...]


def audit_evidence_tables(*, runner: QueryRunner, database: str) -> EvidenceAuditResult:
    checks = tuple(
        EvidenceAuditCheck(name=name, statement=statement, rows=tuple(runner.query(statement)))
        for name, statement in evidence_audit_queries(database=database).items()
    )
    return EvidenceAuditResult(database=database, status="AUDITED", checks=checks)


def evidence_audit_queries(*, database: str) -> dict[str, str]:
    quoted = _quote_identifier(database)
    return {
        "runs_by_status": "\n".join(
            [
                "SELECT status, count(*) AS runs",
                f'FROM "{quoted}"."ctrl_ingestion_runs"',
                "GROUP BY status",
            ]
        ),
        "runs_by_quality_status": "\n".join(
            [
                "SELECT quality_status, count(*) AS runs",
                f'FROM "{quoted}"."ctrl_ingestion_runs"',
                "GROUP BY quality_status",
            ]
        ),
        "quality_by_target": "\n".join(
            [
                "SELECT target_table, count(*) AS quality_rows",
                f'FROM "{quoted}"."ctrl_ingestion_quality"',
                "GROUP BY target_table",
            ]
        ),
        "quarantine_by_target": "\n".join(
            [
                "SELECT target_table, count(*) AS quarantined_rows",
                f'FROM "{quoted}"."ctrl_ingestion_quarantine"',
                "GROUP BY target_table",
            ]
        ),
        "errors_by_target": "\n".join(
            [
                "SELECT target_table, count(*) AS errors",
                f'FROM "{quoted}"."ctrl_ingestion_errors"',
                "GROUP BY target_table",
            ]
        ),
        "cost_by_target": "\n".join(
            [
                "SELECT cost.target_table, count(*) AS cost_rows, sum(cost.signal_value) AS glue_dpu_seconds",
                f'FROM "{quoted}"."ctrl_ingestion_cost" cost',
                f'INNER JOIN "{quoted}"."ctrl_ingestion_runs" runs',
                "  ON runs.run_id = cost.run_id",
                " AND runs.target_table = cost.target_table",
                "WHERE cost.signal_name = 'glue_dpu_seconds'",
                "GROUP BY cost.target_table",
            ]
        ),
    }


def _quote_identifier(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("database must not be empty")
    return text.replace('"', '""')
