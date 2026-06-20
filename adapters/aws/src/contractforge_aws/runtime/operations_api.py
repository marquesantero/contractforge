"""Runtime-facing AWS operations helpers."""

from __future__ import annotations

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_aws.capabilities import AWS_SUBTARGET_GLUE_ICEBERG
from contractforge_aws.operations import render_operations_insert_sql
from contractforge_aws.rendering.names import glue_database_name
from contractforge_aws.runtime.operations import OperationsRecordResult, SqlRunner, record_operations_sql
from contractforge_aws.subtargets import validate_aws_subtarget


def record_aws_operations_contract(
    *,
    runner: SqlRunner,
    contract: dict,
    database: str | None = None,
    run_id: str = "${run_id}",
    subtarget: str = AWS_SUBTARGET_GLUE_ICEBERG,
) -> OperationsRecordResult:
    validate_aws_subtarget(subtarget)
    semantic = semantic_contract_from_mapping(contract)
    evidence_database = database or f"{glue_database_name(semantic)}_ops"
    statement = render_operations_insert_sql(
        semantic,
        database=evidence_database,
        run_id=run_id,
        status="RECORDED",
    )
    return record_operations_sql(runner=runner, statement=statement)


__all__ = ["record_aws_operations_contract"]
