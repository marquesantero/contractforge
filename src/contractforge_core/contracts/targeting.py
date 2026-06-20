"""Platform-neutral target naming helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from contractforge_core.contracts.normalize import semantic_contract_from_mapping
from contractforge_core.semantic import SemanticContract


def target_schema_name(contract: SemanticContract | Mapping[str, Any]) -> str:
    semantic = _semantic_contract(contract)
    if semantic.target.namespace:
        return semantic.target.namespace.split(".")[-1]
    return semantic.target.layer


def target_full_table_name(contract: SemanticContract | Mapping[str, Any]) -> str:
    semantic = _semantic_contract(contract)
    parts = [part for part in ((semantic.target.namespace or "").split(".")) if part]
    parts.append(semantic.target.name)
    return ".".join(parts)


def _semantic_contract(contract: SemanticContract | Mapping[str, Any]) -> SemanticContract:
    if isinstance(contract, SemanticContract):
        return contract
    if isinstance(contract, Mapping):
        return semantic_contract_from_mapping(dict(contract))
    raise TypeError("contract must be a SemanticContract or mapping")
