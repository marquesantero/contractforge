"""Snowflake resolution for core logical table references."""

from __future__ import annotations

from dataclasses import replace

from contractforge_core.connectors import LogicalTableReference, catalog_source_query, source_logical_table_reference
from contractforge_core.semantic import SemanticContract


def snowflake_table_ref_resolver(contract: SemanticContract):
    """Return a resolver that maps logical refs to Snowflake table names."""

    def _resolve(ref: LogicalTableReference) -> str:
        if ref.catalog and ref.schema:
            return f"{ref.catalog}.{ref.schema}.{ref.table}"
        if ref.schema:
            catalog = _target_catalog(contract)
            return f"{catalog}.{ref.schema}.{ref.table}" if catalog else f"{ref.schema}.{ref.table}"
        namespace = _namespace_for_layer(contract, ref.layer)
        return f"{namespace}.{ref.table}" if namespace else ref.table

    return _resolve


def resolve_snowflake_source_table_refs(contract: SemanticContract) -> dict | None:
    """Return source.raw with logical refs resolved to Snowflake table names."""

    if not contract.source.raw:
        return None
    source = dict(contract.source.raw)
    resolver = snowflake_table_ref_resolver(contract)
    table_ref = source_logical_table_reference(source)
    if table_ref is not None:
        source["table"] = resolver(table_ref)
        source.pop("ref", None)
        source.pop("table_ref", None)
    if source.get("query"):
        source["query"] = catalog_source_query(source, table_ref_resolver=resolver)
    return source


def contract_with_snowflake_source_refs(contract: SemanticContract) -> SemanticContract:
    source = resolve_snowflake_source_table_refs(contract)
    if source is None:
        return contract
    return replace(contract, source=replace(contract.source, raw=source))


def _namespace_for_layer(contract: SemanticContract, layer: str) -> str | None:
    namespace = contract.target.namespace
    if not namespace:
        return None
    current_layer = contract.target.layer
    namespace_lower = namespace.lower()
    current_layer_lower = current_layer.lower()
    if namespace_lower.endswith(f"_{current_layer_lower}"):
        suffix = namespace[-len(current_layer) :]
        return f"{namespace[: -(len(current_layer) + 1)]}_{_match_case(layer, suffix)}"
    if namespace_lower.endswith(f".{current_layer_lower}"):
        suffix = namespace[-len(current_layer) :]
        return f"{namespace[: -(len(current_layer) + 1)]}.{_match_case(layer, suffix)}"
    return namespace


def _target_catalog(contract: SemanticContract) -> str | None:
    namespace = contract.target.namespace
    if not namespace or "." not in namespace:
        return None
    return namespace.split(".", 1)[0]


def _match_case(value: str, template: str) -> str:
    return value.upper() if template.isupper() else value


__all__ = [
    "contract_with_snowflake_source_refs",
    "resolve_snowflake_source_table_refs",
    "snowflake_table_ref_resolver",
]
