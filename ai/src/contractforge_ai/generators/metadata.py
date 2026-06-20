"""Deterministic metadata and quality-rule suggestions from schema evidence."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from contractforge_ai.models import EvidenceItem, MetadataSuggestionResult, Suggestion, Traceability

PII_PATTERNS: dict[str, tuple[str, str, float]] = {
    "email": ("email", "restricted", 0.94),
    "e_mail": ("email", "restricted", 0.94),
    "phone": ("phone", "restricted", 0.88),
    "mobile": ("phone", "restricted", 0.88),
    "cpf": ("national_id", "restricted", 0.92),
    "ssn": ("national_id", "restricted", 0.92),
    "tax_id": ("tax_id", "restricted", 0.86),
    "credit_card": ("credit_card", "restricted", 0.95),
    "card_number": ("credit_card", "restricted", 0.95),
}

KEY_PATTERNS = ("id", "_id", "key", "uuid", "guid")
TIMESTAMP_PATTERNS = ("created_at", "updated_at", "event_time", "event_ts", "timestamp", "_ts")
STATUS_PATTERNS = ("status", "state", "type", "category")
AMOUNT_PATTERNS = ("amount", "price", "total", "subtotal", "cost", "revenue", "quantity", "qty")


def suggest_metadata(path: str | Path) -> MetadataSuggestionResult:
    """Suggest annotations and quality rules from a schema/profile JSON or YAML file."""

    source_path = Path(path)
    payload = _load_payload(source_path)
    columns = _extract_columns(payload)
    warnings: list[str] = []
    suggestions: list[Suggestion] = []

    if not columns:
        warnings.append("No columns were found. Expected a list under 'columns' or a mapping with column definitions.")

    annotations: dict[str, Any] = {"table": {}, "columns": {}}
    quality_rules: dict[str, Any] = {}
    not_null: list[str] = []
    accepted_values: dict[str, list[Any]] = {}
    expressions: list[dict[str, Any]] = []

    for column in columns:
        name = column["name"]
        normalized = _normalize_name(name)
        dtype = str(column.get("type") or "").lower()
        nullable = column.get("nullable")
        profile = column.get("profile") if isinstance(column.get("profile"), dict) else {}
        column_annotations: dict[str, Any] = {}
        evidence: list[str] = []

        description = _description_for(name, dtype)
        if description:
            evidence_items = [
                EvidenceItem(
                    source="schema",
                    path=f"columns.{name}",
                    reason="Description generated from column name and type.",
                    value={"name": name, "type": dtype or "unknown"},
                    confidence=0.62,
                )
            ]
            column_annotations["description"] = description
            suggestions.append(
                Suggestion(
                    kind="column_description",
                    target=name,
                    value=description,
                    confidence=0.62,
                    evidence=[f"Generated from column name '{name}' and type '{dtype or 'unknown'}'."],
                    evidence_items=evidence_items,
                )
            )

        pii = _pii_for(normalized)
        if pii:
            pii_type, sensitivity, confidence = pii
            column_annotations["pii"] = {
                "enabled": True,
                "type": pii_type,
                "sensitivity": sensitivity,
            }
            evidence.append(f"Column name matched PII pattern for {pii_type}.")
            suggestions.append(
                Suggestion(
                    kind="pii",
                    target=name,
                    value=column_annotations["pii"],
                    confidence=confidence,
                    evidence=evidence.copy(),
                    evidence_items=[
                        EvidenceItem(
                            source="schema",
                            path=f"columns.{name}.name",
                            reason=f"Column name matched PII pattern for {pii_type}.",
                            value=name,
                            confidence=confidence,
                        )
                    ],
                    review_required=True,
                )
            )

        tags = _tags_for(normalized, dtype)
        if tags:
            column_annotations["tags"] = tags
            suggestions.append(
                Suggestion(
                    kind="column_tags",
                    target=name,
                    value=tags,
                    confidence=0.70,
                    evidence=[f"Tags inferred from column name '{name}'."],
                    evidence_items=[
                        EvidenceItem(
                            source="schema",
                            path=f"columns.{name}.name",
                            reason="Tags inferred from deterministic column-name patterns.",
                            value=name,
                            confidence=0.70,
                        )
                    ],
                )
            )

        if column_annotations:
            annotations["columns"][name] = column_annotations

        if nullable is False or _looks_like_key(normalized):
            not_null.append(name)
            reason = "nullable=false" if nullable is False else "column name looks like a key"
            suggestions.append(
                Suggestion(
                    kind="quality_not_null",
                    target=name,
                    value=True,
                    confidence=0.92 if nullable is False else 0.78,
                    evidence=[reason],
                    evidence_items=[
                        EvidenceItem(
                            source="schema",
                            path=f"columns.{name}.nullable",
                            reason=reason,
                            value=nullable,
                            confidence=0.92 if nullable is False else 0.78,
                        )
                    ],
                )
            )

        values = _accepted_values(profile)
        if values and _looks_categorical(normalized, dtype, profile):
            accepted_values[name] = values
            suggestions.append(
                Suggestion(
                    kind="quality_accepted_values",
                    target=name,
                    value=values,
                    confidence=0.76,
                    evidence=["Profile contains a small set of observed values."],
                    evidence_items=[
                        EvidenceItem(
                            source="profile",
                            path=f"columns.{name}.profile",
                            reason="Profile contains a small set of observed values.",
                            value=values,
                            confidence=0.76,
                        )
                    ],
                )
            )

        if _looks_non_negative(normalized, dtype):
            expressions.append(
                {
                    "name": f"{normalized}_non_negative",
                    "expression": f"{name} >= 0",
                    "severity": "warn",
                    "message": f"{name} should be non-negative.",
                }
            )
            suggestions.append(
                Suggestion(
                    kind="quality_expression",
                    target=name,
                    value=f"{name} >= 0",
                    confidence=0.68,
                    evidence=[f"Column name '{name}' suggests a non-negative measure."],
                    evidence_items=[
                        EvidenceItem(
                            source="schema",
                            path=f"columns.{name}.name",
                            reason="Column name suggests a non-negative measure.",
                            value=name,
                            confidence=0.68,
                        )
                    ],
                    review_required=True,
                )
            )

    if not_null:
        quality_rules["not_null"] = _dedupe(not_null)
    if accepted_values:
        quality_rules["accepted_values"] = accepted_values
    if expressions:
        quality_rules["expressions"] = expressions

    return MetadataSuggestionResult(
        source_path=str(source_path),
        annotations=annotations,
        quality_rules=quality_rules,
        suggestions=suggestions,
        warnings=warnings,
        traceability=Traceability(
            confidence=_result_confidence(suggestions),
            evidence=[
                EvidenceItem(
                    source="schema",
                    path="columns",
                    reason=f"Read {len(columns)} column definition(s) from schema/profile input.",
                    value=len(columns),
                    confidence=1.0 if columns else 0.0,
                )
            ],
            review_required=bool(suggestions),
        ),
    )


def _load_payload(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        data = yaml.safe_load(raw)
    else:
        data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Schema input must be a JSON/YAML object.")
    return data


def _extract_columns(payload: dict[str, Any]) -> list[dict[str, Any]]:
    columns = payload.get("columns")
    if isinstance(columns, list):
        return [_normalize_column(item) for item in columns if isinstance(item, dict)]
    if isinstance(columns, dict):
        return [_normalize_column({"name": key, **value}) for key, value in columns.items() if isinstance(value, dict)]
    return [
        _normalize_column({"name": key, **value})
        for key, value in payload.items()
        if isinstance(value, dict) and ("type" in value or "nullable" in value)
    ]


def _normalize_column(column: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": str(column["name"]),
        "type": column.get("type") or column.get("data_type"),
        "nullable": column.get("nullable"),
        "profile": column.get("profile"),
    }


def _normalize_name(name: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()
    return normalized or name.lower()


def _description_for(name: str, dtype: str) -> str:
    words = _normalize_name(name).replace("_", " ")
    if dtype:
        return f"{words.title()} value ({dtype})."
    return f"{words.title()} value."


def _pii_for(normalized_name: str) -> tuple[str, str, float] | None:
    for pattern, pii in PII_PATTERNS.items():
        if pattern in normalized_name:
            return pii
    return None


def _tags_for(normalized_name: str, dtype: str) -> dict[str, str]:
    tags: dict[str, str] = {}
    if _looks_like_key(normalized_name):
        tags["role"] = "key"
    if any(pattern in normalized_name for pattern in TIMESTAMP_PATTERNS):
        tags["role"] = "timestamp"
    if any(pattern in normalized_name for pattern in STATUS_PATTERNS):
        tags["role"] = "categorical"
    if "date" in normalized_name or "timestamp" in dtype:
        tags.setdefault("semantic_type", "temporal")
    return tags


def _looks_like_key(normalized_name: str) -> bool:
    return normalized_name == "id" or normalized_name.endswith(KEY_PATTERNS) or normalized_name in {"uuid", "guid"}


def _looks_categorical(normalized_name: str, dtype: str, profile: dict[str, Any]) -> bool:
    if any(pattern in normalized_name for pattern in STATUS_PATTERNS):
        return True
    if "string" in dtype and len(_accepted_values(profile)) <= 20:
        return True
    return False


def _accepted_values(profile: dict[str, Any]) -> list[Any]:
    values = profile.get("accepted_values") or profile.get("distinct_values") or profile.get("top_values")
    if not isinstance(values, list):
        return []
    normalized = [item["value"] if isinstance(item, dict) and "value" in item else item for item in values]
    return normalized if 1 < len(normalized) <= 20 else []


def _looks_non_negative(normalized_name: str, dtype: str) -> bool:
    if not any(kind in dtype for kind in ("int", "long", "double", "float", "decimal", "numeric")):
        return False
    return any(pattern in normalized_name for pattern in AMOUNT_PATTERNS)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _result_confidence(suggestions: list[Suggestion]) -> float:
    if not suggestions:
        return 0.0
    return round(sum(suggestion.confidence for suggestion in suggestions) / len(suggestions), 4)

