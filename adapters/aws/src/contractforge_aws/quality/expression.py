"""Render AWS Glue Spark quality expression checks.

Expression rules are not rendered as Glue DQDL because the expression dialect is
Spark SQL. They are still enforceable in the generated Glue job as row-level
DataFrame filters with ContractForge quality/quarantine evidence.
"""

from __future__ import annotations

from collections.abc import Sequence

from contractforge_core.semantic import QualityIntent

_ABORT = "abort"
_QUARANTINE = "quarantine"


def expression_quality_rules(rules: Sequence[QualityIntent]) -> tuple[QualityIntent, ...]:
    return tuple(rule for rule in rules if rule.rule == "expression")


def runtime_unmapped_quality_rules(rules: Sequence[QualityIntent], dqdl_unmapped: tuple[str, ...]) -> tuple[str, ...]:
    expressions = {rule.name for rule in expression_quality_rules(rules)}
    return tuple(name for name in dqdl_unmapped if name not in expressions)


def render_expression_quality_blocks(
    rules: Sequence[QualityIntent],
    dataframe_name: str,
    quality_table: str,
    quarantine_table: str,
    target_table: str,
) -> list[str]:
    lines: list[str] = []
    for rule in rules:
        lines.extend(_expression_block(rule, dataframe_name, quality_table, quarantine_table, target_table))
    return lines


def _expression_block(
    rule: QualityIntent,
    dataframe_name: str,
    quality_table: str,
    quarantine_table: str,
    target_table: str,
) -> list[str]:
    severity = str(rule.severity or "quarantine")
    expression = str(rule.value or "")
    failed_predicate = f"NOT ({expression}) OR ({expression}) IS NULL"
    passed_predicate = f"({expression})"
    prefix = _safe_name(rule.name)
    lines = [
        "",
        f"# Spark SQL quality expression: {rule.name}",
        f"{prefix}_failed = {dataframe_name}.filter({failed_predicate!r})",
        f"{prefix}_failed_count = int({prefix}_failed.count())",
        f"{prefix}_outcomes = [{{",
        f"    'Rule': {rule.name!r},",
        f"    'Outcome': 'Failed' if {prefix}_failed_count else 'Passed',",
        f"    'EvaluatedMetrics': {{'failed_count': {prefix}_failed_count}},",
        f"    'FailureReason': {rule.message!r} if {prefix}_failed_count else None,",
        "}]",
        f"_cf_persist_quality_evidence(spark, {quality_table!r}, _cf_run_id, {target_table!r}, {prefix}_outcomes, {severity!r})",
    ]
    if severity == _ABORT:
        lines.extend(_abort_lines(prefix, rule.name))
    elif severity == _QUARANTINE:
        lines.extend(_quarantine_lines(prefix, dataframe_name, quarantine_table, target_table, passed_predicate))
    else:
        lines.extend(_warn_lines(prefix))
    return lines


def _abort_lines(prefix: str, rule_name: str) -> list[str]:
    return [
        f"if {prefix}_failed_count:",
        "    _cf_update_quality_status('FAILED')",
        f"    raise ValueError('Data quality expression failed: {rule_name}')",
    ]


def _quarantine_lines(prefix: str, dataframe_name: str, quarantine_table: str, target_table: str, passed_predicate: str) -> list[str]:
    return [
        "from pyspark.sql import functions as _cf_F",
        f"if {prefix}_failed_count:",
        "    _cf_update_quality_status('QUARANTINED')",
        f"_cf_payload_columns = list({dataframe_name}.columns)",
        f"{prefix}_failed.select(",
        "    _cf_F.lit(_cf_run_id).alias('run_id'),",
        f"    _cf_F.lit({target_table!r}).alias('target_table'),",
        f"    _cf_F.lit({prefix!r}).alias('rule_name'),",
        "    _cf_F.lit(None).cast('string').alias('error_reason'),",
        "    _cf_F.to_json(_cf_F.struct(*[_cf_F.col(_cf_c) for _cf_c in _cf_payload_columns])).alias('record_payload'),",
        "    _cf_F.lit(None).cast('string').alias('record_ref'),",
        "    _cf_F.lit('quality expression failed').alias('reason'),",
        "    _cf_F.current_timestamp().alias('quarantined_at_utc'),",
        f").writeTo({quarantine_table!r}).append()",
        f"_cf_rows_quarantined = int(globals().get('_cf_rows_quarantined', 0)) + {prefix}_failed_count",
        "globals()['_cf_rows_quarantined'] = _cf_rows_quarantined",
        f"{dataframe_name} = {dataframe_name}.filter({passed_predicate!r})",
    ]


def _warn_lines(prefix: str) -> list[str]:
    return [
        f"if {prefix}_failed_count:",
        "    _cf_update_quality_status('WARNED')",
        f"    print('Data quality expression warning recorded: ' + str({prefix}_outcomes))",
    ]


def _safe_name(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in str(name))
    return "_cf_expr_" + (cleaned or "rule")
