"""Public source contract facade."""

from __future__ import annotations

from typing import Any, Union

from pydantic import ValidationError

from contractforge_core.contracts.base import contract_validation_error
from contractforge_core.contracts.source_connector import ConnectorExtensionMap, ConnectorSourceContract
from contractforge_core.contracts.source_generic import (
    GenericSourceContract,
    SourceDiscoveryContract,
    SourceStateContract,
    SourceStateLocationContract,
)

SourceContract = Union[ConnectorSourceContract, GenericSourceContract]


def validate_source_contract(value: Any) -> dict[str, Any]:
    """Validate a source contract and return a normalized dict."""
    if not isinstance(value, dict):
        return value

    source_type = value.get("type")
    try:
        if source_type == "connector":
            source = ConnectorSourceContract.model_validate(value).model_dump(exclude_none=True, by_alias=True)
            _validate_schema_declaration(source)
            return source
        if source_type:
            source = GenericSourceContract.model_validate(value).model_dump(exclude_none=True, by_alias=True)
            _validate_schema_declaration(source)
            return source
    except ValidationError as exc:
        raise contract_validation_error(exc, prefix="source") from exc
    return value


def _validate_schema_declaration(source: dict[str, Any]) -> None:
    read = source.get("read") if isinstance(source.get("read"), dict) else {}
    options = source.get("options") if isinstance(source.get("options"), dict) else {}
    read_schema = str(read.get("schema") or "").strip()
    options_schema = str(options.get("schema") or "").strip()
    if options_schema and read_schema and options_schema != read_schema:
        raise ValueError("source.options.schema conflicts with source.read.schema")
    if options_schema and not read_schema:
        raise ValueError("source.options.schema is an adapter option; declare source.read.schema instead")


__all__ = [
    "ConnectorExtensionMap",
    "ConnectorSourceContract",
    "GenericSourceContract",
    "SourceDiscoveryContract",
    "SourceStateContract",
    "SourceStateLocationContract",
    "SourceContract",
    "validate_source_contract",
]
