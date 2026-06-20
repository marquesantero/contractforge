"""Render failed-run evidence writes for AWS Glue jobs."""

from __future__ import annotations

from contractforge_core.semantic import SemanticContract
from contractforge_aws.evidence.ddl import evidence_table_names, render_runs_table_ddl
from contractforge_aws.evidence.run_metadata import run_metadata_from_contract
from contractforge_aws.evidence.source import source_run_evidence_fields
from contractforge_aws.rendering.names import glue_database_name, iceberg_table_name


def render_evidence_failure_write(
    contract: SemanticContract,
    *,
    evidence_database_name: str | None = None,
) -> str:
    database = evidence_database_name or f"{glue_database_name(contract)}_ops"
    runs_table = evidence_table_names(database)["runs"]
    target_table = iceberg_table_name(contract)
    source_fields = source_run_evidence_fields(contract, target_table=target_table)
    run_metadata = run_metadata_from_contract(contract)
    return "\n".join(
        [
            "# Persist failed run evidence after error evidence is recorded.",
            f"spark.sql('CREATE DATABASE IF NOT EXISTS glue_catalog.`{database}`')",
            f"spark.sql('''{render_runs_table_ddl(database)}''')",
            "_cf_failure_finished_at = globals().get('_cf_error_now') or datetime.now(timezone.utc)",
            "_cf_failure_write_started_at = globals().get('_cf_write_started_at')",
            "_cf_failure_write_finished_at = globals().get('_cf_write_finished_at') or (_cf_failure_finished_at if _cf_failure_write_started_at else None)",
            "_cf_failure_duration = (_cf_failure_finished_at - _cf_run_now).total_seconds()",
            "_cf_persist_run_evidence(",
            f"    spark, {runs_table!r}, {{",
            "        'run_id': _cf_run_id,",
            "        'run_ts_utc': _cf_run_now.strftime('%Y-%m-%d %H:%M:%S'),",
            "        'run_date': _cf_run_now.strftime('%Y-%m-%d'),",
            "        'started_at_utc': _cf_run_now.strftime('%Y-%m-%d %H:%M:%S'),",
            "        'finished_at_utc': _cf_failure_finished_at.strftime('%Y-%m-%d %H:%M:%S'),",
            "        'write_started_at_utc': _cf_failure_write_started_at.strftime('%Y-%m-%d %H:%M:%S') if _cf_failure_write_started_at else None,",
            "        'write_finished_at_utc': _cf_failure_write_finished_at.strftime('%Y-%m-%d %H:%M:%S') if _cf_failure_write_finished_at else None,",
            "        'duration_seconds': _cf_failure_duration,",
            f"        'target_table': {target_table!r},",
            f"        'layer': {contract.target.layer!r},",
            f"        'mode': {contract.write.mode!r},",
            *[f"        {name!r}: {source_fields[name]!r}," for name in source_fields],
            "        'source_metrics_json': {'rows_read': globals().get('_cf_rows_read')},",
            "        'status': 'FAILED',",
            "        'rows_read': globals().get('_cf_rows_read'),",
            "        'rows_quarantined': int(globals().get('_cf_rows_quarantined', 0)),",
            f"        'write_engine_requested': {contract.write.mode!r},",
            "        'write_engine_selected': 'aws_glue_iceberg',",
            "        'write_engine_status': 'FAILED',",
            "        'write_engine_reason': 'AWS Glue job failed before successful completion',",
            "        'quality_status': globals().get('_cf_quality_status', 'NOT_CONFIGURED'),",
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
            "        'metrics_json': {'error_type': type(_cf_exc).__name__},",
            "        'metrics_source': 'glue_exception',",
            "        'runtime_type': 'aws_glue',",
            "        'runtime_entrypoint': args['JOB_NAME'],",
            "        'framework_version': 'contractforge-aws',",
            "        'ctrl_schema_version': 1,",
            "        'engine_version': spark.version,",
            "        'python_version': sys.version.split()[0],",
            "        'write_committed': False,",
            "        'error_message': _cf_error_message,",
            "    },",
            ")",
        ]
    )
