"""JSON Schema generation for public contract models."""

from __future__ import annotations

from typing import Any

from contractforge_core.contracts.environment import EnvironmentContractModel
from contractforge_core.contracts.execution import ExecutionContractModel
from contractforge_core.contracts.governance import (
    AccessContractModel,
    AnnotationsContractModel,
    OperationsContractModel,
)
from contractforge_core.contracts.quality import QualityRulesContractModel
from contractforge_core.config import PUBLIC_WRITE_MODES
from contractforge_core.contracts.root import SemanticContractInputModel
from contractforge_core.contracts.source import ConnectorSourceContract, GenericSourceContract
from contractforge_core.contracts.transform import ShapeContractModel, TransformContractModel
from contractforge_core.contracts.naming import NamingContractModel


def contract_model_schemas() -> dict[str, dict[str, Any]]:
    """Return JSON Schema fragments generated from public Pydantic models."""
    contract_schema = SemanticContractInputModel.model_json_schema()
    _overlay_public_mode_schema(contract_schema)
    return {
        "source.connector": ConnectorSourceContract.model_json_schema(),
        "source.generic": GenericSourceContract.model_json_schema(),
        "annotations": AnnotationsContractModel.model_json_schema(),
        "operations": OperationsContractModel.model_json_schema(),
        "access": AccessContractModel.model_json_schema(),
        "quality_rules": QualityRulesContractModel.model_json_schema(),
        "naming": NamingContractModel.model_json_schema(),
        "contract": contract_schema,
        "environment": EnvironmentContractModel.model_json_schema(),
        "execution": ExecutionContractModel.model_json_schema(),
        "shape": ShapeContractModel.model_json_schema(),
        "transform": TransformContractModel.model_json_schema(),
    }


def yaml_schema() -> dict[str, Any]:
    """Return the aggregated JSON Schema for ContractForge contract files."""
    schema = SemanticContractInputModel.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://github.com/marquesantero/contractforge-core/schema.json"
    schema["title"] = "ContractForge Core Contract Schema"
    schema.setdefault("required", [])
    for required_field in ("source", "target"):
        if required_field not in schema["required"]:
            schema["required"].append(required_field)
    properties_overlay = schema.setdefault("properties", {})
    target_schema = dict(properties_overlay.get("target") or {})
    target_schema.setdefault("required", [])
    if "table" not in target_schema["required"]:
        target_schema["required"] = sorted({*target_schema["required"], "table"})
    properties_overlay["target"] = target_schema
    _overlay_public_mode_schema(schema)
    return schema


def _overlay_public_mode_schema(schema: dict[str, Any]) -> None:
    properties = schema.setdefault("properties", {})
    properties["mode"] = {
        "default": "append",
        "description": "ContractForge write mode. Values are public contract aliases; custom:<name> is adapter-owned and non-portable.",
        "anyOf": [
            {"enum": sorted(PUBLIC_WRITE_MODES)},
            {"type": "string", "pattern": r"^custom:[A-Za-z0-9_.-]+$"},
        ],
    }
