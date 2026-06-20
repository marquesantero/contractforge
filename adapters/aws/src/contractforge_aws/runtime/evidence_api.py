"""Runtime-facing AWS evidence setup helpers."""

from __future__ import annotations

from contractforge_aws.runtime.evidence import EvidenceSetupResult, SqlRunner, ensure_evidence_tables


def ensure_aws_evidence_tables(
    *,
    runner: SqlRunner,
    database: str = "contractforge_ops",
    include_state: bool = True,
    dialect: str = "spark",
    warehouse_uri: str | None = None,
) -> EvidenceSetupResult:
    return ensure_evidence_tables(
        runner=runner,
        database=database,
        include_state=include_state,
        dialect=dialect,
        warehouse_uri=warehouse_uri,
    )


__all__ = ["ensure_aws_evidence_tables"]
