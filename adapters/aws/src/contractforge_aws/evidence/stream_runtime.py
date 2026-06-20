"""Render stream-batch evidence for AWS available-now Glue jobs."""

from __future__ import annotations

from contractforge_core.security import redact_value
from contractforge_core.evidence import EVIDENCE_TABLE_SCHEMAS
from contractforge_aws.schema_columns import schema_columns
from contractforge_core.semantic import SemanticContract
from contractforge_aws.evidence.ddl import evidence_table_names, render_evidence_table_ddl
from contractforge_aws.evidence.run_metadata import run_metadata_from_contract
from contractforge_aws.evidence.runtime import evidence_database
from contractforge_aws.rendering.names import iceberg_table_name


def render_stream_totals_init() -> str:
    return "_cf_stream_totals = {'batches': 0, 'rows_read': 0, 'rows_written': 0, 'rows_quarantined': 0}"


def render_stream_batch_start() -> list[str]:
    return [
        "_cf_batch_started = datetime.now(timezone.utc)",
        "_cf_batch_rows_read = int(df.count())",
        "globals()['_cf_rows_quarantined'] = 0",
    ]


def render_stream_batch_write(
    contract: SemanticContract,
    *,
    checkpoint_location: str,
    evidence_database_name: str | None = None,
) -> str:
    database = evidence_database(contract, evidence_database_name)
    streams_table = evidence_table_names(database)["streams"]
    target_table = iceberg_table_name(contract)
    source = contract.source.raw or {}
    source_type = str(source.get("type") or contract.source.kind or "")
    source_path = redact_value(source.get("path") or source.get("topic") or source.get("eventhub_name") or source.get("url"))
    checkpoint = redact_value(checkpoint_location)
    run_metadata = run_metadata_from_contract(contract)
    return "\n".join(
        [
            "_cf_batch_finished = datetime.now(timezone.utc)",
            "_cf_batch_rows_written = int(df.count())",
            "_cf_batch_rows_quarantined = int(globals().get('_cf_rows_quarantined', 0))",
            "_cf_stream_totals['batches'] += 1",
            "_cf_stream_totals['rows_read'] += _cf_batch_rows_read",
            "_cf_stream_totals['rows_written'] += _cf_batch_rows_written",
            "_cf_stream_totals['rows_quarantined'] += _cf_batch_rows_quarantined",
            "_cf_persist_stream_batch_evidence(",
            f"    spark, {streams_table!r}, {{",
            "        'stream_run_id': _cf_run_id + ':' + str(batch_id),",
            "        'run_id': _cf_run_id,",
            f"        'target_table': {target_table!r},",
            f"        'target_catalog': {contract.target.namespace!r},",
            f"        'target_layer': {contract.target.layer!r},",
            "        'runtime_entrypoint': args['JOB_NAME'],",
            f"        'source_type': {source_type!r},",
            f"        'source_path': {str(source_path) if source_path is not None else None!r},",
            "        'trigger': 'available_now',",
            f"        'checkpoint_location': {checkpoint!r},",
            "        'status': 'SUCCESS',",
            "        'started_at_utc': _cf_batch_started.strftime('%Y-%m-%d %H:%M:%S'),",
            "        'ended_at_utc': _cf_batch_finished.strftime('%Y-%m-%d %H:%M:%S'),",
            "        'duration_seconds': (_cf_batch_finished - _cf_batch_started).total_seconds(),",
            "        'batches_processed': 1,",
            "        'total_rows_read': _cf_batch_rows_read,",
            "        'total_rows_written': _cf_batch_rows_written,",
            "        'total_rows_quarantined': _cf_batch_rows_quarantined,",
            "        'batch_id': str(batch_id),",
            "        'batch_metrics_json': {",
            "            'rows_read': _cf_batch_rows_read,",
            "            'rows_written': _cf_batch_rows_written,",
            "            'rows_quarantined': _cf_batch_rows_quarantined,",
            "        },",
            "        'captured_at_utc': _cf_batch_finished.strftime('%Y-%m-%d %H:%M:%S'),",
            "        'framework_version': 'contractforge-aws',",
            "        'ctrl_schema_version': 1,",
            "        'runtime_type': 'aws_glue',",
            "        'engine_version': spark.version,",
            "        'python_version': sys.version.split()[0],",
            f"        'master_job_id': {run_metadata.get('master_job_id')!r} or _cf_master_job_id,",
            f"        'master_run_id': {run_metadata.get('master_run_id')!r} or _cf_master_run_id,",
            f"        'parent_run_id': {run_metadata.get('parent_run_id')!r} or _cf_parent_run_id,",
            f"        'run_group_id': {run_metadata.get('run_group_id')!r} or _cf_run_group_id,",
            "    },",
            ")",
        ]
    )


def render_stream_batch_table_ddl(contract: SemanticContract, *, evidence_database_name: str | None = None) -> str:
    database = evidence_database(contract, evidence_database_name)
    return "\n".join(
        [
            f"spark.sql('CREATE DATABASE IF NOT EXISTS glue_catalog.`{database}`')",
            f"spark.sql('''{render_evidence_table_ddl('streams', database)}''')",
        ]
    )


def render_stream_batch_helper() -> str:
    stream_columns = schema_columns(EVIDENCE_TABLE_SCHEMAS["streams"])
    return "\n".join(
        [
            f"_CF_STREAM_COLUMNS = {stream_columns!r}",
            "_CF_STREAM_TS_COLUMNS = {'started_at_utc', 'ended_at_utc', 'captured_at_utc'}",
            "_CF_STREAM_INT_COLUMNS = {'batches_processed', 'total_rows_read', 'total_rows_written',",
            "                          'total_rows_quarantined', 'ctrl_schema_version'}",
            "",
            "",
            "def _cf_persist_stream_batch_evidence(spark, streams_table, row):",
            '    """Append one immutable stream-batch row to the Iceberg control table."""',
            "    import json",
            "",
            "    def _literal(column, value):",
            "        if value is None:",
            "            return 'CAST(NULL AS TIMESTAMP)' if column in _CF_STREAM_TS_COLUMNS else 'NULL'",
            "        if column in _CF_STREAM_TS_COLUMNS:",
            '            return "CAST(\'" + str(value).replace("\'", "\'\'") + "\' AS TIMESTAMP)"',
            "        if column in _CF_STREAM_INT_COLUMNS:",
            "            return str(int(value))",
            "        if column == 'duration_seconds':",
            "            return str(float(value))",
            "        if column.endswith('_json'):",
            '            return "\'" + json.dumps(value, sort_keys=True).replace("\'", "\'\'") + "\'"',
            '        return "\'" + str(value).replace("\'", "\'\'") + "\'"',
            "",
            "    normalized = {column: row.get(column) for column in _CF_STREAM_COLUMNS}",
            "    columns_sql = ', '.join('`' + key + '`' for key in _CF_STREAM_COLUMNS)",
            "    values_sql = ', '.join(_literal(key, normalized[key]) for key in _CF_STREAM_COLUMNS)",
            "    spark.sql('INSERT INTO ' + streams_table + ' (' + columns_sql + ') VALUES (' + values_sql + ')')",
            "",
        ]
    )

