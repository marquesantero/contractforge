"""Render AWS Glue Data Quality DQDL rulesets from portable quality rules.

The DQDL ruleset is a review/apply artifact that expresses the contract's
quality intent in AWS-native form. It is complementary to the abortive Spark
prechecks rendered into the Glue job: it can be evaluated by Glue Data Quality
(``EvaluateDataQuality`` / a managed ruleset) for native metrics.

Mapping is intentionally conservative. Rules that have no faithful DQDL
equivalent (``expression``) are reported as unmapped rather than approximated.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Callable

from contractforge_core.semantic import QualityIntent, SemanticContract


def can_render_quality_dqdl(contract: SemanticContract) -> bool:
    """Return whether any quality rule maps to a DQDL rule."""

    return any(_rule_to_dqdl(rule) for rule in contract.quality)


def render_quality_dqdl(contract: SemanticContract) -> str:
    """Render a DQDL ``Rules = [...]`` ruleset, or '' when nothing maps."""

    return render_quality_dqdl_rules(contract.quality)


def render_quality_dqdl_rules(intents: Iterable[QualityIntent]) -> str:
    """Render a DQDL ``Rules = [...]`` block for the given intents, or '' when none map."""

    rules: list[str] = []
    for intent in intents:
        rules.extend(_rule_to_dqdl(intent))
    if not rules:
        return ""
    body = ",\n".join(f"    {rule}" for rule in rules)
    return f"Rules = [\n{body}\n]\n"


def unmapped_quality_rules(contract: SemanticContract) -> tuple[str, ...]:
    """Return names of quality rules with no faithful DQDL equivalent."""

    return tuple(rule.name for rule in contract.quality if not _rule_to_dqdl(rule))


# Rules whose DQDL form (IsComplete / ColumnValues) yields meaningful per-row
# pass/fail in Glue ``rowLevelOutcomes``. Aggregate/schema rules (IsUnique,
# RowCount, ColumnExists, Completeness) would fail every row on a dataset-level
# violation, so they are never row-quarantined.
_ROW_LEVEL_QUARANTINABLE = frozenset({"not_null", "accepted_values"})


@dataclass(frozen=True)
class DqdlRuleRenderer:
    kind: str
    render: Callable[[QualityIntent], list[str]]


@dataclass(frozen=True)
class DqdlValueFormatter:
    matches: Callable[[object], bool]
    format: Callable[[object], str]


def is_row_level_quarantinable(rule: QualityIntent) -> bool:
    """Return whether a rule can quarantine offending rows via row-level DQ outcomes."""

    return rule.rule in _ROW_LEVEL_QUARANTINABLE and bool(_rule_to_dqdl(rule))


def _rule_to_dqdl(rule: QualityIntent) -> list[str]:
    renderer = _DQDL_RENDERERS.get(rule.rule)
    return [] if renderer is None else renderer.render(rule)


def _required_columns(rule: QualityIntent) -> list[str]:
    return [f'ColumnExists "{_ident(column)}"' for column in rule.columns]


def _not_null(rule: QualityIntent) -> list[str]:
    return [f'IsComplete "{_ident(column)}"' for column in rule.columns]


def _unique_key(rule: QualityIntent) -> list[str]:
    columns = tuple(rule.columns)
    if not columns:
        return []
    if len(columns) == 1:
        return [f'IsUnique "{_ident(columns[0])}"']
    joined = " ".join(f'"{_ident(column)}"' for column in columns)
    return [f"IsPrimaryKey {joined}"]


def _row_count_minimum(rule: QualityIntent) -> list[str]:
    return [f"RowCount >= {int(rule.value or 0)}"]


def _accepted_values(rule: QualityIntent) -> list[str]:
    if not rule.columns:
        return []
    values = _format_values(rule.value)
    if not values:
        return []
    return [f'ColumnValues "{_ident(rule.columns[0])}" in [{", ".join(values)}]']


def _max_null_ratio(rule: QualityIntent) -> list[str]:
    if not rule.columns:
        return []
    threshold = _format_number(1.0 - float(rule.value or 0))
    return [f'Completeness "{_ident(rule.columns[0])}" >= {threshold}']


def _format_values(value: object) -> list[str]:
    return [_format_value(item) for item in _iter_values(value) if item is not None]


def _iter_values(value: object) -> list[object]:
    return list(value) if isinstance(value, (list, tuple)) else ([] if value is None else [value])


def _format_value(value: object) -> str:
    formatter = next(rule for rule in _VALUE_FORMATTERS if rule.matches(value))
    return formatter.format(value)


def _is_bool(value: object) -> bool:
    return isinstance(value, bool)


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _format_bool(value: object) -> str:
    return "true" if bool(value) else "false"


def _format_numeric_value(value: object) -> str:
    return _format_number(float(value))


def _format_string_value(value: object) -> str:
    return f'"{_ident(str(value))}"'


def _format_number(value: float) -> str:
    if isinstance(value, int) or float(value).is_integer():
        return str(int(value))
    return f"{value:.6g}"


def _ident(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


_DQDL_RENDERERS = {
    renderer.kind: renderer
    for renderer in (
        DqdlRuleRenderer("required_columns", _required_columns),
        DqdlRuleRenderer("not_null", _not_null),
        DqdlRuleRenderer("unique_key", _unique_key),
        DqdlRuleRenderer("row_count_minimum", _row_count_minimum),
        DqdlRuleRenderer("accepted_values", _accepted_values),
        DqdlRuleRenderer("max_null_ratio", _max_null_ratio),
    )
}

_VALUE_FORMATTERS = (
    DqdlValueFormatter(_is_bool, _format_bool),
    DqdlValueFormatter(_is_number, _format_numeric_value),
    DqdlValueFormatter(lambda _value: True, _format_string_value),
)
