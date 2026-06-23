"""Deterministic contract default resolution."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from typing import Any, Mapping

from contractforge_core.config import canonical_write_mode


@dataclass(frozen=True)
class ContractDefaultDecision:
    path: str
    value: Any
    source: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ResolvedContract:
    contract: dict[str, Any]
    decisions: tuple[ContractDefaultDecision, ...]

    def decisions_json(self) -> list[dict[str, Any]]:
        return [decision.to_dict() for decision in self.decisions]


IDENTITY_WRITE_MODES = {"scd1_upsert", "scd1_hash_diff", "scd2_historical", "snapshot_soft_delete"}


def resolve_contract_defaults(
    contract: Mapping[str, Any],
    *,
    project: Mapping[str, Any] | None = None,
    defaults: Mapping[str, Any] | None = None,
) -> ResolvedContract:
    """Apply explicit project/default values and safe inference to a contract.

    Defaults are deterministic and explicit: every value added by this function
    is returned in the decision ledger. Existing contract values always win.
    """

    resolved = deepcopy(dict(contract))
    decisions: list[ContractDefaultDecision] = []
    default_values = _default_values(project=project, defaults=defaults)
    _apply_target_defaults(resolved, default_values, decisions)
    _apply_contract_defaults(resolved, default_values, decisions)
    _apply_operations_defaults(resolved, default_values, decisions)
    _apply_annotation_defaults(resolved, default_values, decisions)
    _infer_quality_from_identity(resolved, decisions)
    _infer_custom_transform_output(resolved, default_values, decisions)
    return ResolvedContract(contract=resolved, decisions=tuple(decisions))


def _default_values(*, project: Mapping[str, Any] | None, defaults: Mapping[str, Any] | None) -> dict[str, Any]:
    values: dict[str, Any] = {}
    if isinstance(project, Mapping) and isinstance(project.get("defaults"), Mapping):
        values = _deep_merge(values, dict(project["defaults"]))
    if isinstance(defaults, Mapping):
        values = _deep_merge(values, dict(defaults))
    return values


def _apply_target_defaults(
    contract: dict[str, Any],
    defaults: Mapping[str, Any],
    decisions: list[ContractDefaultDecision],
) -> None:
    target = contract.get("target")
    if not isinstance(target, dict):
        return
    if _missing(target.get("catalog")) and defaults.get("catalog"):
        _set(target, "catalog", defaults["catalog"], decisions, "target.catalog", "project.defaults.catalog")
    if _missing(target.get("catalog_type")) and defaults.get("catalog_type"):
        _set(target, "catalog_type", defaults["catalog_type"], decisions, "target.catalog_type", "project.defaults.catalog_type")
    if _missing(target.get("schema")):
        schema = _schema_for_layer(contract, defaults)
        if schema:
            _set(target, "schema", schema, decisions, "target.schema", "project.defaults.schemas")


def _apply_contract_defaults(
    contract: dict[str, Any],
    defaults: Mapping[str, Any],
    decisions: list[ContractDefaultDecision],
) -> None:
    for key in ("mode", "schema_policy", "on_quality_fail"):
        if _missing(contract.get(key)) and defaults.get(key):
            _set(contract, key, defaults[key], decisions, key, f"project.defaults.{key}")


def _apply_operations_defaults(
    contract: dict[str, Any],
    defaults: Mapping[str, Any],
    decisions: list[ContractDefaultDecision],
) -> None:
    operations_defaults = defaults.get("operations")
    if not isinstance(operations_defaults, Mapping):
        return
    operations = contract.get("operations")
    if not isinstance(operations, dict):
        operations = {}
        contract["operations"] = operations
    normalized = _normalize_operations_defaults(dict(operations_defaults))
    _merge_missing(operations, normalized, decisions, path="operations", source="project.defaults.operations")


def _apply_annotation_defaults(
    contract: dict[str, Any],
    defaults: Mapping[str, Any],
    decisions: list[ContractDefaultDecision],
) -> None:
    annotations_defaults = defaults.get("annotations")
    if not isinstance(annotations_defaults, Mapping):
        return
    annotations = contract.get("annotations")
    if not isinstance(annotations, dict):
        annotations = {}
        contract["annotations"] = annotations
    _merge_missing(annotations, dict(annotations_defaults), decisions, path="annotations", source="project.defaults.annotations")


def _infer_quality_from_identity(contract: dict[str, Any], decisions: list[ContractDefaultDecision]) -> None:
    merge_keys = _as_list(contract.get("merge_keys"))
    if not merge_keys:
        return
    if canonical_write_mode(str(contract.get("mode") or "append")) not in IDENTITY_WRITE_MODES:
        return
    quality = contract.get("quality_rules")
    if not isinstance(quality, dict):
        quality = {}
        contract["quality_rules"] = quality
    if not _as_list(quality.get("unique_key")):
        _set(quality, "unique_key", merge_keys, decisions, "quality_rules.unique_key", "inference.merge_keys")
    not_null = _as_list(quality.get("not_null"))
    missing = [key for key in merge_keys if key not in not_null]
    if missing:
        value = [*not_null, *missing]
        _set(quality, "not_null", value, decisions, "quality_rules.not_null", "inference.merge_keys")


def _infer_custom_transform_output(
    contract: dict[str, Any],
    defaults: Mapping[str, Any],
    decisions: list[ContractDefaultDecision],
) -> None:
    source = contract.get("source")
    if not isinstance(source, dict) or source.get("type") != "custom_transform":
        return
    transform = contract.get("transform")
    custom = transform.get("custom") if isinstance(transform, dict) else None
    if isinstance(custom, dict) and not _missing(custom.get("output")):
        return
    output = _custom_transform_output_name(contract, defaults)
    if not output:
        return
    if not isinstance(transform, dict):
        transform = {}
        contract["transform"] = transform
    if not isinstance(transform.get("custom"), dict):
        transform["custom"] = {}
    _set(transform["custom"], "output", output, decisions, "transform.custom.output", "inference.custom_transform_output")


def _custom_transform_output_name(contract: Mapping[str, Any], defaults: Mapping[str, Any]) -> str | None:
    target = contract.get("target")
    if not isinstance(target, Mapping) or _missing(target.get("table")):
        return None
    catalog = target.get("catalog") or defaults.get("catalog")
    schemas = defaults.get("schemas") if isinstance(defaults.get("schemas"), Mapping) else {}
    tmp_schema = defaults.get("tmp_schema") or schemas.get("tmp") or schemas.get("staging")
    if not catalog or not tmp_schema:
        return None
    return f"{catalog}.{tmp_schema}.{target['table']}__custom_output"


def _schema_for_layer(contract: Mapping[str, Any], defaults: Mapping[str, Any]) -> Any:
    schemas = defaults.get("schemas")
    if not isinstance(schemas, Mapping):
        return defaults.get("schema")
    layer = str(contract.get("layer") or defaults.get("layer") or "bronze")
    return schemas.get(layer) or schemas.get("default") or defaults.get("schema")


def _normalize_operations_defaults(value: dict[str, Any]) -> dict[str, Any]:
    ownership_fields = {"business_owner", "technical_owner", "steward", "support_group", "escalation_group"}
    flat = {field: value.pop(field) for field in list(value) if field in ownership_fields}
    if flat:
        ownership = dict(value.get("ownership") or {})
        ownership.update(flat)
        value["ownership"] = ownership
    return value


def _merge_missing(
    target: dict[str, Any],
    defaults: Mapping[str, Any],
    decisions: list[ContractDefaultDecision],
    *,
    path: str,
    source: str,
) -> None:
    for key, value in defaults.items():
        child_path = f"{path}.{key}"
        if isinstance(value, Mapping) and isinstance(target.get(key), dict):
            _merge_missing(target[key], value, decisions, path=child_path, source=source)
        elif _missing(target.get(key)):
            _set(target, key, deepcopy(value), decisions, child_path, source)


def _set(
    target: dict[str, Any],
    key: str,
    value: Any,
    decisions: list[ContractDefaultDecision],
    path: str,
    source: str,
) -> None:
    target[key] = value
    decisions.append(
        ContractDefaultDecision(
            path=path,
            value=value,
            source=source,
            reason="Value was omitted by the contract and resolved deterministically.",
        )
    )


def _deep_merge(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(left)
    for key, value in right.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], dict(value))
        else:
            merged[key] = deepcopy(value)
    return merged


def _missing(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []
