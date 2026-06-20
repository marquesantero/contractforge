"""Render AWS Glue Spark jobs for supported Iceberg write modes."""

from __future__ import annotations

from contractforge_core.semantic import SemanticContract
from contractforge_aws.evidence.runtime import (
    render_error_evidence_helper,
    render_evidence_context,
    render_evidence_helper,
    render_evidence_success_write,
)
from contractforge_aws.rendering.error_handler import render_error_evidence_handler
from contractforge_aws.rendering.glue_job_common import render_job_preamble, render_target_namespace_create
from contractforge_aws.lineage.runtime import render_lineage_helper, render_lineage_write
from contractforge_aws.evidence.metadata_runtime import render_source_metadata_helper, render_source_metadata_write
from contractforge_aws.rendering.key_guards import render_pre_quality_merge_key_guard
from contractforge_aws.rendering.names import iceberg_table_name
from contractforge_aws.preparation import can_render_preparation, render_preparation
from contractforge_aws.quality.runtime import (
    can_render_quality_runtime,
    has_quality_rules,
    render_quality_evaluation,
    render_quality_evidence_helper,
)
from contractforge_aws.schema.runtime import (
    render_schema_change_helper,
    render_schema_change_write,
    render_schema_snapshot_start,
)
from contractforge_aws.state.runtime import render_state_helper, render_state_update
from contractforge_aws.rendering.streaming_job import (
    can_render_streaming_job,
    is_available_now_intent,
    render_streaming_glue_job,
)
from contractforge_aws.sources import can_render_source, render_source_dataframe
from contractforge_aws.sources.table_refs import contract_with_aws_source_refs
from contractforge_aws.write_modes import render_iceberg_write
from contractforge_aws.write_modes.iceberg import RENDERABLE_WRITE_MODES


def can_render_glue_job(contract: SemanticContract) -> bool:
    if is_available_now_intent(contract):
        return can_render_streaming_job(contract)
    return (
        contract.write.mode in RENDERABLE_WRITE_MODES
        and can_render_source(contract.source.raw or {})
        and can_render_preparation(contract)
        and can_render_quality_runtime(contract)
    )


def render_glue_job(
    contract: SemanticContract,
    *,
    evidence_database_name: str | None = None,
    environment_parameters: dict[str, object] | None = None,
) -> str:
    if not can_render_glue_job(contract):
        raise ValueError(f"AWS Glue job rendering is not implemented for {contract.write.mode!r}")
    runtime_contract = contract_with_aws_source_refs(contract)
    source = runtime_contract.source.raw or {}
    if is_available_now_intent(runtime_contract):
        return render_streaming_glue_job(
            runtime_contract,
            evidence_database_name=evidence_database_name,
            environment_parameters=environment_parameters,
        )
    return _render_batch_glue_job(
        runtime_contract,
        source,
        evidence_database_name=evidence_database_name,
        environment_parameters=environment_parameters,
    )


def _render_batch_glue_job(
    contract: SemanticContract,
    source: dict,
    *,
    evidence_database_name: str | None = None,
    environment_parameters: dict[str, object] | None = None,
) -> str:
    body = ["# Ensure target namespace inside the protected execution block."]
    body.append(render_target_namespace_create(contract, environment_parameters=environment_parameters))
    body += ["", "# Read source intent."]
    _append_block(body, render_source_dataframe(source))
    body += ["", ""]
    if has_quality_rules(contract):
        _append_block(body, render_quality_evidence_helper())
        body += ["", ""]
    _append_block(body, render_schema_change_helper())
    body += ["", ""]
    body += [
        "# Glue bookmarks may return no files/rows and no inferred schema. Treat that",
        "# as an observed skipped run before preparation references contract columns.",
        "_cf_no_input_skip = len(df.columns) == 0",
        "if _cf_no_input_skip:",
        *_indent(_render_no_input_skip_block()),
        "else:",
        *_indent(_render_batch_write_block(contract, evidence_database_name=evidence_database_name)),
        "",
    ]
    body += ["# Commit the Glue job before writing success-state control evidence.", "job.commit()", ""]
    schema_write = render_schema_change_write(contract, evidence_database_name=evidence_database_name).rstrip().splitlines()
    body += ["if not _cf_no_input_skip:", *_indent(schema_write), "", ""]
    _append_block(
        body,
        render_evidence_context(
            contract,
            rows_read_expression="_cf_rows_read",
            evidence_database_name=evidence_database_name,
        ),
    )
    body += ["", ""]
    _append_block(body, render_state_helper())
    body += ["", ""]
    _append_block(body, render_state_update(contract, evidence_database_name=evidence_database_name))
    body += ["", ""]
    _append_block(body, render_source_metadata_helper())
    body += ["", ""]
    _append_block(body, render_source_metadata_write(contract, evidence_database_name=evidence_database_name))
    body += ["", ""]
    _append_block(body, render_lineage_helper())
    body += ["", ""]
    _append_block(body, render_lineage_write(contract, evidence_database_name=evidence_database_name))
    body += ["", ""]
    _append_block(body, render_evidence_success_write(contract, evidence_database_name=evidence_database_name))
    body += ["", ""]
    wrapped = [
        render_error_evidence_helper().rstrip(),
        "",
        render_evidence_helper().rstrip(),
        "",
        "try:",
        *_indent(body),
        *render_error_evidence_handler(contract, evidence_database_name=evidence_database_name),
    ]
    return "\n".join([*render_job_preamble(contract, source, environment_parameters=environment_parameters), *wrapped])


def _render_batch_write_block(contract: SemanticContract, *, evidence_database_name: str | None = None) -> list[str]:
    lines: list[str] = []
    _append_block(lines, render_preparation(contract))
    lines += [
        "",
        "# Capture rows entering quality/write enforcement before quarantine filters mutate the dataframe.",
        "_cf_rows_read = int(df.count())",
        "",
    ]
    merge_key_guard = render_pre_quality_merge_key_guard(contract)
    if merge_key_guard:
        lines.extend(merge_key_guard)
        lines += ["", ""]
    if has_quality_rules(contract):
        _append_block(lines, render_quality_evaluation(contract, evidence_database_name=evidence_database_name))
        lines += ["", ""]
    _append_block(lines, render_schema_snapshot_start(contract))
    lines += [
        "",
        "# Write target intent.",
        f"# Target Iceberg table: {iceberg_table_name(contract)}",
        "",
        "_cf_write_started_at = datetime.now(timezone.utc)",
    ]
    _append_block(lines, render_iceberg_write(contract))
    lines += ["", "_cf_write_finished_at = datetime.now(timezone.utc)", ""]
    return lines


def _render_no_input_skip_block() -> list[str]:
    return [
        "_cf_rows_read = 0",
        "_cf_rows_quarantined = 0",
        "_cf_run_status = 'SKIPPED'",
        "_cf_quality_status = 'SKIPPED'",
        "_cf_skip_reason = 'no_new_input'",
        "_cf_write_engine_status = 'SKIPPED'",
        "_cf_write_engine_reason = 'No new input rows/files were returned by the source'",
        "_cf_schema_changes = None",
        "_cf_write_started_at = datetime.now(timezone.utc)",
        "_cf_write_finished_at = _cf_write_started_at",
    ]


def _append_block(lines: list[str], block: str) -> None:
    lines.extend(block.rstrip().splitlines())


def _indent(lines: list[str]) -> list[str]:
    return [f"    {line}" if line.strip() else "" for line in lines]
