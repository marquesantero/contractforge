"""Render in-job source metadata evidence writes for AWS Glue jobs."""

from __future__ import annotations

from contractforge_core.connectors import source_metadata_from_contract
from contractforge_core.evidence import EVIDENCE_TABLE_SCHEMAS
from contractforge_aws.schema_columns import schema_columns
from contractforge_core.semantic import SemanticContract
from contractforge_aws.evidence.ddl import evidence_table_names, render_evidence_table_ddl
from contractforge_aws.evidence.runtime import evidence_database
from contractforge_aws.rendering.names import iceberg_table_name


def render_source_metadata_write(
    contract: SemanticContract,
    *,
    dataframe_name: str = "df",
    evidence_database_name: str | None = None,
) -> str:
    database = evidence_database(contract, evidence_database_name)
    metadata_table = evidence_table_names(database)["metadata"]
    target_table = iceberg_table_name(contract)
    metadata = source_metadata_from_contract(contract, target_table=target_table)
    return "\n".join(
        [
            "# Persist source metadata evidence (append-only).",
            f"spark.sql('''{render_evidence_table_ddl('metadata', database)}''')",
            f"_cf_source_metadata = {metadata!r}",
            "_cf_source_metadata.setdefault('source_metrics', {})['rows_read'] = _cf_rows_read",
            f"_cf_source_metadata.setdefault('source_metrics', {{}})['columns_read'] = len({dataframe_name}.columns)",
            "_cf_source_metadata['source_schema'] = {",
            "    'columns': [",
            "        {",
            "            'name': field.name,",
            "            'type': field.dataType.simpleString(),",
            "            'nullable': bool(field.nullable),",
            "        }",
            f"        for field in {dataframe_name}.schema.fields",
            "    ]",
            "}",
            "_cf_persist_source_metadata_evidence(",
            f"    spark, {metadata_table!r}, {{",
            "        'component': 'source',",
            "        'framework_version': 'contractforge-aws',",
            "        'ctrl_schema_version': 1,",
            "        'updated_at_utc': _cf_finished_at.strftime('%Y-%m-%d %H:%M:%S'),",
            "        'run_id': _cf_run_id,",
            f"        'target_table': {target_table!r},",
            "        'source_metadata_json': _cf_source_metadata,",
            "        'captured_at_utc': _cf_finished_at.strftime('%Y-%m-%d %H:%M:%S'),",
            "    },",
            ")",
        ]
    )


def render_source_metadata_helper() -> str:
    metadata_columns = schema_columns(EVIDENCE_TABLE_SCHEMAS["metadata"])
    return "\n".join(
        [
            f"_CF_METADATA_COLUMNS = {metadata_columns!r}",
            "_CF_METADATA_TS_COLUMNS = {'updated_at_utc', 'captured_at_utc'}",
            "_CF_METADATA_INT_COLUMNS = {'ctrl_schema_version'}",
            "",
            "",
            "def _cf_persist_source_metadata_evidence(spark, metadata_table, row):",
            '    """Append one immutable source metadata row to the Iceberg control table."""',
            "    import json",
            "",
            "    def _literal(column, value):",
            "        if value is None:",
            "            return 'CAST(NULL AS TIMESTAMP)' if column in _CF_METADATA_TS_COLUMNS else 'NULL'",
            "        if column in _CF_METADATA_TS_COLUMNS:",
            '            return "CAST(\'" + str(value).replace("\'", "\'\'") + "\' AS TIMESTAMP)"',
            "        if column in _CF_METADATA_INT_COLUMNS:",
            "            return str(int(value))",
            "        if column.endswith('_json'):",
            '            return "\'" + json.dumps(value, sort_keys=True).replace("\'", "\'\'") + "\'"',
            '        return "\'" + str(value).replace("\'", "\'\'") + "\'"',
            "",
            "    normalized = {column: row.get(column) for column in _CF_METADATA_COLUMNS}",
            "    columns_sql = ', '.join('`' + key + '`' for key in _CF_METADATA_COLUMNS)",
            "    values_sql = ', '.join(_literal(key, normalized[key]) for key in _CF_METADATA_COLUMNS)",
            "    spark.sql('INSERT INTO ' + metadata_table + ' (' + columns_sql + ') VALUES (' + values_sql + ')')",
            "",
        ]
    )

