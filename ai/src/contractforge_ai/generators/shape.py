"""Shape suggestions for nested JSON samples."""

from __future__ import annotations

import json
import pprint
import re
from pathlib import Path
from typing import Any

from contractforge_ai.models import EvidenceItem, RequiredDecision, ShapeSuggestionResult, Traceability

MAX_DISCOVERY_DEPTH = 8


def suggest_shape(path: str | Path, *, source_column: str = "raw_payload") -> ShapeSuggestionResult:
    """Suggest ContractForge shape configuration from a JSON sample."""

    source_path = Path(path)
    payload = _load_json_sample(source_path)
    sample = payload[0] if isinstance(payload, list) and payload else payload
    warnings: list[str] = []
    decisions_required: list[str] = []

    if isinstance(payload, list):
        warnings.append("Root JSON is an array. Confirm whether each item should become one row.")
        decisions_required.append("Choose whether to explode the root array or load it as one array-valued column.")

    if not isinstance(sample, dict):
        raise ValueError("Shape suggestions require a JSON object or an array of JSON objects.")

    discovered = _discover(sample)
    arrays = [item for item in discovered if item["kind"].startswith("array")]
    structs = [item for item in discovered if item["kind"] == "struct"]
    primitives = [item for item in discovered if item["kind"] == "primitive"]

    shape: dict[str, Any] = {
        "select": [_column_suggestion(item["path"]) for item in primitives],
    }

    if structs:
        shape["flatten"] = [{"path": item["path"], "prefix": _safe_name(item["path"])} for item in structs]

    if arrays:
        decisions_required.extend(_array_decisions(arrays))
        shape["explode"] = [
            {
                "path": item["path"],
                "mode": "outer",
                "alias": _safe_name(item["path"]),
                "requires_review": True,
            }
            for item in arrays
        ]
        warnings.append("Array explosions can multiply row counts. Review cardinality before applying this shape.")

    if _contains_nested_arrays(arrays):
        warnings.append("Nested arrays were found. Explode one logical array at a time and validate row counts.")

    shape["notes"] = [
        "Generated from a sample payload. Review before applying.",
        "Explode operations are marked requires_review because they can change row cardinality.",
    ]

    return ShapeSuggestionResult(
        source_path=str(source_path),
        shape=shape,
        python_example=_python_example(source_column, shape),
        decisions_required=decisions_required,
        warnings=warnings,
        discovered_paths=discovered,
        traceability=Traceability(
            confidence=0.62 if decisions_required else 0.78,
            evidence=[
                EvidenceItem(
                    source="sample",
                    path=str(source_path),
                    reason="Discovered nested payload structure from a representative JSON sample.",
                    value={"paths": len(discovered), "arrays": len(arrays), "structs": len(structs)},
                    confidence=0.75,
                )
            ],
            decisions_required=[
                RequiredDecision(
                    question=decision,
                    reason="Shape transformations can alter output schema or row cardinality.",
                )
                for decision in decisions_required
            ],
            review_required=bool(decisions_required or warnings),
        ),
    )


def _load_json_sample(path: Path) -> Any:
    raw = path.read_text(encoding="utf-8")
    return json.loads(raw)


def _discover(value: Any, *, prefix: str = "", depth: int = 0) -> list[dict[str, Any]]:
    if depth > MAX_DISCOVERY_DEPTH:
        return [{"path": prefix, "kind": "max_depth", "type": type(value).__name__}]

    if isinstance(value, dict):
        result = []
        if prefix:
            result.append({"path": prefix, "kind": "struct", "type": "object"})
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            result.extend(_discover(item, prefix=path, depth=depth + 1))
        return result

    if isinstance(value, list):
        item_kind = "unknown"
        if value:
            first = value[0]
            if isinstance(first, dict):
                item_kind = "struct"
            elif isinstance(first, list):
                item_kind = "array"
            else:
                item_kind = "primitive"
        result = [{"path": prefix, "kind": f"array<{item_kind}>", "type": "array", "sample_size": len(value)}]
        if value:
            result.extend(_discover(value[0], prefix=f"{prefix}[]", depth=depth + 1))
        return result

    return [{"path": prefix, "kind": "primitive", "type": _json_type(value)}]


def _json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "long"
    if isinstance(value, float):
        return "double"
    return "string"


def _column_suggestion(path: str) -> dict[str, str]:
    return {"path": path, "alias": _safe_name(path)}


def _safe_name(path: str) -> str:
    name = path.replace("[]", "").replace(".", "_")
    name = re.sub(r"[^a-zA-Z0-9_]+", "_", name).strip("_").lower()
    return name or "value"


def _array_decisions(arrays: list[dict[str, Any]]) -> list[str]:
    return [
        f"Review explode for '{item['path']}' ({item['kind']}); sample_size={item.get('sample_size', 'unknown')}."
        for item in arrays
    ]


def _contains_nested_arrays(arrays: list[dict[str, Any]]) -> bool:
    return any("[]" in item["path"] for item in arrays)


def _python_example(source_column: str, shape: dict[str, Any]) -> str:
    shape_literal = pprint.pformat(shape, width=100, sort_dicts=False)
    return (
        "from contractforge_core.contracts import semantic_contract_from_mapping\n\n"
        f"shape = {shape_literal}\n\n"
        "contract = {\n"
        "    \"source\": {\"type\": \"connector\", \"connector\": \"REVIEW_REQUIRED\", \"path\": \"REVIEW_REQUIRED\"},\n"
        "    \"target\": {\"schema\": \"silver_examples\", \"table\": \"s_nested_payload\"},\n"
        "    \"layer\": \"silver\",\n"
        "    \"mode\": \"overwrite\",\n"
        "    \"shape\": shape,\n"
        "}\n\n"
        f"# Apply this shape to the parsed source column: {source_column!r}.\n"
        "semantic = semantic_contract_from_mapping(contract)\n"
    )

