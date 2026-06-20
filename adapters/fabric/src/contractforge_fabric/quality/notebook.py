"""Render Fabric notebook quality gates."""

from __future__ import annotations

import json
from typing import Any

from contractforge_core.semantic import QualityIntent, SemanticContract

_SUPPORTED_RULES = frozenset(
    {
        "required_columns",
        "not_null",
        "unique_key",
        "accepted_values",
        "row_count_minimum",
        "max_null_ratio",
        "expression",
    }
)


def has_quality_rules(contract: SemanticContract) -> bool:
    return bool(contract.quality)


def can_render_quality_runtime(contract: SemanticContract) -> bool:
    return all(rule.rule in _SUPPORTED_RULES for rule in contract.quality)


def render_quality_gate_statement(contract: SemanticContract, *, dataframe_name: str = "df") -> str:
    if not contract.quality:
        return "\n".join(
            [
                "# Quality rules: not configured.",
                "_cf_quality_status = 'NOT_CONFIGURED'",
                "_cf_rows_quarantined = 0",
            ]
        )
    unsupported = [rule.rule for rule in contract.quality if rule.rule not in _SUPPORTED_RULES]
    if unsupported:
        raise ValueError(f"Fabric notebook quality runtime does not implement rules: {unsupported}")

    lines = [
        "# ContractForge quality gates.",
        "_cf_quality_status = 'PASSED'",
        "_cf_rows_quarantined = 0",
        "",
        "def _cf_update_quality_status(status):",
        "    precedence = {'NOT_CONFIGURED': 0, 'PASSED': 1, 'WARNED': 2, 'QUARANTINED': 3, 'FAILED': 4}",
        "    global _cf_quality_status",
        "    if precedence.get(status, 0) > precedence.get(_cf_quality_status, 0):",
        "        _cf_quality_status = status",
        "",
        "def _cf_quote_identifier(value):",
        "    return '`' + str(value).replace('`', '``') + '`'",
        "",
        "def _cf_handle_quality_failure(rule_name, severity, failed_count):",
        "    if failed_count <= 0:",
        "        return",
        "    if severity == 'abort':",
        "        _cf_update_quality_status('FAILED')",
        "        raise ValueError(f'Data quality rule failed: {rule_name}')",
        "    if severity == 'quarantine':",
        "        _cf_update_quality_status('QUARANTINED')",
        "        return",
        "    _cf_update_quality_status('WARNED')",
        "    print(f'Data quality warning recorded: {rule_name} failed_count={failed_count}')",
        "",
    ]
    for rule in contract.quality:
        lines.extend(_rule_lines(rule, dataframe_name=dataframe_name))
    return "\n".join(lines)


def _rule_lines(rule: QualityIntent, *, dataframe_name: str) -> list[str]:
    if rule.rule == "required_columns":
        return _required_columns(rule, dataframe_name=dataframe_name)
    if rule.rule == "not_null":
        return _row_predicate_rule(rule, _not_null_predicate(rule), dataframe_name=dataframe_name)
    if rule.rule == "accepted_values":
        return _row_predicate_rule(rule, _accepted_values_predicate(rule), dataframe_name=dataframe_name)
    if rule.rule == "unique_key":
        return _unique_key(rule, dataframe_name=dataframe_name)
    if rule.rule == "row_count_minimum":
        return _row_count_minimum(rule, dataframe_name=dataframe_name)
    if rule.rule == "max_null_ratio":
        return _max_null_ratio(rule, dataframe_name=dataframe_name)
    if rule.rule == "expression":
        return _row_predicate_rule(rule, _expression_failed_predicate(rule), dataframe_name=dataframe_name)
    raise ValueError(f"Fabric notebook quality runtime does not implement rule: {rule.rule}")


def _required_columns(rule: QualityIntent, *, dataframe_name: str) -> list[str]:
    return [
        "",
        f"# Quality rule: {rule.name}",
        f"_cf_required_columns = {json.dumps(list(rule.columns))}",
        f"_cf_missing_columns = [column for column in _cf_required_columns if column not in {dataframe_name}.columns]",
        (
            f"_cf_add_quality_result({json.dumps(rule.name)}, 'FAILED' if _cf_missing_columns else 'PASSED', "
            "'abort', len(_cf_missing_columns), ','.join(_cf_missing_columns) if _cf_missing_columns else '0', "
            "f'Missing required columns: {_cf_missing_columns}' if _cf_missing_columns else None, "
            "{'required_columns': _cf_required_columns, 'missing_columns': _cf_missing_columns})"
        ),
        "if _cf_missing_columns:",
        "    _cf_update_quality_status('FAILED')",
        "    raise ValueError(f'Missing required columns: {_cf_missing_columns}')",
    ]


def _row_predicate_rule(rule: QualityIntent, failed_predicate: str, *, dataframe_name: str) -> list[str]:
    severity = _severity(rule)
    prefix = _prefix(rule)
    lines = [
        "",
        f"# Quality rule: {rule.name}",
        f"{prefix}_failed_predicate = {json.dumps(failed_predicate)}",
        f"{prefix}_failed = {dataframe_name}.filter({prefix}_failed_predicate)",
        f"{prefix}_failed_count = {prefix}_failed.count()",
        (
            f"_cf_add_quality_result({json.dumps(rule.name)}, 'FAILED' if {prefix}_failed_count > 0 else 'PASSED', "
            f"{json.dumps(severity)}, {prefix}_failed_count, str({prefix}_failed_count), "
            f"f'Quality rule failed: {json.dumps(rule.name)}' if {prefix}_failed_count > 0 else None, "
            f"{{'predicate': {prefix}_failed_predicate, 'columns': {json.dumps(list(rule.columns))}}})"
        ),
    ]
    if severity == "quarantine":
        lines.extend(
            [
                f"if {prefix}_failed_count > 0:",
                "    _cf_rows_quarantined += " + f"{prefix}_failed_count",
                f"    _cf_record_quarantine_evidence({json.dumps(rule.name)}, {prefix}_failed, {prefix}_failed_predicate)",
                f"    _cf_handle_quality_failure({json.dumps(rule.name)}, {json.dumps(severity)}, {prefix}_failed_count)",
                f"    {dataframe_name} = {dataframe_name}.filter('NOT (' + {prefix}_failed_predicate + ')')",
            ]
        )
    else:
        lines.append(f"_cf_handle_quality_failure({json.dumps(rule.name)}, {json.dumps(severity)}, {prefix}_failed_count)")
    return lines


def _unique_key(rule: QualityIntent, *, dataframe_name: str) -> list[str]:
    prefix = _prefix(rule)
    return [
        "",
        f"# Quality rule: {rule.name}",
        f"{prefix}_columns = {json.dumps(list(rule.columns))}",
        f"{prefix}_missing = [column for column in {prefix}_columns if column not in {dataframe_name}.columns]",
        f"if {prefix}_missing:",
        (
            f"    _cf_add_quality_result({json.dumps(rule.name)}, 'FAILED', {json.dumps(_severity(rule))}, "
            f"len({prefix}_missing), ','.join({prefix}_missing), "
            f"f'Missing unique_key columns: {{{prefix}_missing}}', "
            f"{{'columns': {prefix}_columns, 'missing_columns': {prefix}_missing}})"
        ),
        "    _cf_update_quality_status('FAILED')",
        f"    raise ValueError(f'Missing unique_key columns: {{{prefix}_missing}}')",
        f"{prefix}_duplicate_groups = (",
        f"    {dataframe_name}.groupBy(*{prefix}_columns)",
        "    .count()",
        "    .filter('`count` > 1')",
        "    .count()",
        ")",
        (
            f"_cf_add_quality_result({json.dumps(rule.name)}, 'FAILED' if {prefix}_duplicate_groups > 0 else 'PASSED', "
            f"{json.dumps(_severity(rule))}, {prefix}_duplicate_groups, str({prefix}_duplicate_groups), "
            f"f'Duplicate key groups: {{{prefix}_duplicate_groups}}' if {prefix}_duplicate_groups > 0 else None, "
            f"{{'columns': {prefix}_columns}})"
        ),
        f"_cf_handle_quality_failure({json.dumps(rule.name)}, {json.dumps(_severity(rule))}, {prefix}_duplicate_groups)",
    ]


def _row_count_minimum(rule: QualityIntent, *, dataframe_name: str) -> list[str]:
    prefix = _prefix(rule)
    minimum = int(rule.value or 0)
    return [
        "",
        f"# Quality rule: {rule.name}",
        f"{prefix}_row_count = {dataframe_name}.count()",
        f"{prefix}_failed_count = 1 if {prefix}_row_count < {minimum} else 0",
        (
            f"_cf_add_quality_result({json.dumps(rule.name)}, 'FAILED' if {prefix}_failed_count > 0 else 'PASSED', "
            f"{json.dumps(_severity(rule))}, {prefix}_failed_count, str({prefix}_row_count), "
            f"f'Observed row count below minimum: {{{prefix}_row_count}} < {minimum}' if {prefix}_failed_count > 0 else None, "
            f"{{'minimum': {minimum}, 'observed_row_count': {prefix}_row_count}})"
        ),
        f"_cf_handle_quality_failure({json.dumps(rule.name)}, {json.dumps(_severity(rule))}, {prefix}_failed_count)",
    ]


def _max_null_ratio(rule: QualityIntent, *, dataframe_name: str) -> list[str]:
    prefix = _prefix(rule)
    column = _single_column(rule)
    ratio = float(rule.value or 0)
    return [
        "",
        f"# Quality rule: {rule.name}",
        f"{prefix}_total = {dataframe_name}.count()",
        f"{prefix}_nulls = {dataframe_name}.filter({_sql_string(f'{_quote_identifier(column)} IS NULL')}).count()",
        f"{prefix}_ratio = ({prefix}_nulls / {prefix}_total) if {prefix}_total else 0",
        f"{prefix}_failed_count = 1 if {prefix}_ratio > {ratio} else 0",
        (
            f"_cf_add_quality_result({json.dumps(rule.name)}, 'FAILED' if {prefix}_failed_count > 0 else 'PASSED', "
            f"{json.dumps(_severity(rule))}, {prefix}_failed_count, str({prefix}_ratio), "
            f"f'Observed null ratio above maximum: {{{prefix}_ratio}} > {ratio}' if {prefix}_failed_count > 0 else None, "
            f"{{'column': {json.dumps(column)}, 'maximum_ratio': {ratio}, 'observed_ratio': {prefix}_ratio, "
            f"'null_count': {prefix}_nulls, 'total_count': {prefix}_total}})"
        ),
        f"_cf_handle_quality_failure({json.dumps(rule.name)}, {json.dumps(_severity(rule))}, {prefix}_failed_count)",
    ]


def _not_null_predicate(rule: QualityIntent) -> str:
    column = _single_column(rule)
    return f"{_quote_identifier(column)} IS NULL"


def _accepted_values_predicate(rule: QualityIntent) -> str:
    column = _single_column(rule)
    values = rule.value if isinstance(rule.value, list) else [rule.value]
    value_sql = ", ".join(_sql_literal(value) for value in values)
    return f"{_quote_identifier(column)} IS NULL OR {_quote_identifier(column)} NOT IN ({value_sql})"


def _expression_failed_predicate(rule: QualityIntent) -> str:
    expression = str(rule.value or "").strip()
    if not expression:
        raise ValueError(f"Fabric quality expression `{rule.name}` must not be empty")
    return f"NOT ({expression}) OR ({expression}) IS NULL"


def _severity(rule: QualityIntent) -> str:
    return str(rule.severity or "quarantine")


def _prefix(rule: QualityIntent) -> str:
    safe = "".join(char if char.isalnum() else "_" for char in rule.name)
    return f"_cf_quality_{safe}"


def _single_column(rule: QualityIntent) -> str:
    if len(rule.columns) != 1:
        raise ValueError(f"Fabric quality rule `{rule.name}` requires exactly one column")
    return rule.columns[0]


def _quote_identifier(value: str) -> str:
    return "`" + str(value).replace("`", "``") + "`"


def _sql_string(value: str) -> str:
    return json.dumps(value)


def _sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"
