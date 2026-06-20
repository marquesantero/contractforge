"""Template helpers for Databricks adapter contract examples."""

from __future__ import annotations

from copy import deepcopy
import json
from typing import Any

from contractforge_databricks.templates.catalog import BUILTIN_CONTRACT_TEMPLATES, TEMPLATE_META_KEY, ContractTemplate


def list_contract_templates() -> list[str]:
    return sorted(BUILTIN_CONTRACT_TEMPLATES)


def get_contract_template(name: str) -> ContractTemplate:
    if name not in BUILTIN_CONTRACT_TEMPLATES:
        raise ValueError(f"Template not found: {name}. Valid templates: {list_contract_templates()}")
    return deepcopy(BUILTIN_CONTRACT_TEMPLATES[name])


def contract_template_files(name: str) -> dict[str, dict[str, Any]]:
    template = get_contract_template(name)
    return {
        key: deepcopy(template[key])
        for key in ("ingestion", "annotations", "operations", "access")
        if key in template
    }


def contract_template_details(name: str) -> dict[str, Any]:
    template = get_contract_template(name)
    meta = dict(template.get(TEMPLATE_META_KEY) or {})
    ingestion = template.get("ingestion") or {}
    return {
        "name": name,
        "description": meta.get("description", ""),
        "category": meta.get("category", "custom"),
        "files": [key for key in ("ingestion", "annotations", "operations", "access") if key in template],
        "target": ingestion.get("target"),
        "presets": ingestion.get("preset"),
        "source": _source_kind(template),
        "mode": ingestion.get("mode"),
        "recommendation_priority": meta.get("recommendation_priority", 100),
    }


def recommend_contract_templates(
    *,
    layer: str | None = None,
    source: str | None = None,
    mode: str | None = None,
    pattern: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    criteria = {"layer": _norm(layer), "source": _norm(source), "mode": _norm(mode), "pattern": _norm(pattern)}
    has_criteria = any(criteria.values())
    matches = []
    for name in list_contract_templates():
        details = contract_template_details(name)
        haystack = _norm(json.dumps({"name": name, "details": details, "template": get_contract_template(name)}))
        score = 0
        matched: list[str] = []
        for key, weight in (("layer", 4), ("source", 3), ("mode", 3), ("pattern", 2)):
            if criteria[key] and criteria[key] in haystack:
                score += weight
                matched.append(key)
        if has_criteria and score == 0:
            continue
        matches.append({**details, "score": score, "matched": matched})
    matches.sort(key=lambda item: (-int(item["score"]), int(item["recommendation_priority"]), str(item["name"])))
    return matches[: max(0, int(limit))] if limit is not None else matches


def _source_kind(template: ContractTemplate) -> str:
    source = (template.get("ingestion") or {}).get("source")
    if isinstance(source, dict):
        return str(source.get("type") or source.get("connector") or "connector")
    return str(source or "unknown")


def _norm(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_")
