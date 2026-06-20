"""Databricks runtime registry for custom quality evaluators."""

from __future__ import annotations

from collections.abc import Callable
from importlib import import_module
from typing import Any

from contractforge_core.config import VALID_QUALITY_RULE_SEVERITIES
from contractforge_core.quality import QualityRuleResult, is_abort_only_failure as is_abort_only_failure

QualityRuleEvaluator = Callable[[Any, str, dict[str, Any]], dict[str, Any]]
QUALITY_RULE_REGISTRY: dict[str, QualityRuleEvaluator] = {}


def register_quality_rule(rule_type: str, evaluator: QualityRuleEvaluator, *, overwrite: bool = False) -> None:
    normalized = _normalize_rule_type(rule_type)
    if not callable(evaluator):
        raise ValueError("quality rule evaluator must be callable")
    if normalized in QUALITY_RULE_REGISTRY and not overwrite:
        raise ValueError(f"quality rule already registered: {normalized}")
    QUALITY_RULE_REGISTRY[normalized] = evaluator


def unregister_quality_rule(rule_type: str) -> None:
    QUALITY_RULE_REGISTRY.pop(_normalize_rule_type(rule_type), None)


def get_quality_rule(rule_type: str) -> QualityRuleEvaluator | None:
    return QUALITY_RULE_REGISTRY.get(_normalize_rule_type(rule_type))


def list_quality_rules() -> tuple[str, ...]:
    return tuple(sorted(QUALITY_RULE_REGISTRY))


def clear_quality_rule_registry() -> None:
    QUALITY_RULE_REGISTRY.clear()


def evaluate_custom_quality_rules(df: Any, custom_rules: dict[str, dict[str, Any]] | None) -> tuple[QualityRuleResult, ...]:
    if not custom_rules:
        return ()
    results: list[QualityRuleResult] = []
    for rule_name, config in custom_rules.items():
        rule_type = str(config.get("type") or "").strip()
        evaluator = QUALITY_RULE_REGISTRY.get(rule_type)
        if evaluator is None:
            raise ValueError(f"quality_rules.custom.{rule_name} uses unregistered type: {rule_type}")
        payload = evaluator(df, str(rule_name), dict(config))
        failed_count = int(payload.get("failed_count", 0) or 0)
        severity = str(payload.get("severity") or config.get("severity") or "abort").strip()
        if severity not in VALID_QUALITY_RULE_SEVERITIES:
            raise ValueError(
                f"quality_rules.custom.{rule_name}.severity={severity!r} is not supported. "
                f"Valid values: {sorted(VALID_QUALITY_RULE_SEVERITIES)}"
            )
        status = _status(failed_count, severity)
        results.append(
            QualityRuleResult(
                rule_name=f"custom:{rule_name}",
                status=status,
                failed_count=failed_count,
                severity=severity,  # type: ignore[arg-type]
                message=payload.get("message") or config.get("message"),
                details={"name": rule_name, "type": rule_type, **dict(payload.get("details") or {})},
            )
        )
    return tuple(results)


def evaluate_custom_quality_runtime(
    df: Any,
    custom_rules: dict[str, dict[str, Any]] | None,
) -> tuple[tuple[QualityRuleResult, ...], Any | None]:
    if not custom_rules:
        return (), None
    functions = import_module("pyspark.sql").functions
    quarantine_condition = functions.lit(False)
    has_quarantine_condition = False
    results: list[QualityRuleResult] = []
    for rule_name, config in custom_rules.items():
        rule_type = str(config.get("type") or "").strip()
        evaluator = QUALITY_RULE_REGISTRY.get(rule_type)
        if evaluator is None:
            raise ValueError(f"quality_rules.custom.{rule_name} uses unregistered type: {rule_type}")
        payload = evaluator(df, str(rule_name), dict(config))
        result = _custom_result(str(rule_name), rule_type, config, payload)
        results.append(result)
        if result.failed_count and result.severity == "quarantine":
            condition = payload.get("condition")
            if condition is None:
                raise ValueError(f"quality_rules.custom.{rule_name} with severity=quarantine must return condition")
            quarantine_condition = quarantine_condition | condition
            has_quarantine_condition = True
    return tuple(results), quarantine_condition if has_quarantine_condition else None


def _custom_result(
    rule_name: str,
    rule_type: str,
    config: dict[str, Any],
    payload: dict[str, Any],
) -> QualityRuleResult:
    failed_count = int(payload.get("failed_count", 0) or 0)
    severity = str(payload.get("severity") or config.get("severity") or "abort").strip()
    if severity not in VALID_QUALITY_RULE_SEVERITIES:
        raise ValueError(
            f"quality_rules.custom.{rule_name}.severity={severity!r} is not supported. "
            f"Valid values: {sorted(VALID_QUALITY_RULE_SEVERITIES)}"
        )
    return QualityRuleResult(
        rule_name=f"custom:{rule_name}",
        status=_status(failed_count, severity),
        failed_count=failed_count,
        severity=severity,  # type: ignore[arg-type]
        message=payload.get("message") or config.get("message"),
        details={"name": rule_name, "type": rule_type, **dict(payload.get("details") or {})},
    )


def _status(failed_count: int, severity: str) -> str:
    if failed_count <= 0:
        return "PASSED"
    if severity == "warn":
        return "WARNED"
    return "FAILED"


def _normalize_rule_type(rule_type: str) -> str:
    normalized = str(rule_type or "").strip()
    if not normalized:
        raise ValueError("quality rule type cannot be empty")
    return normalized
