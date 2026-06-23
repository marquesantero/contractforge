"""Snowflake runtime quality evaluation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

from contractforge_core.semantic import QualityIntent, SemanticContract
from contractforge_snowflake.environment import SnowflakeEnvironment
from contractforge_snowflake.evidence import record_quality_evidence, record_quarantine_evidence
from contractforge_snowflake.naming import quote_identifier
from contractforge_snowflake.preparation.sql import _safe_expression as _safe_preparation_expression
from contractforge_snowflake.runtime.schema_policy import source_columns_for
from contractforge_snowflake.session_ops import scalar_value


@dataclass(frozen=True)
class SnowflakeQualityResult:
    source_sql: str
    commands: tuple[str, ...]
    status: str
    results: tuple[dict[str, Any], ...]


def apply_quality_rules(
    *,
    session: Any,
    environment: SnowflakeEnvironment,
    contract: SemanticContract,
    run_id: str,
    source_sql: str,
) -> SnowflakeQualityResult:
    commands: list[str] = []
    results: list[dict[str, Any]] = []
    current_source = source_sql
    status = "PASSED"
    for rule in contract.quality:
        context = _QualityContext(contract=contract, rule=rule, source_sql=current_source)
        evaluator = _QUALITY_EVALUATORS.get(rule.rule)
        if evaluator is None:
            raise NotImplementedError(f"Snowflake quality rule is not implemented: {rule.rule}")
        outcome = evaluator(context, session)
        results.append(_quality_result(rule, outcome))
        commands.extend(
            record_quality_evidence(
                session,
                environment=environment,
                contract=contract,
                run_id=run_id,
                rule=rule,
                status=outcome.status,
                failed_count=outcome.failed_count,
                observed_value=outcome.observed_value,
            ).commands
        )
        if outcome.failed_count <= 0:
            continue
        if rule.severity == "abort":
            raise RuntimeError(f"Snowflake quality rule failed: {rule.name}")
        if rule.severity == "quarantine":
            if not outcome.row_level_condition:
                raise RuntimeError(f"Snowflake aggregate quality rule cannot quarantine rows: {rule.name}")
            commands.extend(
                record_quarantine_evidence(
                    session,
                    environment=environment,
                    contract=contract,
                    run_id=run_id,
                    rule=rule,
                    source_sql=current_source,
                    failed_condition=outcome.row_level_condition,
                ).commands
            )
            current_source = _filtered_source(current_source, outcome.row_level_condition)
            status = "QUARANTINED"
        elif status == "PASSED":
            status = "WARNED"
    return SnowflakeQualityResult(source_sql=current_source, commands=tuple(commands), status=status, results=tuple(results))


@dataclass(frozen=True)
class _QualityContext:
    contract: SemanticContract
    rule: QualityIntent
    source_sql: str


@dataclass(frozen=True)
class _QualityOutcome:
    failed_count: int
    status: str
    observed_value: object | None = None
    row_level_condition: str | None = None


def _required_columns(context: _QualityContext, session: Any) -> _QualityOutcome:
    columns = _source_columns(session, context.source_sql)
    available = {_normalized_column_key(column) for column in columns}
    missing = tuple(column for column in context.rule.columns if _normalized_column_key(column) not in available)
    return _QualityOutcome(failed_count=len(missing), status="FAILED" if missing else "PASSED", observed_value=",".join(missing))


def _not_null(context: _QualityContext, session: Any) -> _QualityOutcome:
    column = _source_column_identifier(context, session, _single_column(context.rule))
    condition = f"{quote_identifier(column)} IS NULL"
    failed = _count(session, context.source_sql, condition)
    return _QualityOutcome(failed_count=failed, status=_status(failed), observed_value=failed, row_level_condition=condition)


def _accepted_values(context: _QualityContext, session: Any) -> _QualityOutcome:
    column = _source_column_identifier(context, session, _single_column(context.rule))
    values = context.rule.value if isinstance(context.rule.value, (list, tuple, set)) else (context.rule.value,)
    literals = ", ".join(_sql_literal(value) for value in values)
    condition = f"{quote_identifier(column)} IS NOT NULL AND {quote_identifier(column)} NOT IN ({literals})"
    failed = _count(session, context.source_sql, condition)
    return _QualityOutcome(failed_count=failed, status=_status(failed), observed_value=failed, row_level_condition=condition)


def _expression(context: _QualityContext, session: Any) -> _QualityOutcome:
    expression = str(context.rule.value or "").strip()
    if not expression:
        raise ValueError(f"Snowflake expression quality rule {context.rule.name!r} requires an expression")
    expression = _safe_preparation_expression(expression, known_columns=_source_columns(session, context.source_sql))
    if _is_aggregate_expression(expression):
        failed = _scalar_int(session, f"SELECT IFF(({expression}), 0, 1) FROM (\n{context.source_sql}\n) AS _CF_SOURCE")
        return _QualityOutcome(failed_count=failed, status=_status(failed), observed_value=failed)
    condition = f"NOT ({expression}) OR ({expression}) IS NULL"
    failed = _count(session, context.source_sql, condition)
    return _QualityOutcome(failed_count=failed, status=_status(failed), observed_value=failed, row_level_condition=condition)


def _row_count_minimum(context: _QualityContext, session: Any) -> _QualityOutcome:
    observed = _scalar_int(session, f"SELECT COUNT(*) FROM (\n{context.source_sql}\n) AS _CF_SOURCE")
    minimum = int(context.rule.value or 0)
    failed = 1 if observed < minimum else 0
    return _QualityOutcome(failed_count=failed, status=_status(failed), observed_value=observed)


def _unique_key(context: _QualityContext, session: Any) -> _QualityOutcome:
    columns = ", ".join(quote_identifier(_source_column_identifier(context, session, column)) for column in context.rule.columns)
    sql = (
        "SELECT COUNT(*) FROM (\n"
        f"  SELECT {columns}, COUNT(*) AS _CF_COUNT\n"
        f"  FROM (\n{context.source_sql}\n) AS _CF_SOURCE\n"
        f"  GROUP BY {columns}\n"
        "  HAVING COUNT(*) > 1\n"
        ") AS _CF_DUPLICATES"
    )
    failed = _scalar_int(session, sql)
    return _QualityOutcome(failed_count=failed, status=_status(failed), observed_value=failed)


def _max_null_ratio(context: _QualityContext, session: Any) -> _QualityOutcome:
    column = _source_column_identifier(context, session, _single_column(context.rule))
    threshold = float(context.rule.value or 0)
    sql = (
        f"SELECT COALESCE(AVG(IFF({quote_identifier(column)} IS NULL, 1, 0)), 0)\n"
        f"FROM (\n{context.source_sql}\n) AS _CF_SOURCE"
    )
    observed = _scalar_float(session, sql)
    failed = 1 if observed > threshold else 0
    return _QualityOutcome(failed_count=failed, status=_status(failed), observed_value=observed)


def _count(session: Any, source_sql: str, condition: str) -> int:
    return _scalar_int(session, f"SELECT COUNT(*) FROM (\n{source_sql}\n) AS _CF_SOURCE\nWHERE {condition}")


def _scalar_int(session: Any, sql: str) -> int:
    return int(_scalar(session, sql) or 0)


def _scalar_float(session: Any, sql: str) -> float:
    return float(_scalar(session, sql) or 0)


def _scalar(session: Any, sql: str) -> object | None:
    return scalar_value(session, sql, key="COUNT")


def _source_columns(session: Any, source_sql: str) -> tuple[str, ...]:
    return source_columns_for(session, source_sql)


def _source_column_identifier(context: _QualityContext, session: Any, column: str) -> str:
    columns = _source_columns(session, context.source_sql)
    exact = tuple(candidate for candidate in columns if candidate == column)
    if exact:
        return exact[0]
    normalized = _normalized_column_key(column)
    matches = tuple(candidate for candidate in columns if _normalized_column_key(candidate) == normalized)
    if len(matches) == 1:
        return matches[0]
    return column


def _normalized_column_key(column: str) -> str:
    return str(column).strip('"').upper()


def _filtered_source(source_sql: str, failed_condition: str) -> str:
    return f"SELECT * FROM (\n{source_sql}\n) AS _CF_SOURCE\nWHERE NOT ({failed_condition})"


def _single_column(rule: QualityIntent) -> str:
    if len(rule.columns) != 1:
        raise ValueError(f"Snowflake quality rule {rule.name!r} requires exactly one column")
    return rule.columns[0]


def _status(failed_count: int) -> str:
    return "FAILED" if failed_count > 0 else "PASSED"


def _quality_result(rule: QualityIntent, outcome: _QualityOutcome) -> dict[str, Any]:
    return {
        "rule_name": rule.name,
        "rule": rule.rule,
        "columns": list(rule.columns),
        "severity": rule.severity,
        "status": outcome.status,
        "failed_count": outcome.failed_count,
        "observed_value": outcome.observed_value,
        "row_level": bool(outcome.row_level_condition),
    }


def _sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def _is_aggregate_expression(expression: str) -> bool:
    return bool(re.search(r"\b(count|sum|avg|min|max)\s*\(", expression, flags=re.IGNORECASE))


_QUALITY_EVALUATORS: dict[str, Callable[[_QualityContext, Any], _QualityOutcome]] = {
    "required_columns": _required_columns,
    "not_null": _not_null,
    "accepted_values": _accepted_values,
    "expression": _expression,
    "row_count_minimum": _row_count_minimum,
    "unique_key": _unique_key,
    "max_null_ratio": _max_null_ratio,
}


__all__ = ["SnowflakeQualityResult", "apply_quality_rules"]
