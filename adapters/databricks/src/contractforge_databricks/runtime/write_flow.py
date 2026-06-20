"""Prepared write flow for Databricks runtime ingestion."""

from __future__ import annotations

from time import perf_counter
from typing import Any
from typing import NamedTuple

from contractforge_core.execution import ExecutionOutcome
from contractforge_core.quality import QualityRuleResult
from contractforge_core.runtime import PreparedInput, QueryOne, rows_written_from_outcome
from contractforge_core.semantic import SemanticContract
from contractforge_databricks.evidence import EvidenceWriter
from contractforge_databricks.execution import SqlRunner, with_delta_retry
from contractforge_databricks.runtime.governance import apply_runtime_governance
from contractforge_databricks.runtime.maintenance import run_post_write_maintenance
from contractforge_databricks.runtime.merge_validation import validate_merge_source_safety
from contractforge_databricks.runtime.models import DatabricksIngestOptions
from contractforge_databricks.runtime.partitioning import replace_partition_predicate, target_partition_predicate
from contractforge_databricks.runtime.schema import setup_and_sync_schema
from contractforge_databricks.runtime.utils import utc_now_str
from contractforge_databricks.runtime.write import execute_prepared_write


class WriteFlowResult(NamedTuple):
    outcome: ExecutionOutcome
    logical_rows_written: int
    schema_changes: dict[str, Any]
    governance_results: dict[str, Any]
    write_started_at: str
    write_finished_at: str
    stage_durations: dict[str, float]


def execute_runtime_write_flow(
    *,
    runner: SqlRunner,
    evidence: EvidenceWriter,
    contract: SemanticContract,
    prepared: PreparedInput,
    opts: DatabricksIngestOptions,
    run_id: str,
    target: str,
    query_one: QueryOne | None = None,
    quality_results: tuple[QualityRuleResult, ...] = (),
) -> WriteFlowResult:
    stage_durations: dict[str, float] = {}
    schema_start = perf_counter()
    schema_changes = setup_and_sync_schema(
        runner=runner,
        evidence=evidence,
        contract=contract,
        prepared=prepared,
        run_id=run_id,
        ensure_table=opts.ensure_table,
        target_schema=opts.target_schema,
    )
    stage_durations["schema"] = _elapsed(schema_start)
    validation_start = perf_counter()
    validate_merge_source_safety(
        contract=contract,
        prepared=prepared,
        query_one=query_one,
        quality_results=quality_results,
    )
    stage_durations["preflight"] = _elapsed(validation_start)
    write_started_at = _utc_now()
    write_start = perf_counter()
    outcome = with_delta_retry(
        lambda: execute_prepared_write(
            runner=runner,
            contract=contract,
            prepared=prepared,
            replace_partition_predicate=replace_partition_predicate(
                contract=contract,
                prepared=prepared,
                query_one=query_one,
            ),
            target_schema=opts.target_schema,
            query_one=query_one,
            target_partition_predicate=target_partition_predicate(
                contract=contract,
                prepared=prepared,
                query_one=query_one,
            ),
        ),
        attempts=_retry_attempts(contract),
        backoff_seconds=_retry_backoff_seconds(contract),
        jitter=lambda: 0.0,
    )
    write_finished_at = _utc_now()
    stage_durations["write"] = _elapsed(write_start)
    logical_rows_written = rows_written_from_outcome(prepared, outcome)
    maintenance_start = perf_counter()
    run_post_write_maintenance(
        runner=runner,
        contract=contract,
        target_table=target,
        outcome=outcome,
        rows_written=logical_rows_written,
    )
    stage_durations["maintenance"] = _elapsed(maintenance_start)
    governance_start = perf_counter()
    governance_results = apply_runtime_governance(
        runner=runner,
        contract=contract,
        run_id=run_id,
        evidence_catalog=opts.catalog,
        evidence_schema=opts.schema,
    )
    stage_durations["governance"] = _elapsed(governance_start)
    return WriteFlowResult(
        outcome,
        logical_rows_written,
        schema_changes,
        governance_results,
        write_started_at,
        write_finished_at,
        stage_durations,
    )


def _retry_attempts(contract: SemanticContract) -> int:
    metadata = contract.operations.metadata if contract.operations and contract.operations.metadata else {}
    value = metadata.get("retry_attempts", 1)
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return 1


def _retry_backoff_seconds(contract: SemanticContract) -> float:
    metadata = contract.operations.metadata if contract.operations and contract.operations.metadata else {}
    value = metadata.get("retry_backoff_seconds", 1.0)
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return 1.0


def _utc_now() -> str:
    return utc_now_str()


def _elapsed(start: float) -> float:
    return round(perf_counter() - start, 6)
