"""Render ContractForge state-table updates for AWS Glue jobs."""

from __future__ import annotations

from contractforge_core.evidence import STATE_TABLE_SCHEMAS
from contractforge_aws.schema_columns import schema_columns
from contractforge_core.semantic import SemanticContract
from contractforge_aws.evidence.ddl import render_state_table_ddl, state_table_names
from contractforge_aws.evidence.runtime import evidence_database
from contractforge_aws.rendering.names import iceberg_table_name


def render_state_update(
    contract: SemanticContract,
    *,
    dataframe_name: str | None = "df",
    evidence_database_name: str | None = None,
) -> str:
    database = evidence_database(contract, evidence_database_name)
    state_table = state_table_names(database)["state"]
    target_table = iceberg_table_name(contract)
    watermark_column = _watermark_column(contract)
    lines = [
        "# Update ContractForge state table after a committed write.",
        f"spark.sql('CREATE DATABASE IF NOT EXISTS glue_catalog.`{database}`')",
        f"spark.sql('''{render_state_table_ddl('state', database)}''')",
        "_cf_state_rows_written = int(",
        "    _cf_summary.get('contractforge_rows_written')",
        "    if _cf_summary.get('contractforge_rows_written') is not None",
        "    else int(_cf_summary.get('added-records') or 0) + int(_cf_summary.get('updated-records') or 0)",
        ")",
        "_cf_state_last_table_version = str(_cf_snapshots[0]['snapshot_id']) if _cf_snapshots else None",
        "_cf_state_status = globals().get('_cf_run_status', 'SUCCESS')",
        "_cf_state_success_ts = _cf_finished_at.strftime('%Y-%m-%d %H:%M:%S') if _cf_state_status == 'SUCCESS' else None",
        "_cf_state_write_completed_ts = _cf_finished_at.strftime('%Y-%m-%d %H:%M:%S') if _cf_state_status == 'SUCCESS' else None",
        f"_cf_state_watermark_column = {watermark_column!r}",
        "_cf_state_watermark_value = None",
    ]
    if dataframe_name is not None:
        lines.extend(_watermark_candidate_lines(dataframe_name))
    lines.extend(
        [
            "_cf_record_state(",
            f"    spark, {state_table!r}, {{",
            f"        'target_table': {target_table!r},",
            "        'watermark_column': _cf_state_watermark_column,",
            "        'watermark_value': _cf_state_watermark_value,",
            "        'last_success_at_utc': _cf_state_success_ts,",
            "        'last_run_id': _cf_run_id,",
            "        'last_status': _cf_state_status,",
            "        'last_rows_written': _cf_state_rows_written,",
            "        'last_table_version': _cf_state_last_table_version,",
            "        'last_watermark_candidate': _cf_state_watermark_value,",
            "        'last_write_completed_at_utc': _cf_state_write_completed_ts,",
            "        'last_updated_at_utc': _cf_finished_at.strftime('%Y-%m-%d %H:%M:%S'),",
            "    },",
            ")",
        ]
    )
    return "\n".join(lines)


def render_state_helper() -> str:
    state_columns = schema_columns(STATE_TABLE_SCHEMAS["state"])
    return "\n".join(
        [
            f"_CF_STATE_COLUMNS = {state_columns!r}",
            "_CF_STATE_TS_COLUMNS = {'last_success_at_utc', 'last_write_completed_at_utc', 'last_updated_at_utc'}",
            "_CF_STATE_INT_COLUMNS = {'last_rows_written'}",
            "",
            "",
            "def _cf_record_state(spark, state_table, row):",
            '    """Append one state observation after a committed write."""',
            "",
            "    def _literal(column, value):",
            "        if value is None:",
            "            return 'CAST(NULL AS TIMESTAMP)' if column in _CF_STATE_TS_COLUMNS else 'NULL'",
            "        if column in _CF_STATE_TS_COLUMNS:",
            '            return "CAST(\'" + str(value).replace("\'", "\'\'") + "\' AS TIMESTAMP)"',
            "        if column in _CF_STATE_INT_COLUMNS:",
            "            return str(int(value))",
            '        return "\'" + str(value).replace("\'", "\'\'") + "\'"',
            "",
            "    normalized = {column: row.get(column) for column in _CF_STATE_COLUMNS}",
            "    select_sql = ', '.join(_literal(column, normalized[column]) + ' AS `' + column + '`' for column in _CF_STATE_COLUMNS)",
            "    spark.sql('INSERT INTO ' + state_table + ' SELECT ' + select_sql)",
            "",
        ]
    )


def _watermark_column(contract: SemanticContract) -> str | None:
    source = contract.source.raw or {}
    incremental = source.get("incremental") if isinstance(source.get("incremental"), dict) else {}
    value = source.get("watermark_column") or incremental.get("watermark_column") or incremental.get("watermark")
    return str(value) if value is not None else None


def _watermark_candidate_lines(dataframe_name: str) -> list[str]:
    return [
        "def _cf_quote_state_identifier(value):",
        "    return '`' + str(value).replace('`', '``') + '`'",
        f"if _cf_state_watermark_column and _cf_state_watermark_column in {dataframe_name}.columns:",
        "    _cf_state_watermark_expr = (",
        "        'CAST(max(' + _cf_quote_state_identifier(_cf_state_watermark_column) + ') AS STRING) AS watermark_value'",
        "    )",
        f"    _cf_state_watermark_rows = {dataframe_name}.selectExpr(_cf_state_watermark_expr).collect()",
        "    _cf_state_watermark_value = (",
        "        _cf_state_watermark_rows[0]['watermark_value'] if _cf_state_watermark_rows else None",
        "    )",
    ]

