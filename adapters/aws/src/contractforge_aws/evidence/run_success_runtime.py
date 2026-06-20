"""Render AWS Glue successful run-evidence writes."""

from __future__ import annotations

from contractforge_core.semantic import SemanticContract
from contractforge_aws.evidence.database import evidence_database
from contractforge_aws.evidence.ddl import evidence_table_names
from contractforge_aws.evidence.run_metadata import run_metadata_from_contract
from contractforge_aws.evidence.source import source_run_evidence_fields
from contractforge_aws.rendering.names import iceberg_table_name


def render_evidence_success_write(
    contract: SemanticContract,
    *,
    evidence_database_name: str | None = None,
) -> str:
    database = evidence_database(contract, evidence_database_name)
    runs_table = evidence_table_names(database)["runs"]
    target_table = iceberg_table_name(contract)
    source_fields = source_run_evidence_fields(contract, target_table=target_table)
    run_metadata = run_metadata_from_contract(contract)
    return "\n".join(
        [
            "# Persist final successful run evidence after all post-write evidence steps complete.",
            "_cf_success_write_started_at = globals().get('_cf_write_started_at') or _cf_run_now",
            "_cf_success_write_finished_at = globals().get('_cf_write_finished_at') or _cf_finished_at",
            "_cf_persist_run_evidence(",
            f"    spark, {runs_table!r}, {{",
            "        'run_id': _cf_run_id,",
            "        'run_ts_utc': _cf_run_now.strftime('%Y-%m-%d %H:%M:%S'),",
            "        'run_date': _cf_run_now.strftime('%Y-%m-%d'),",
            "        'started_at_utc': _cf_run_now.strftime('%Y-%m-%d %H:%M:%S'),",
            "        'finished_at_utc': _cf_finished_at.strftime('%Y-%m-%d %H:%M:%S'),",
            "        'write_started_at_utc': _cf_success_write_started_at.strftime('%Y-%m-%d %H:%M:%S'),",
            "        'write_finished_at_utc': _cf_success_write_finished_at.strftime('%Y-%m-%d %H:%M:%S'),",
            "        'duration_seconds': _cf_duration,",
            f"        'target_table': {target_table!r},",
            f"        'layer': {contract.target.layer!r},",
            f"        'mode': {contract.write.mode!r},",
            *[f"        {name!r}: {source_fields[name]!r}," for name in source_fields],
            "        'source_metrics_json': {'rows_read': _cf_rows_read},",
            "        'status': globals().get('_cf_run_status', 'SUCCESS'),",
            "        'rows_read': _cf_rows_read,",
            "        'rows_written': int(_cf_summary.get('contractforge_rows_written') if _cf_summary.get('contractforge_rows_written') is not None else (_cf_summary.get('added-records') or 0)),",
            "        'rows_inserted': int(_cf_summary.get('added-records') or 0),",
            "        'rows_updated': int(_cf_summary.get('updated-records') or 0),",
            "        'rows_deleted': int(_cf_summary.get('deleted-records') or 0),",
            "        'rows_quarantined': int(globals().get('_cf_rows_quarantined', 0)),",
            f"        'write_engine_requested': {contract.write.mode!r},",
            "        'write_engine_selected': 'aws_glue_iceberg',",
            "        'write_engine_status': globals().get('_cf_write_engine_status', 'SUPPORTED'),",
            "        'write_engine_reason': globals().get('_cf_write_engine_reason', 'Rendered by contractforge-aws Glue/Iceberg adapter'),",
            f"        'quality_status': globals().get('_cf_quality_status', {'PASSED' if contract.quality else 'NOT_CONFIGURED'!r}),",
            "        'schema_changes_json': globals().get('_cf_schema_changes'),",
            f"        'contract_description': {run_metadata.get('contract_description')!r},",
            f"        'contract_owner': {run_metadata.get('contract_owner')!r},",
            f"        'contract_domain': {run_metadata.get('contract_domain')!r},",
            f"        'contract_tags_json': {run_metadata.get('contract_tags_json')!r},",
            f"        'contract_sla': {str(run_metadata.get('contract_sla')) if run_metadata.get('contract_sla') is not None else None!r},",
            f"        'runtime_parameters_json': {run_metadata.get('runtime_parameters_json')!r},",
            f"        'ownership_json': {run_metadata.get('ownership_json')!r},",
            f"        'operations_json': {run_metadata.get('operations_json')!r},",
            f"        'parent_run_id': {run_metadata.get('parent_run_id')!r} or _cf_parent_run_id,",
            f"        'run_group_id': {run_metadata.get('run_group_id')!r} or _cf_run_group_id,",
            f"        'master_job_id': {run_metadata.get('master_job_id')!r} or _cf_master_job_id,",
            f"        'master_run_id': {run_metadata.get('master_run_id')!r} or _cf_master_run_id,",
            f"        'idempotency_key': {run_metadata.get('idempotency_key')!r},",
            f"        'idempotency_policy': {run_metadata.get('idempotency_policy')!r},",
            "        'skip_reason': globals().get('_cf_skip_reason'),",
            "        'table_version_after': (str(_cf_snapshots[0]['snapshot_id']) if _cf_snapshots else None),",
            "        'operation_metrics_json': _cf_summary,",
            "        'metrics_json': _cf_summary,",
            "        'metrics_source': 'glue_iceberg',",
            "        'runtime_type': 'aws_glue',",
            "        'runtime_entrypoint': args['JOB_NAME'],",
            "        'framework_version': 'contractforge-aws',",
            "        'ctrl_schema_version': 1,",
            "        'engine_version': _cf_spark_version,",
            "        'python_version': _cf_python_version,",
            "        'write_committed': not bool(globals().get('_cf_no_input_skip', False) or globals().get('_cf_skip_reason') == 'no_hash_changes'),",
            "    },",
            ")",
        ]
    )
