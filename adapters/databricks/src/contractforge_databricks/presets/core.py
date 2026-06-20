"""Preset helpers for Databricks adapter examples and templates."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from contractforge_databricks.presets.catalog import BUILTIN_PRESETS, PRESET_META_KEY, Preset

PRESETS: dict[str, Preset] = deepcopy(BUILTIN_PRESETS)


def list_presets() -> list[str]:
    return sorted(PRESETS)


def get_preset(name: str) -> Preset:
    if name not in PRESETS:
        raise ValueError(f"Preset not found: {name}. valid presets: {list_presets()}")
    return deepcopy(PRESETS[name])


def register_preset(name: str, preset: Preset, *, override: bool = False) -> None:
    normalized_name = str(name or "").strip()
    if not normalized_name:
        raise ValueError("preset name cannot be empty")
    if not isinstance(preset, dict):
        raise ValueError("preset must be a dict")
    if normalized_name in PRESETS and not override:
        raise ValueError(f"Preset already registered: {normalized_name}")
    payload = deepcopy(preset)
    meta = dict(payload.get(PRESET_META_KEY) or {})
    meta.setdefault("name", normalized_name)
    meta.setdefault("description", "")
    meta.setdefault("category", "custom")
    meta.setdefault("kind", "modifier")
    meta.setdefault("required_fields", [])
    payload[PRESET_META_KEY] = meta
    PRESETS[normalized_name] = payload


def preset_details(name: str) -> dict[str, Any]:
    preset = get_preset(name)
    meta = dict(preset.pop(PRESET_META_KEY, {}))
    return {
        "name": name,
        "description": meta.get("description", ""),
        "category": meta.get("category", "custom"),
        "kind": meta.get("kind", "modifier"),
        "required_fields": list(meta.get("required_fields") or []),
        "sets": sorted(_flatten_keys(preset)),
    }


def apply_preset(contract: dict[str, Any]) -> dict[str, Any]:
    names = _preset_names(contract)
    expanded: dict[str, Any] = {}
    metas = []
    for name in names:
        preset = get_preset(name)
        metas.append(dict(preset.pop(PRESET_META_KEY, {})))
        expanded = _deep_merge(expanded, preset)
    explicit = _copy(contract)
    explicit.pop("preset", None)
    explicit.pop("presets", None)
    expanded = _deep_merge(expanded, explicit)
    expanded["applied_presets"] = names
    _validate_exclusive(metas)
    _validate_required(expanded, metas)
    return expanded


def _preset_names(contract: dict[str, Any]) -> list[str]:
    raw = contract.get("preset", contract.get("presets", []))
    if raw is None:
        return []
    values = raw if isinstance(raw, list) else [raw]
    names = [str(item).strip() for item in values]
    if any(not name for name in names):
        raise ValueError("preset cannot contain empty values")
    return names


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = _copy(value)
    return result


def _copy(value: Any) -> Any:
    return deepcopy(value)


def _validate_exclusive(metas: list[dict[str, Any]]) -> None:
    kinds: dict[str, list[str]] = {}
    for meta in metas:
        kinds.setdefault(str(meta.get("kind") or "modifier"), []).append(str(meta.get("name") or "unknown"))
    for kind in ("ingestion", "runtime"):
        if len(kinds.get(kind, [])) > 1:
            raise ValueError(f"Presets of kind {kind} are exclusive; received: {kinds[kind]}")


def _validate_required(contract: dict[str, Any], metas: list[dict[str, Any]]) -> None:
    missing = []
    for meta in metas:
        for field in meta.get("required_fields") or []:
            if not _has_value(contract, str(field)):
                missing.append(f"{meta.get('name')}:{field}")
    if missing:
        raise ValueError(f"Missing required fields for presets: {missing}")


def _has_value(contract: dict[str, Any], field_path: str) -> bool:
    current: Any = contract
    for part in field_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return False
        current = current[part]
    return current is not None and (not isinstance(current, (str, list, tuple, dict)) or bool(current))


def _flatten_keys(payload: dict[str, Any], prefix: str = "") -> list[str]:
    keys = []
    for key, value in payload.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            keys.extend(_flatten_keys(value, path))
        else:
            keys.append(path)
    return keys
