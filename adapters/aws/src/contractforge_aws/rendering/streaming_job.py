"""Render AWS Glue structured-streaming jobs for available_now stream sources.

available_now stream sources (Kafka / Event Hubs with the availableNow trigger)
read once to completion with checkpoint-driven progress. They do not fit the
batch read->prepare->quality->write shape, so the job is rendered as
``readStream`` + ``writeStream`` with a ``foreachBatch`` that runs the same
preparation, quality and Iceberg write per micro-batch.
"""

from __future__ import annotations

from contractforge_core.connectors import (
    is_available_now_stream_source,
    is_eventhubs_stream_source,
    is_kafka_stream_source,
)
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
from contractforge_aws.evidence.stream_runtime import (
    render_stream_batch_helper,
    render_stream_batch_start,
    render_stream_batch_table_ddl,
    render_stream_batch_write,
    render_stream_totals_init,
)
from contractforge_aws.security import render_secret_aware_literal
from contractforge_aws.sources.streams import render_available_now_stream_source
from contractforge_aws.write_modes import render_iceberg_write

# Overwrite per micro-batch would replace the table each batch, so it is excluded.
STREAMING_WRITE_MODES = frozenset({"scd0_append", "scd1_upsert", "scd1_hash_diff"})


def is_available_now_intent(contract: SemanticContract) -> bool:
    """Return whether the contract requests available_now streaming on a stream source."""

    source = contract.source.raw or {}
    if is_available_now_stream_source(source):
        return True
    operations = contract.operations
    if operations is None or not operations.available_now_streaming:
        return False
    return is_kafka_stream_source(source) or is_eventhubs_stream_source(source)


def can_render_streaming_job(contract: SemanticContract) -> bool:
    return (
        contract.write.mode in STREAMING_WRITE_MODES
        and bool(_checkpoint_location(contract))
        and can_render_preparation(contract)
        and can_render_quality_runtime(contract)
    )


def render_streaming_glue_job(
    contract: SemanticContract,
    *,
    evidence_database_name: str | None = None,
    environment_parameters: dict[str, object] | None = None,
) -> str:
    source = contract.source.raw or {}
    checkpoint = _checkpoint_location(contract)
    if not checkpoint:
        raise ValueError("available_now stream rendering requires source.checkpoint_location")
    body = ["# Ensure target namespace inside the protected execution block."]
    body.append(render_target_namespace_create(contract, environment_parameters=environment_parameters))
    body += ["", "# Read source intent (structured streaming, trigger availableNow)."]
    _append_block(body, render_available_now_stream_source(source, dataframe_name="source_stream"))
    body += ["", ""]
    if has_quality_rules(contract):
        _append_block(body, render_quality_evidence_helper())
        body += ["", ""]
    _append_block(body, render_schema_change_helper())
    body += ["", ""]
    _append_block(body, render_schema_snapshot_start(contract))
    body += ["", ""]
    _append_block(body, render_stream_batch_helper())
    body += ["", ""]
    _append_block(body, render_stream_batch_table_ddl(contract, evidence_database_name=evidence_database_name))
    body += ["", render_stream_totals_init(), ""]
    body += [
        f"# Target Iceberg table: {iceberg_table_name(contract)}",
        *_process_batch_lines(contract, checkpoint_location=checkpoint, evidence_database_name=evidence_database_name),
        "",
        "_cf_write_started_at = datetime.now(timezone.utc)",
        "query = (",
        "    source_stream.writeStream",
        f"    .option('checkpointLocation', {render_secret_aware_literal(checkpoint)})",
        "    .trigger(availableNow=True)",
        "    .foreachBatch(_process_batch)",
        "    .start()",
        ")",
        "query.awaitTermination()",
        "_cf_write_finished_at = datetime.now(timezone.utc)",
        "",
        "# Commit the Glue job before writing success-state control evidence.",
        "job.commit()",
        "",
        "",
    ]
    _append_block(body, render_schema_change_write(contract, evidence_database_name=evidence_database_name))
    body += ["", ""]
    _append_block(
        body,
        render_evidence_context(
            contract,
            rows_read_expression="int(_cf_stream_totals.get('rows_read', 0))",
            evidence_database_name=evidence_database_name,
        ),
    )
    body += [
        "_cf_summary.update({",
        "    'stream_batches': int(_cf_stream_totals.get('batches', 0)),",
        "    'stream_rows_read': int(_cf_stream_totals.get('rows_read', 0)),",
        "    'stream_rows_written': int(_cf_stream_totals.get('rows_written', 0)),",
        "    'stream_rows_quarantined': int(_cf_stream_totals.get('rows_quarantined', 0)),",
        "    'contractforge_rows_written': int(_cf_stream_totals.get('rows_written', 0)),",
        "})",
    ]
    body += ["", ""]
    _append_block(body, render_state_helper())
    body += ["", ""]
    _append_block(body, render_state_update(contract, dataframe_name=None, evidence_database_name=evidence_database_name))
    body += ["", ""]
    _append_block(body, render_source_metadata_helper())
    body += ["", ""]
    _append_block(
        body,
        render_source_metadata_write(contract, dataframe_name="source_stream", evidence_database_name=evidence_database_name),
    )
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


def _process_batch_lines(
    contract: SemanticContract,
    *,
    checkpoint_location: str,
    evidence_database_name: str | None = None,
) -> list[str]:
    quality = (
        render_quality_evaluation(contract, evidence_database_name=evidence_database_name).rstrip()
        if has_quality_rules(contract)
        else ""
    )
    sections = [
        "\n".join(render_stream_batch_start()),
        render_preparation(contract).rstrip(),
        quality,
        render_iceberg_write(contract).rstrip(),
        render_stream_batch_write(
            contract,
            checkpoint_location=checkpoint_location,
            evidence_database_name=evidence_database_name,
        ).rstrip(),
    ]
    inner = "\n\n".join(section for section in sections if section)
    indented = [f"    {line}" if line.strip() else "" for line in inner.split("\n")]
    return ["def _process_batch(df, batch_id):", *indented]


def _checkpoint_location(contract: SemanticContract) -> str:
    source = contract.source.raw or {}
    return str(source.get("checkpoint_location") or source.get("options", {}).get("checkpointLocation") or "").strip()


def _append_block(lines: list[str], block: str) -> None:
    lines.extend(block.rstrip().splitlines())


def _indent(lines: list[str]) -> list[str]:
    return [f"    {line}" if line.strip() else "" for line in lines]
