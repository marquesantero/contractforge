"""Render AWS Glue run-evidence persistence helpers."""

from __future__ import annotations

from contractforge_core.evidence import EVIDENCE_TABLE_SCHEMAS
from contractforge_aws.schema_columns import schema_columns


def render_evidence_helper() -> str:
    run_columns = schema_columns(EVIDENCE_TABLE_SCHEMAS["runs"])
    return "\n".join(
        [
            f"_CF_RUN_COLUMNS = {run_columns!r}",
            "_CF_RUN_TS_COLUMNS = {'run_ts_utc', 'started_at_utc', 'finished_at_utc',",
            "                      'write_started_at_utc', 'write_finished_at_utc'}",
            "_CF_RUN_INT_COLUMNS = {'rows_read', 'rows_written', 'rows_inserted', 'rows_updated',",
            "                       'rows_deleted', 'rows_expired', 'rows_quarantined', 'ctrl_schema_version'}",
            "",
            "",
            "def _cf_persist_run_evidence(spark, runs_table, row):",
            "    import json",
            "",
            "    def _literal(column, value):",
            "        if value is None:",
            "            return 'CAST(NULL AS TIMESTAMP)' if column in _CF_RUN_TS_COLUMNS else 'NULL'",
            "        if column in _CF_RUN_TS_COLUMNS:",
            '            return "CAST(\'" + str(value).replace("\'", "\'\'") + "\' AS TIMESTAMP)"',
            "        if column == 'run_date':",
            '            return "CAST(\'" + str(value).replace("\'", "\'\'") + "\' AS DATE)"',
            "        if column in _CF_RUN_INT_COLUMNS:",
            "            return str(int(value))",
            "        if column == 'duration_seconds':",
            "            return str(float(value))",
            "        if column == 'write_committed':",
            "            return 'TRUE' if value else 'FALSE'",
            "        if column.endswith('_json'):",
            '            return "\'" + json.dumps(value, sort_keys=True).replace("\'", "\'\'") + "\'"',
            '        return "\'" + str(value).replace("\'", "\'\'") + "\'"',
            "",
            "    normalized = {column: row.get(column) for column in _CF_RUN_COLUMNS}",
            "    columns_sql = ', '.join('`' + key + '`' for key in _CF_RUN_COLUMNS)",
            "    values_sql = ', '.join(_literal(key, normalized[key]) for key in _CF_RUN_COLUMNS)",
            "    spark.sql('INSERT INTO ' + runs_table + ' (' + columns_sql + ') VALUES (' + values_sql + ')')",
            "",
        ]
    )

