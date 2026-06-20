"""Render AWS Glue schema-change evidence helpers."""

from __future__ import annotations

from contractforge_core.evidence import EVIDENCE_TABLE_SCHEMAS
from contractforge_aws.schema_columns import schema_columns
from contractforge_core.semantic import SemanticContract
from contractforge_aws.evidence.ddl import evidence_table_names, render_evidence_table_ddl
from contractforge_aws.evidence.runtime import evidence_database
from contractforge_aws.rendering.names import iceberg_table_name


def render_schema_snapshot_start(contract: SemanticContract) -> str:
    return "\n".join(
        [
            "# Capture target schema before the write for schema-change evidence.",
            f"_cf_target_table = {iceberg_table_name(contract)!r}",
            "_cf_schema_before = _cf_describe_table_schema(spark, _cf_target_table)",
        ]
    )


def render_schema_change_write(contract: SemanticContract, *, evidence_database_name: str | None = None) -> str:
    database = evidence_database(contract, evidence_database_name)
    table = evidence_table_names(database)["schema_changes"]
    return "\n".join(
        [
            "# Persist schema-change evidence after the committed write.",
            f"spark.sql('''{render_evidence_table_ddl('schema_changes', database)}''')",
            "_cf_schema_after = _cf_describe_table_schema(spark, _cf_target_table)",
            "_cf_schema_added = [name for name in _cf_schema_after if name not in _cf_schema_before]",
            "_cf_schema_type_changes = [",
            "    {'column_name': name, 'source_type': _cf_schema_before[name], 'target_type': _cf_schema_after[name], 'applied': True}",
            "    for name in _cf_schema_after",
            "    if name in _cf_schema_before and _cf_schema_before[name] != _cf_schema_after[name]",
            "]",
            "_cf_schema_changes = {'added_columns': _cf_schema_added, 'type_changes': _cf_schema_type_changes}",
            f"_cf_persist_schema_change_evidence(spark, {table!r}, _cf_run_id, _cf_target_table, _cf_schema_after, _cf_schema_changes)",
        ]
    )


def render_schema_change_helper() -> str:
    columns = schema_columns(EVIDENCE_TABLE_SCHEMAS["schema_changes"])
    return "\n".join(
        [
            f"_CF_SCHEMA_CHANGE_COLUMNS = {columns!r}",
            "_CF_SCHEMA_CHANGE_TS_COLUMNS = {'change_ts_utc', 'changed_at_utc'}",
            "_CF_SCHEMA_CHANGE_INT_COLUMNS = {'ctrl_schema_version'}",
            "",
            "",
            "def _cf_describe_table_schema(spark, table):",
            "    try:",
            "        rows = spark.sql('DESCRIBE TABLE ' + table).collect()",
            "    except Exception:",
            "        return {}",
            "    schema = {}",
            "    for row in rows:",
            "        data = row.asDict(recursive=True) if hasattr(row, 'asDict') else dict(row)",
            "        name = str(data.get('col_name') or '').strip()",
            "        data_type = str(data.get('data_type') or '').strip()",
            "        if name and data_type and not name.startswith('#'):",
            "            schema[name] = data_type",
            "    return schema",
            "",
            "",
            "def _cf_persist_schema_change_evidence(spark, table, run_id, target_table, schema_after, changes):",
            "    import json",
            "    now = datetime.now(timezone.utc)",
            "    rows = []",
            "    for column in changes.get('added_columns') or []:",
            "        rows.append({'change_type': 'ADD_COLUMN', 'column_name': column, 'target_type': schema_after.get(column), 'applied': True})",
            "    rows.extend({**change, 'change_type': 'TYPE_CHANGE'} for change in changes.get('type_changes') or [])",
            "    for row in rows:",
            "        payload = {**row, 'schema_after': schema_after}",
            "        values = {",
            "            'run_id': run_id, 'change_ts_utc': now.strftime('%Y-%m-%d %H:%M:%S'),",
            "            'target_table': target_table, 'change_type': row.get('change_type'),",
            "            'column_name': row.get('column_name'), 'source_type': row.get('source_type'),",
            "            'target_type': row.get('target_type'), 'applied': row.get('applied'),",
            "            'details_json': payload, 'payload_json': payload,",
            "            'changed_at_utc': now.strftime('%Y-%m-%d %H:%M:%S'),",
            "            'framework_version': 'contractforge-aws', 'ctrl_schema_version': 1,",
            "        }",
            "        normalized = {column: values.get(column) for column in _CF_SCHEMA_CHANGE_COLUMNS}",
            "        columns_sql = ', '.join('`' + key + '`' for key in _CF_SCHEMA_CHANGE_COLUMNS)",
            "        values_sql = ', '.join(_cf_schema_literal(key, normalized[key], json) for key in _CF_SCHEMA_CHANGE_COLUMNS)",
            "        spark.sql('INSERT INTO ' + table + ' (' + columns_sql + ') VALUES (' + values_sql + ')')",
            "",
            "",
            "def _cf_schema_literal(column, value, json_module):",
            "    if value is None:",
            "        return 'CAST(NULL AS TIMESTAMP)' if column in _CF_SCHEMA_CHANGE_TS_COLUMNS else 'NULL'",
            "    if column in _CF_SCHEMA_CHANGE_TS_COLUMNS:",
            "        return \"CAST('\" + str(value).replace(\"'\", \"''\") + \"' AS TIMESTAMP)\"",
            "    if column in _CF_SCHEMA_CHANGE_INT_COLUMNS:",
            "        return str(int(value))",
            "    if column == 'applied':",
            "        return 'TRUE' if value else 'FALSE'",
            "    if column.endswith('_json'):",
            "        return \"'\" + json_module.dumps(value, sort_keys=True).replace(\"'\", \"''\") + \"'\"",
            "    return \"'\" + str(value).replace(\"'\", \"''\") + \"'\"",
        ]
    )

