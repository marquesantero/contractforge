"""Databricks runtime evaluation for portable quality intents."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from contractforge_core.config import MAX_INLINE_ACCEPTED_VALUES
from contractforge_core.quality import QualityRuleResult, quality_status
from contractforge_core.semantic import QualityIntent, SemanticContract
from contractforge_databricks.quality.registry import evaluate_custom_quality_runtime


def evaluate_quality(
    df: Any,
    contract_or_quality: SemanticContract | tuple[QualityIntent, ...],
) -> tuple[str, tuple[QualityRuleResult, ...], Any, Any, int]:
    quality = contract_or_quality.quality if isinstance(contract_or_quality, SemanticContract) else contract_or_quality
    custom_rules = _custom_quality_rules(contract_or_quality)
    if not quality and not custom_rules:
        return "NOT_CONFIGURED", (), df, df.limit(0), 0
    functions = _functions()
    results: list[QualityRuleResult] = []
    quarantine_condition = functions.lit(False)
    has_quarantine_condition = False
    row_count: int | None = None

    for intent in quality:
        if intent.rule != "required_columns":
            _validate_columns(df, intent.columns, f"quality.{intent.rule}")
        if intent.rule == "required_columns":
            result = _required_columns(df, intent)
        elif intent.rule == "not_null":
            result = _not_null(df, intent, functions)
            if result.failed_count:
                quarantine_condition = quarantine_condition | functions.col(intent.columns[0]).isNull()
                has_quarantine_condition = True
        elif intent.rule == "accepted_values":
            result = _accepted_values(df, intent, functions)
            if result.failed_count:
                column = functions.col(intent.columns[0])
                values = _values(intent.value)
                quarantine_condition = quarantine_condition | ((~column.isin(values)) & column.isNotNull())
                has_quarantine_condition = True
        elif intent.rule == "max_null_ratio":
            row_count = _row_count(df) if row_count is None else row_count
            result = _max_null_ratio(df, intent, functions, row_count)
            if result.failed_count:
                quarantine_condition = quarantine_condition | functions.col(intent.columns[0]).isNull()
                has_quarantine_condition = True
        elif intent.rule == "unique_key":
            result = _unique_key(df, intent, functions)
        elif intent.rule == "row_count_minimum":
            row_count = _row_count(df) if row_count is None else row_count
            result = _row_count_minimum(intent, row_count)
        elif intent.rule == "expression":
            result, condition = _expression(df, intent, functions)
            if result.failed_count and result.severity == "quarantine":
                quarantine_condition = quarantine_condition | condition
                has_quarantine_condition = True
        else:
            result = QualityRuleResult(intent.name, "FAILED", 1, "abort", f"Unsupported quality rule: {intent.rule}")
        results.append(result)

    custom_results, custom_quarantine_condition = evaluate_custom_quality_runtime(df, custom_rules)
    results.extend(custom_results)
    if custom_quarantine_condition is not None:
        quarantine_condition = (
            quarantine_condition | custom_quarantine_condition
            if has_quarantine_condition
            else custom_quarantine_condition
        )
        has_quarantine_condition = True

    failed = tuple(result for result in results if result.failed_count > 0)
    quarantined_df = df.where(quarantine_condition) if failed and has_quarantine_condition else df.limit(0)
    quarantined_count = int(quarantined_df.count()) if failed and has_quarantine_condition else 0
    valid_df = df.where(~quarantine_condition) if quarantined_count > 0 else df
    return quality_status(tuple(results)), tuple(results), valid_df, quarantined_df, quarantined_count


def _required_columns(df: Any, intent: QualityIntent) -> QualityRuleResult:
    missing = [column for column in intent.columns if column not in (getattr(df, "columns", ()) or ())]
    return QualityRuleResult(
        intent.name,
        "FAILED" if missing else "PASSED",
        len(missing),
        "abort",
        "Required columns are missing." if missing else None,
        {"missing": missing},
    )


def _not_null(df: Any, intent: QualityIntent, functions: Any) -> QualityRuleResult:
    column = intent.columns[0]
    count = _agg_int(df, functions.sum(functions.col(column).isNull().cast("long")).alias("failed_rows"), "failed_rows")
    return QualityRuleResult(intent.name, "FAILED" if count else "PASSED", count, _severity(intent), intent.message, {"column": column})


def _accepted_values(df: Any, intent: QualityIntent, functions: Any) -> QualityRuleResult:
    column_name = intent.columns[0]
    column = functions.col(column_name)
    values = _values(intent.value)
    if len(values) > MAX_INLINE_ACCEPTED_VALUES:
        raise ValueError(
            f"quality.accepted_values.{column_name} has {len(values)} values. "
            "Use a reference table or custom quality evaluator for large value sets."
        )
    invalid = (~column.isin(values)) & column.isNotNull()
    count = _agg_int(df, functions.sum(invalid.cast("long")).alias("failed_rows"), "failed_rows")
    return QualityRuleResult(intent.name, "FAILED" if count else "PASSED", count, _severity(intent), intent.message, {"column": column_name, "values": values})


def _max_null_ratio(df: Any, intent: QualityIntent, functions: Any, row_count: int) -> QualityRuleResult:
    column = intent.columns[0]
    null_count = _agg_int(df, functions.sum(functions.col(column).isNull().cast("long")).alias("failed_rows"), "failed_rows")
    ratio = 0.0 if row_count == 0 else null_count / row_count
    failed = ratio > float(intent.value)
    return QualityRuleResult(intent.name, "FAILED" if failed else "PASSED", null_count if failed else 0, _severity(intent), intent.message, {"column": column, "ratio": ratio, "max_ratio": intent.value})


def _unique_key(df: Any, intent: QualityIntent, functions: Any) -> QualityRuleResult:
    duplicates = df.groupBy(*intent.columns).count().where(functions.col("count") > 1).count()
    count = int(duplicates or 0)
    return QualityRuleResult(intent.name, "FAILED" if count else "PASSED", count, "abort", intent.message, {"columns": list(intent.columns)})


def _row_count_minimum(intent: QualityIntent, row_count: int) -> QualityRuleResult:
    minimum = int(intent.value)
    failed = max(0, minimum - row_count)
    return QualityRuleResult(intent.name, "FAILED" if failed else "PASSED", failed, "abort", intent.message, {"min_rows": minimum, "actual": row_count})


def _expression(df: Any, intent: QualityIntent, functions: Any) -> tuple[QualityRuleResult, Any]:
    expression = functions.expr(str(intent.value))
    invalid = expression.isNull() | (expression == functions.lit(False))
    count = _agg_int(df, functions.sum(invalid.cast("long")).alias("failed_rows"), "failed_rows")
    severity = _severity(intent)
    status = "WARNED" if count and severity == "warn" else "FAILED" if count else "PASSED"
    return QualityRuleResult(intent.name, status, count, severity, intent.message, {"expression": intent.value}), invalid


def _agg_int(df: Any, expression: Any, field: str) -> int:
    row = df.agg(expression).collect()[0]
    return int((row[field] if row is not None else 0) or 0)


def _row_count(df: Any) -> int:
    return int(df.count() or 0)


def _validate_columns(df: Any, columns: tuple[str, ...], context: str) -> None:
    missing = [column for column in columns if column not in (getattr(df, "columns", ()) or ())]
    if missing:
        raise ValueError(f"{context} not found: {missing}")


def _values(value: object) -> list[Any]:
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _severity(intent: QualityIntent) -> str:
    return str(intent.severity or "quarantine")  # type: ignore[return-value]


def _functions() -> Any:
    return import_module("pyspark.sql").functions


def _custom_quality_rules(contract_or_quality: SemanticContract | tuple[QualityIntent, ...]) -> dict[str, dict[str, Any]]:
    if not isinstance(contract_or_quality, SemanticContract):
        return {}
    extensions = contract_or_quality.extensions or {}
    quality = extensions.get("quality") if isinstance(extensions, dict) else None
    custom = quality.get("custom") if isinstance(quality, dict) else None
    return dict(custom) if isinstance(custom, dict) else {}
