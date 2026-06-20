"""Fabric logical naming helpers."""

from __future__ import annotations

from contractforge_core.security import redact_value
from contractforge_core.semantic import SemanticContract


def target_table_name(contract: SemanticContract) -> str:
    parts = [part for part in (contract.target.namespace or "").split(".") if part]
    if len(parts) > 1:
        parts = parts[1:]
    parts.append(contract.target.name)
    return ".".join(parts)


def source_display_name(contract: SemanticContract) -> str:
    source = contract.source.raw or {}
    if str(source.get("type") or "").casefold() == "sql":
        return str(source.get("name") or "sql_query")
    value = (
        source.get("name")
        or source.get("table")
        or source.get("ref")
        or source.get("table_ref")
        or source.get("path")
        or source.get("url")
        or contract.source.location
        or contract.source.name
    )
    return str(redact_value(value))


def openlineage_namespace(contract: SemanticContract, *, namespace: str | None = None) -> str:
    if namespace:
        return namespace
    workspace = (contract.target.namespace or contract.target.layer or "workspace").split(".", 1)[0]
    return f"fabric://{workspace}"


__all__ = ["openlineage_namespace", "source_display_name", "target_table_name"]
