"""Render in-job lineage evidence writes for AWS Glue jobs."""

from __future__ import annotations

from contractforge_core.evidence import EVIDENCE_TABLE_SCHEMAS
from contractforge_aws.schema_columns import schema_columns
from contractforge_core.semantic import SemanticContract
from contractforge_aws.evidence.ddl import evidence_table_names, render_evidence_table_ddl
from contractforge_aws.evidence.runtime import evidence_database
from contractforge_aws.rendering.names import glue_database_name, iceberg_table_name


def render_lineage_write(contract: SemanticContract, *, evidence_database_name: str | None = None) -> str:
    database = evidence_database(contract, evidence_database_name)
    lineage_table = evidence_table_names(database)["lineage"]
    target_table = iceberg_table_name(contract)
    source = contract.source.raw or {}
    source_name = str(source.get("name") or source.get("table") or source.get("path") or source.get("url") or contract.source.name)
    namespace = f"aws-glue://{glue_database_name(contract)}"
    job_name = f"{contract.target.layer}.{contract.target.name}.{contract.write.mode}"
    return "\n".join(
        [
            "# Persist OpenLineage-compatible lineage evidence (append-only).",
            f"spark.sql('''{render_evidence_table_ddl('lineage', database)}''')",
            "_cf_lineage_rows_written = int(",
            "    _cf_summary.get('contractforge_rows_written')",
            "    if _cf_summary.get('contractforge_rows_written') is not None",
            "    else _cf_summary.get('added-records') or 0",
            ")",
            "_cf_lineage_snapshot_after = str(_cf_snapshots[0]['snapshot_id']) if _cf_snapshots else None",
            "_cf_lineage_event = {",
            "    'eventType': 'COMPLETE',",
            "    'eventTime': _cf_finished_at.isoformat(),",
            "    'producer': 'contractforge-aws',",
            "    'schemaURL': 'https://openlineage.io/spec/1-0-5/OpenLineage.json',",
            "    'run': {",
            "        'runId': _cf_run_id,",
            "        'facets': {",
            "            'processing_engine': {",
            "                '_producer': 'contractforge-aws',",
            "                '_schemaURL': 'https://openlineage.io/spec/facets/1-0-0/ProcessingEngineRunFacet.json',",
            "                'name': 'spark',",
            "                'version': _cf_spark_version,",
            "            },",
            "        },",
            "    },",
            f"    'job': {{'namespace': {namespace!r}, 'name': {job_name!r}}},",
            f"    'inputs': [{{'namespace': {namespace!r}, 'name': {source_name!r}}}],",
            f"    'outputs': [{{'namespace': {namespace!r}, 'name': {target_table!r}, 'facets': {{'dataQualityMetrics': {{'rowCount': _cf_lineage_rows_written}}}}}}],",
            "    'facets': {",
            "        'contractforge': {",
            "            '_producer': 'contractforge-aws',",
            "            '_schemaURL': 'https://openlineage.io/spec/facets/1-0-0/RunFacet.json',",
            f"            'mode': {contract.write.mode!r},",
            f"            'layer': {contract.target.layer!r},",
            "            'rowsRead': _cf_rows_read,",
            "            'rowsWritten': _cf_lineage_rows_written,",
            "            'icebergSnapshotAfter': _cf_lineage_snapshot_after,",
            "            'operationMetrics': _cf_summary,",
            "            'startedAt': _cf_run_now.isoformat(),",
            "            'finishedAt': _cf_finished_at.isoformat(),",
            "        }",
            "    },",
            "}",
            "_cf_persist_lineage_evidence(",
            f"    spark, {lineage_table!r}, {{",
            "        'run_id': _cf_run_id,",
            "        'event_time_utc': _cf_finished_at.strftime('%Y-%m-%d %H:%M:%S'),",
            "        'event_type': 'COMPLETE',",
            f"        'target_table': {target_table!r},",
            f"        'source_table': {source_name!r},",
            f"        'source_name': {source_name!r},",
            f"        'namespace': {namespace!r},",
            "        'producer': 'contractforge-aws',",
            "        'event_json': _cf_lineage_event,",
            "    },",
            ")",
        ]
    )


def render_lineage_helper() -> str:
    lineage_columns = schema_columns(EVIDENCE_TABLE_SCHEMAS["lineage"])
    return "\n".join(
        [
            f"_CF_LINEAGE_COLUMNS = {lineage_columns!r}",
            "_CF_LINEAGE_TS_COLUMNS = {'event_time_utc'}",
            "",
            "",
            "def _cf_persist_lineage_evidence(spark, lineage_table, row):",
            '    """Append one immutable lineage event to the Iceberg control table."""',
            "    import json",
            "",
            "    def _literal(column, value):",
            "        if value is None:",
            "            return 'CAST(NULL AS TIMESTAMP)' if column in _CF_LINEAGE_TS_COLUMNS else 'NULL'",
            "        if column in _CF_LINEAGE_TS_COLUMNS:",
            '            return "CAST(\'" + str(value).replace("\'", "\'\'") + "\' AS TIMESTAMP)"',
            "        if column == 'event_json':",
            '            return "\'" + json.dumps(value, sort_keys=True).replace("\'", "\'\'") + "\'"',
            '        return "\'" + str(value).replace("\'", "\'\'") + "\'"',
            "",
            "    normalized = {column: row.get(column) for column in _CF_LINEAGE_COLUMNS}",
            "    columns_sql = ', '.join('`' + key + '`' for key in _CF_LINEAGE_COLUMNS)",
            "    values_sql = ', '.join(_literal(key, normalized[key]) for key in _CF_LINEAGE_COLUMNS)",
            "    spark.sql('INSERT INTO ' + lineage_table + ' (' + columns_sql + ') VALUES (' + values_sql + ')')",
            "",
        ]
    )

