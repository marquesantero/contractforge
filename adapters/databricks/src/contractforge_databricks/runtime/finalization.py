"""Finalize Databricks runtime ingestion with evidence and state."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from contractforge_core.config import CTRL_SCHEMA_VERSION, FRAMEWORK_VERSION
from contractforge_core.quality import QualityRuleResult
from contractforge_core.runtime import PreparedInput, QuarantineReference
from contractforge_core.semantic import SemanticContract
from contractforge_databricks.evidence import EvidenceWriter, SourceMetadataEvidenceRecord
from contractforge_databricks.quality import render_quality_result_insert_sql, render_quarantine_reference_insert_sql
from contractforge_databricks.runtime.models import DatabricksIngestOptions
from contractforge_databricks.runtime.run_payload import run_payload
from contractforge_databricks.runtime.utils import utc_now_str
from contractforge_databricks.state import StateWriter


def finalize_ingest(
    evidence: EvidenceWriter,
    state: StateWriter,
    contract: SemanticContract,
    prepared: PreparedInput,
    opts: DatabricksIngestOptions,
    run_id: str,
    target: str,
    status: str,
    started: str,
    *,
    rows_written: int,
    quality_status_value: str,
    quality_results: tuple[QualityRuleResult, ...] = (),
    operation_metrics: dict[str, Any] | None = None,
    schema_changes: dict[str, Any] | None = None,
    governance_results: dict[str, Any] | None = None,
    write_started_at: str | None = None,
    write_finished_at: str | None = None,
    stage_durations: dict[str, float] | None = None,
    watermark_column: str | None = None,
    watermark_previous: str | None = None,
    watermark_current: str | None = None,
    diagnostics: dict[str, bool] | None = None,
    error_message: str | None = None,
    skip_reason: str | None = None,
    skipped_by_run_id: str | None = None,
) -> dict[str, Any]:
    finished = _utc_now()
    payload = run_payload(
        contract,
        prepared,
        opts,
        run_id,
        target,
        status,
        started,
        finished,
        rows_written,
        quality_status_value,
        operation_metrics or {},
        schema_changes or {},
        governance_results or {},
        write_started_at,
        write_finished_at,
        stage_durations or {},
        watermark_column,
        watermark_previous,
        watermark_current,
        diagnostics or {},
        error_message,
        skip_reason,
        skipped_by_run_id,
    )
    if not opts.dry_run:
        operations = contract.operations.metadata if contract.operations and contract.operations.metadata else {}
        evidence.write_run_log(payload)
        _write_quality_results(evidence, run_id, target, quality_results, payload["finished_at_utc"], opts)
        _write_quarantine_references(evidence, run_id, target, prepared.quarantine_records, payload["finished_at_utc"], opts)
        if prepared.source_metadata:
            evidence.write_source_metadata(
                SourceMetadataEvidenceRecord(
                    run_id=run_id,
                    target_table=target,
                    source_metadata=dict(prepared.source_metadata),
                    captured_at_utc=_parse_utc(finished=payload["finished_at_utc"]),
                )
            )
        state.record_control_metadata(
            framework_version=FRAMEWORK_VERSION,
            ctrl_schema_version=CTRL_SCHEMA_VERSION,
        )
        state.upsert_state(
            target_table=target,
            run_id=run_id,
            status=status,
            rows_written=rows_written,
            watermark_column=watermark_column,
            watermark_value=watermark_current,
            success_at_utc=finished if status == "SUCCESS" else None,
            watermark_candidate=watermark_current,
            table_version=payload.get("table_version_after"),
            write_completed_at_utc=write_finished_at if status == "SUCCESS" else None,
            error_message=error_message,
            parent_run_id=operations.get("parent_run_id"),
            run_group_id=operations.get("run_group_id"),
            master_job_id=operations.get("master_job_id"),
            master_run_id=operations.get("master_run_id"),
        )
    return payload


def _utc_now() -> str:
    return utc_now_str()


def _write_quality_results(
    evidence: EvidenceWriter,
    run_id: str,
    target: str,
    results: tuple[QualityRuleResult, ...],
    checked_at: object,
    opts: DatabricksIngestOptions,
) -> None:
    checked_at_utc = _parse_utc(finished=checked_at)
    for result in results:
        evidence.runner.sql(
            render_quality_result_insert_sql(
                run_id=run_id,
                target_table=target,
                result=result,
                checked_at_utc=checked_at_utc,
                catalog=opts.catalog,
                schema=opts.schema,
            )
        )


def _write_quarantine_references(
    evidence: EvidenceWriter,
    run_id: str,
    target: str,
    records: tuple[QuarantineReference, ...],
    quarantined_at: object,
    opts: DatabricksIngestOptions,
) -> None:
    quarantined_at_utc = _parse_utc(finished=quarantined_at)
    for record in records:
        reason = f"{record.rule_name}: {record.reason}" if record.rule_name else record.reason
        evidence.runner.sql(
            render_quarantine_reference_insert_sql(
                run_id=run_id,
                target_table=target,
                record_ref=record.record_ref,
                reason=reason,
                quarantined_at_utc=quarantined_at_utc,
                catalog=opts.catalog,
                schema=opts.schema,
            )
        )


def _parse_utc(*, finished: object) -> datetime:
    if isinstance(finished, datetime):
        return finished
    try:
        return datetime.strptime(str(finished), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc)
