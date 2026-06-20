"""Normalize quality contract sections into semantic intents."""

from __future__ import annotations

from typing import Any

from contractforge_core.normalization.common import as_tuple
from contractforge_core.semantic.models import QualityIntent


def quality_intents(quality_rules: dict[str, Any] | None) -> tuple[QualityIntent, ...]:
    if not quality_rules:
        return ()
    intents: list[QualityIntent] = []
    intents.extend(_required_columns(quality_rules))
    intents.extend(_not_null(quality_rules))
    intents.extend(_unique_key(quality_rules))
    intents.extend(_accepted_values(quality_rules))
    intents.extend(_row_count_minimum(quality_rules))
    intents.extend(_max_null_ratio(quality_rules))
    intents.extend(_expressions(quality_rules))
    return tuple(intents)


def _required_columns(quality_rules: dict[str, Any]) -> list[QualityIntent]:
    required_columns = as_tuple(quality_rules.get("required_columns"))
    if not required_columns:
        return []
    return [
        QualityIntent(
            name="required_columns",
            rule="required_columns",
            columns=required_columns,
            severity="abort",
        )
    ]


def _not_null(quality_rules: dict[str, Any]) -> list[QualityIntent]:
    return [
        QualityIntent(name=f"{column}_not_null", rule="not_null", columns=(column,))
        for column in as_tuple(quality_rules.get("not_null"))
    ]


def _unique_key(quality_rules: dict[str, Any]) -> list[QualityIntent]:
    unique_key = as_tuple(quality_rules.get("unique_key"))
    if not unique_key:
        return []
    return [QualityIntent(name="unique_key", rule="unique_key", columns=unique_key, severity="abort")]


def _accepted_values(quality_rules: dict[str, Any]) -> list[QualityIntent]:
    return [
        QualityIntent(name=f"{column}_accepted_values", rule="accepted_values", columns=(column,), value=values)
        for column, values in quality_rules.get("accepted_values", {}).items()
    ]


def _row_count_minimum(quality_rules: dict[str, Any]) -> list[QualityIntent]:
    if quality_rules.get("min_rows") is None:
        return []
    return [
        QualityIntent(
            name="min_rows",
            rule="row_count_minimum",
            value=quality_rules["min_rows"],
            severity="abort",
        )
    ]


def _max_null_ratio(quality_rules: dict[str, Any]) -> list[QualityIntent]:
    return [
        QualityIntent(
            name=f"{column}_max_null_ratio",
            rule="max_null_ratio",
            columns=(column,),
            value=ratio,
            severity="warn",
        )
        for column, ratio in quality_rules.get("max_null_ratio", {}).items()
    ]


def _expressions(quality_rules: dict[str, Any]) -> list[QualityIntent]:
    intents = []
    for rule in quality_rules.get("expressions", ()):
        if not isinstance(rule, dict):
            continue
        intents.append(
            QualityIntent(
                name=str(rule["name"]),
                rule="expression",
                value=rule["expression"],
                severity=str(rule.get("severity", "quarantine")),
                message=rule.get("message"),
            )
        )
    return intents
