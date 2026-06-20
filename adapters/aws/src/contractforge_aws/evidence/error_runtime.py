"""Render in-job AWS Glue error evidence writes."""

from __future__ import annotations

from contractforge_core.evidence import EVIDENCE_TABLE_SCHEMAS
from contractforge_aws.schema_columns import schema_columns
from contractforge_core.semantic import SemanticContract
from contractforge_aws.evidence.ddl import evidence_table_names, render_evidence_table_ddl
from contractforge_aws.rendering.names import glue_database_name, iceberg_table_name


def evidence_database(contract: SemanticContract, override: str | None = None) -> str:
    return override or f"{glue_database_name(contract)}_ops"


def render_error_evidence_write(contract: SemanticContract, *, evidence_database_name: str | None = None) -> str:
    database = evidence_database(contract, evidence_database_name)
    errors_table = evidence_table_names(database)["errors"]
    target_table = iceberg_table_name(contract)
    source = contract.source.raw or {}
    source_table = source.get("table") or source.get("path") or source.get("url") or contract.source.location
    return "\n".join(
        [
            "# Persist failure evidence to the Iceberg error control table, then re-raise.",
            "_cf_error_now = datetime.now(timezone.utc)",
            "_cf_error_message = _cf_redact_error_text(str(_cf_exc))",
            "_cf_stack_trace = _cf_redact_error_text(traceback.format_exc())",
            f"spark.sql('CREATE DATABASE IF NOT EXISTS glue_catalog.`{database}`')",
            f"spark.sql('''{render_evidence_table_ddl('errors', database)}''')",
            "_cf_persist_error_evidence(",
            f"    spark, {errors_table!r}, {{",
            "        'run_id': _cf_run_id,",
            "        'error_ts_utc': _cf_error_now.strftime('%Y-%m-%d %H:%M:%S'),",
            "        'error_date': _cf_error_now.strftime('%Y-%m-%d'),",
            f"        'target_table': {target_table!r},",
            f"        'source_table': {str(source_table) if source_table is not None else None!r},",
            f"        'mode': {contract.write.mode!r},",
            "        'status': 'FAILED',",
            "        'error_type': type(_cf_exc).__name__,",
            "        'error_class': type(_cf_exc).__module__ + '.' + type(_cf_exc).__name__,",
            "        'error_message': _cf_error_message,",
            "        'stack_trace': _cf_stack_trace,",
            "        'occurred_at_utc': _cf_error_now.strftime('%Y-%m-%d %H:%M:%S'),",
            "        'framework_version': 'contractforge-aws',",
            "        'ctrl_schema_version': 1,",
            "        'runtime_type': 'aws_glue',",
            "        'engine_version': spark.version,",
            "        'python_version': sys.version.split()[0],",
            "    },",
            ")",
        ]
    )


def render_error_evidence_helper() -> str:
    error_columns = schema_columns(EVIDENCE_TABLE_SCHEMAS["errors"])
    return "\n".join(
        [
            f"_CF_ERROR_COLUMNS = {error_columns!r}",
            "_CF_ERROR_TS_COLUMNS = {'error_ts_utc', 'occurred_at_utc'}",
            "_CF_ERROR_INT_COLUMNS = {'ctrl_schema_version'}",
            "",
            "",
            "def _cf_redact_error_text(value):",
            "    text = str(value)",
            "    try:",
            "        from contractforge_core.security import redact_text as _redact_text",
            "        return _redact_text(text)",
            "    except Exception:",
            "        import re as _cf_re",
            "        redacted = text",
            "        redacted = _cf_re.sub(",
            r"            r'(?i)\b(password|passwd|pwd|token|access_token|refresh_token|session_token|security_token|credential|signature|sig|sas|secret|client_secret|api_key|apikey|authorization|private_key|private-key|passphrase|sfpassword|sharedaccesskey|connection_string)(\s*[:=]\s*)([^\s,;&})\]]+)',",
            r"            r'\1\2***REDACTED***',",
            "            redacted,",
            "        )",
            "        redacted = _cf_re.sub(r\"\\b(Bearer|Basic)\\s+[^,\\s'\\\"}]+\", r\"\\1 ***REDACTED***\", redacted, flags=_cf_re.IGNORECASE)",
            "        redacted = _cf_re.sub(r\"([a-z][a-z0-9+.-]*://)([^:/@\\s]+):([^@\\s]+)@\", r\"\\1***REDACTED***:***REDACTED***@\", redacted, flags=_cf_re.IGNORECASE)",
            "        return redacted",
            "",
            "",
            "def _cf_persist_error_evidence(spark, errors_table, row):",
            "",
            "    def _literal(column, value):",
            "        if value is None:",
            "            return 'CAST(NULL AS TIMESTAMP)' if column in _CF_ERROR_TS_COLUMNS else 'NULL'",
            "        if column in _CF_ERROR_TS_COLUMNS:",
            '            return "CAST(\'" + str(value).replace("\'", "\'\'") + "\' AS TIMESTAMP)"',
            "        if column == 'error_date':",
            '            return "CAST(\'" + str(value).replace("\'", "\'\'") + "\' AS DATE)"',
            "        if column in _CF_ERROR_INT_COLUMNS:",
            "            return str(int(value))",
            '        return "\'" + str(value).replace("\'", "\'\'") + "\'"',
            "",
            "    normalized = {column: row.get(column) for column in _CF_ERROR_COLUMNS}",
            "    columns_sql = ', '.join('`' + key + '`' for key in _CF_ERROR_COLUMNS)",
            "    values_sql = ', '.join(_literal(key, normalized[key]) for key in _CF_ERROR_COLUMNS)",
            "    spark.sql('INSERT INTO ' + errors_table + ' (' + columns_sql + ') VALUES (' + values_sql + ')')",
            "",
        ]
    )

