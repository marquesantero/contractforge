"""Static contract validation helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from contractforge_core.contracts.normalize import semantic_contract_from_mapping
from contractforge_core.contracts.shape_validation import validate_shape_semantics
from contractforge_core.contracts.source_validation import validate_source_semantics


def validate_plan_shape(contract: Mapping[str, Any]) -> None:
    """Validate a ContractForge mapping without executing a platform runtime."""

    semantic_contract_from_mapping(dict(contract))
    source = contract.get("source")
    if isinstance(source, dict):
        validate_source_semantics(source)
    shape = contract.get("shape")
    if isinstance(shape, dict):
        validate_shape_semantics(shape)
    transform = contract.get("transform")
    if isinstance(transform, dict):
        validate_shape_semantics(transform.get("shape"), context="transform.shape")
