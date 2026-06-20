"""Transformation planning from schema evidence and target intent."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from contractforge_ai.agentic.models import IntentSpec, TransformationPlan, TransformationStep
from contractforge_ai.models import RequiredDecision


@dataclass(frozen=True)
class SchemaColumn:
    """Column evidence extracted from source or target schema metadata."""

    name: str
    type: str | None = None
    expression: str | None = None
    requires_review: bool = False
    review_reason: str | None = None


def infer_transformation_plan(intent: IntentSpec, *, schema_path: str | None) -> TransformationPlan:
    """Infer safe technical transformations from schema evidence."""

    if not intent.final_columns:
        return TransformationPlan()
    schema_columns, target_columns = _schema_profile(schema_path)
    if not schema_columns:
        return TransformationPlan(
            decisions_required=[
                RequiredDecision(
                    question="Confirm source schema before applying final-column projection.",
                    reason="The prompt requested final columns, but no readable schema evidence was available.",
                    path="transform.shape.columns",
                )
            ]
        )

    steps: list[TransformationStep] = []
    decisions: list[RequiredDecision] = []
    schema_lookup = {column.name.lower(): column for column in schema_columns}
    target_lookup = {column.name.lower(): column for column in target_columns}
    for column in intent.final_columns:
        target_column = target_lookup.get(column.lower())
        source_column = schema_lookup.get(column.lower())
        structural_candidates = _structural_candidates(column, schema_columns)
        if source_column and source_column.requires_review:
            decisions.append(_source_review_decision(column, source_column))
            steps.append(
                TransformationStep(
                    action="review_required",
                    column=column,
                    reason=source_column.review_reason or "Source expression requires review.",
                )
            )
            continue
        if source_column and source_column.name != column and len(structural_candidates) > 1:
            decisions.append(_ambiguous_rename_decision(column, structural_candidates))
            steps.append(
                TransformationStep(
                    action="review_required",
                    column=column,
                    reason="Multiple source columns are structurally similar to the requested final column.",
                )
            )
            continue
        if source_column:
            step = _projection_step(column=column, source_column=source_column, target_column=target_column)
            if step.action == "review_required":
                decisions.append(_cast_decision(column, source_column, target_column))
            steps.append(step)
            continue

        rename_candidates = [candidate for candidate in structural_candidates if candidate.name.lower() != column.lower()]
        if len(rename_candidates) == 1:
            if rename_candidates[0].requires_review:
                decisions.append(_source_review_decision(column, rename_candidates[0]))
                steps.append(
                    TransformationStep(
                        action="review_required",
                        column=column,
                        reason=rename_candidates[0].review_reason or "Source expression requires review.",
                    )
                )
                continue
            step = _projection_step(
                column=column,
                source_column=rename_candidates[0],
                target_column=target_column,
                rename=True,
            )
            if step.action == "review_required":
                decisions.append(_cast_decision(column, rename_candidates[0], target_column))
            steps.append(step)
            continue
        if len(rename_candidates) > 1:
            decisions.append(_ambiguous_rename_decision(column, rename_candidates))
            steps.append(
                TransformationStep(
                    action="review_required",
                    column=column,
                    reason="Multiple source columns are structurally similar to the requested final column.",
                )
            )
            continue

        decisions.append(
            RequiredDecision(
                question=f"Map requested final column `{column}` to a source expression.",
                reason="The requested final column was not found in the available schema evidence.",
                path=f"transform.shape.columns.{column}",
            )
        )
        steps.append(
            TransformationStep(
                action="review_required",
                column=column,
                reason="No source column with the same name was found.",
            )
        )
    return TransformationPlan(steps=steps, decisions_required=decisions)


def _projection_step(
    *,
    column: str,
    source_column: SchemaColumn,
    target_column: SchemaColumn | None,
    rename: bool = False,
) -> TransformationStep:
    target_type = target_column.type if target_column else None
    expression = source_column.expression or source_column.name
    if target_type and source_column.type and _canonical_type(target_type) != _canonical_type(source_column.type):
        if not _is_safe_cast(source_column.type, target_type):
            return TransformationStep(
                action="review_required",
                column=column,
                reason=(
                    f"Source column `{source_column.name}` has type `{source_column.type}`, but target type "
                    f"`{target_type}` needs explicit review."
                ),
            )
        return TransformationStep(
            action="cast",
            column=column,
            expression=f"CAST({expression} AS {target_type.upper()})",
            reason="Target schema declares a compatible type cast backed by schema evidence.",
        )
    return TransformationStep(
        action="rename" if rename or expression != column else "select",
        column=column,
        expression=expression,
        reason=(
            "Requested final column matches a structurally equivalent source column and can be renamed safely."
            if rename
            else "Requested final column exists in schema evidence and can be projected safely."
        ),
    )


def _source_review_decision(column: str, source_column: SchemaColumn) -> RequiredDecision:
    return RequiredDecision(
        question=f"Review source expression for requested final column `{column}`.",
        reason=source_column.review_reason or "The source expression can change row cardinality or needs human review.",
        path=f"transform.shape.columns.{column}",
    )


def _cast_decision(column: str, source_column: SchemaColumn, target_column: SchemaColumn | None) -> RequiredDecision:
    return RequiredDecision(
        question=f"Confirm cast or expression for requested final column `{column}`.",
        reason=(
            f"Source column `{source_column.name}` type `{source_column.type}` is not safely compatible with "
            f"target type `{target_column.type if target_column else 'unknown'}`."
        ),
        path=f"transform.shape.columns.{column}",
    )


def _schema_profile(schema_path: str | None) -> tuple[list[SchemaColumn], list[SchemaColumn]]:
    if not schema_path:
        return [], []
    path = Path(schema_path)
    if not path.exists():
        return [], []
    try:
        raw = path.read_text(encoding="utf-8")
        payload = yaml.safe_load(raw) if path.suffix.lower() in {".yaml", ".yml"} else json.loads(raw)
    except Exception:
        return [], []
    columns = _extract_columns(payload)
    if not columns:
        columns = _extract_sample_columns(payload)
    return columns, _extract_target_columns(payload)


def _extract_columns(payload: Any) -> list[SchemaColumn]:
    if not isinstance(payload, dict):
        return []
    columns = payload.get("source_columns") or payload.get("columns") or payload.get("fields")
    return _columns_from_node(columns, payload.get("schema"))


def _extract_target_columns(payload: Any) -> list[SchemaColumn]:
    if not isinstance(payload, dict):
        return []
    columns = payload.get("target_columns") or payload.get("output_columns") or payload.get("final_columns")
    return _columns_from_node(columns, payload.get("target_schema"))


def _columns_from_node(columns: Any, nested_schema: Any = None) -> list[SchemaColumn]:
    if isinstance(columns, list):
        names = []
        for item in columns:
            if isinstance(item, dict) and item.get("name"):
                name = str(item["name"])
                names.append(SchemaColumn(name=name, type=_column_type(item), expression=name))
            elif isinstance(item, str):
                names.append(SchemaColumn(name=item, expression=item))
        return names
    if isinstance(columns, dict):
        names = []
        for key, value in columns.items():
            column_type = _column_type(value) if isinstance(value, dict) else str(value) if isinstance(value, str) else None
            names.append(SchemaColumn(name=str(key), type=column_type, expression=str(key)))
        return names
    if isinstance(nested_schema, dict):
        return _columns_from_node(
            nested_schema.get("columns") or nested_schema.get("fields"),
            nested_schema.get("schema"),
        )
    return []


def _column_type(item: dict[str, Any]) -> str | None:
    value = item.get("type") or item.get("data_type") or item.get("datatype")
    return str(value).upper() if value else None


def _extract_sample_columns(payload: Any) -> list[SchemaColumn]:
    sample = payload[0] if isinstance(payload, list) and payload else payload
    if not isinstance(sample, dict):
        return []
    return [
        SchemaColumn(
            name=_safe_name(path),
            type=_json_type(value),
            expression=path,
            requires_review="[]" in path,
            review_reason=(
                "The source path comes from an array. Explode or zip semantics must be reviewed before projection."
                if "[]" in path
                else None
            ),
        )
        for path, value in _primitive_paths(sample)
    ]


def _primitive_paths(value: Any, *, prefix: str = "") -> list[tuple[str, Any]]:
    if isinstance(value, dict):
        paths: list[tuple[str, Any]] = []
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            paths.extend(_primitive_paths(item, prefix=path))
        return paths
    if isinstance(value, list):
        if not value:
            return [(prefix, value)]
        return _primitive_paths(value[0], prefix=f"{prefix}[]")
    return [(prefix, value)]


def _json_type(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "BOOLEAN"
    if isinstance(value, int):
        return "LONG"
    if isinstance(value, float):
        return "DOUBLE"
    return "STRING"


def _structural_candidates(column: str, schema_columns: list[SchemaColumn]) -> list[SchemaColumn]:
    target_key = _name_key(column)
    return [candidate for candidate in schema_columns if _name_key(candidate.name) == target_key]


def _ambiguous_rename_decision(column: str, candidates: list[SchemaColumn]) -> RequiredDecision:
    return RequiredDecision(
        question=f"Choose the source column for requested final column `{column}`.",
        reason="Multiple structurally similar source columns were found in schema evidence.",
        path=f"transform.shape.columns.{column}",
        options=[candidate.name for candidate in candidates],
    )


def _name_key(value: str) -> str:
    words = re.findall(r"[A-Za-z]+|[0-9]+", value)
    return "".join(word.lower() for word in words)


def _safe_name(path: str) -> str:
    name = path.replace("[]", "").replace(".", "_")
    return re.sub(r"[^A-Za-z0-9_]+", "_", name).strip("_").lower() or "value"


def _canonical_type(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.lower().split("(", 1)[0].strip()
    aliases = {
        "integer": "int",
        "bigint": "long",
        "smallint": "short",
        "real": "float",
        "double precision": "double",
        "number": "decimal",
        "numeric": "decimal",
    }
    return aliases.get(normalized, normalized)


def _is_safe_cast(source_type: str, target_type: str) -> bool:
    numeric_order = {
        "byte": 1,
        "short": 2,
        "int": 3,
        "long": 4,
        "float": 5,
        "double": 6,
        "decimal": 7,
    }
    source = _canonical_type(source_type)
    target = _canonical_type(target_type)
    if source == target:
        return True
    if source in numeric_order and target in numeric_order:
        return numeric_order[source] <= numeric_order[target]
    return False
