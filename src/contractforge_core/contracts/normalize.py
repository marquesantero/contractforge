"""Normalize validated public contracts into semantic core models."""

from __future__ import annotations

from typing import Any

from contractforge_core.config import PUBLIC_WRITE_MODES, VALID_SCHEMA_POLICIES, canonical_write_mode, is_valid_write_mode
from contractforge_core.contracts.governance import (
    validate_access_contract,
    validate_annotations_contract,
    validate_operations_contract,
)
from contractforge_core.contracts.execution import validate_execution_contract
from contractforge_core.contracts.naming import validate_naming_contract
from contractforge_core.contracts.quality import validate_quality_rules_contract
from contractforge_core.contracts.root import validate_contract
from contractforge_core.contracts.source import validate_source_contract
from contractforge_core.contracts.transform import validate_shape_contract, validate_transform_contract
from contractforge_core.normalization import (
    as_tuple,
    governance_intent,
    nested_shape,
    operations_intent,
    quality_intents,
    source_intent,
    target_intent,
    validated_choice,
)
from contractforge_core.semantic.models import NamingIntent, SemanticContract, ShapeIntent, TransformIntent, WriteIntent


def semantic_contract_from_mapping(contract: dict[str, Any]) -> SemanticContract:
    """Build a semantic contract from a ContractForge-style mapping."""
    contract = validate_contract(contract)
    source = validate_source_contract(contract.get("source"))
    access = validate_access_contract(contract.get("access"))
    annotations = validate_annotations_contract(contract.get("annotations"))
    operations = validate_operations_contract(contract.get("operations"))
    execution = validate_execution_contract(contract.get("execution"))
    naming = validate_naming_contract(contract.get("naming"))
    quality_rules = validate_quality_rules_contract(contract.get("quality_rules"))
    transform = validate_transform_contract(contract.get("transform"))
    shape = validate_shape_contract(contract.get("shape") or nested_shape(transform))
    schemas = _schemas(contract)
    shape = _resolve_shape_schema_refs(shape, schemas)
    transform = _resolve_transform_shape_schema_refs(transform, schemas)

    mode = canonical_write_mode(str(contract.get("mode") or "append"))
    if not is_valid_write_mode(mode):
        raise ValueError(f"mode must be one of {sorted(PUBLIC_WRITE_MODES)} or custom:<name>")
    schema_policy = validated_choice(
        contract.get("schema_policy") or "permissive",
        VALID_SCHEMA_POLICIES,
        "schema_policy",
    )

    return SemanticContract(
        source=source_intent(source),
        target=target_intent(contract),
        write=WriteIntent(
            mode=mode,
            schema_policy=schema_policy,
            merge_keys=as_tuple(contract.get("merge_keys")),
            hash_strategy=contract.get("hash_strategy", "explicit"),
            hash_keys=as_tuple(contract.get("hash_keys")),
            hash_exclude_columns=as_tuple(contract.get("hash_exclude_columns")),
            scd2_change_columns=as_tuple(contract.get("scd2_change_columns")),
            scd2_effective_from_column=contract.get("scd2_effective_from_column"),
            scd2_sequence_by=contract.get("scd2_sequence_by"),
            scd2_late_arriving_policy=contract.get("scd2_late_arriving_policy", "apply"),
            scd2_apply_as_deletes=contract.get("scd2_apply_as_deletes"),
        ),
        quality=quality_intents(quality_rules),
        governance=governance_intent(contract, access, annotations),
        operations=operations_intent(contract, operations, source, execution),
        shape=ShapeIntent(raw=shape) if isinstance(shape, dict) else None,
        transform=TransformIntent(raw=transform) if isinstance(transform, dict) else None,
        naming=NamingIntent(raw=naming) if isinstance(naming, dict) else None,
        extensions=_extensions(contract, quality_rules),
    )


def _extensions(contract: dict[str, Any], quality_rules: dict[str, Any] | None) -> dict[str, Any] | None:
    extensions = dict(contract.get("extensions") or {}) if isinstance(contract.get("extensions"), dict) else {}
    custom_quality = quality_rules.get("custom") if isinstance(quality_rules, dict) else None
    if custom_quality:
        quality = dict(extensions.get("quality") or {})
        quality["custom"] = custom_quality
        extensions["quality"] = quality
    return extensions or None

def _schemas(contract: dict[str, Any]) -> dict[str, str]:
    value = contract.get("schemas")
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items()}


def _resolve_transform_shape_schema_refs(transform: dict[str, Any] | None, schemas: dict[str, str]) -> dict[str, Any] | None:
    if not isinstance(transform, dict) or not isinstance(transform.get("shape"), dict):
        return transform
    resolved = dict(transform)
    resolved["shape"] = _resolve_shape_schema_refs(resolved["shape"], schemas)
    return resolved


def _resolve_shape_schema_refs(shape: dict[str, Any] | None, schemas: dict[str, str]) -> dict[str, Any] | None:
    if not isinstance(shape, dict) or not shape.get("parse_json"):
        return shape
    resolved = dict(shape)
    resolved["parse_json"] = [_resolve_parse_json_config(item, schemas, idx) for idx, item in enumerate(shape["parse_json"])]
    return resolved


def _resolve_parse_json_config(config: dict[str, Any], schemas: dict[str, str], idx: int) -> dict[str, Any]:
    item = dict(config)
    schema = str(item.get("schema") or "").strip()
    schema_ref = str(item.get("schema_ref") or "").strip()
    if schema and schema_ref:
        raise ValueError("shape.parse_json must declare schema or schema_ref, not both")
    if schema_ref:
        if not schemas:
            return item
        if schema_ref not in schemas:
            raise ValueError(f"shape.parse_json[{idx}].schema_ref={schema_ref!r} does not exist in schemas")
        item["schema"] = schemas[schema_ref]
    elif not schema:
        raise ValueError("shape.parse_json requires schema or schema_ref")
    return item
