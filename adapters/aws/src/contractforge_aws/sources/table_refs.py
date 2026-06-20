"""AWS Glue/Iceberg resolution for core logical table references."""

from __future__ import annotations

from dataclasses import replace

from contractforge_core.connectors import catalog_source_query, source_logical_table_reference
from contractforge_core.connectors import LogicalTableReference
from contractforge_core.semantic import SemanticContract
from contractforge_aws.rendering.names import glue_database_name


def aws_table_ref_resolver(contract: SemanticContract):
    """Return a resolver that maps logical refs to Glue Catalog Iceberg names."""

    def _resolve(ref: LogicalTableReference) -> str:
        if ref.catalog and ref.schema:
            return f"glue_catalog.{ref.catalog}_{ref.schema}.{ref.table}"
        if ref.schema:
            catalog = _target_catalog(contract)
            database = f"{catalog}_{ref.schema}" if catalog else ref.schema
            return f"glue_catalog.{database}.{ref.table}"
        return f"glue_catalog.{_database_for_layer(contract, ref.layer)}.{ref.table}"

    return _resolve


def resolve_aws_source_table_refs(contract: SemanticContract) -> dict | None:
    """Return source.raw with logical refs resolved to AWS Glue/Iceberg table names."""

    if not contract.source.raw:
        return None
    source = dict(contract.source.raw)
    resolver = aws_table_ref_resolver(contract)
    table_ref = source_logical_table_reference(source)
    if table_ref is not None:
        source["table"] = resolver(table_ref)
        source.pop("ref", None)
        source.pop("table_ref", None)
    if source.get("query"):
        source["query"] = catalog_source_query(source, table_ref_resolver=resolver)
    return source


def contract_with_aws_source_refs(contract: SemanticContract) -> SemanticContract:
    source = resolve_aws_source_table_refs(contract)
    if source is None:
        return contract
    return replace(contract, source=replace(contract.source, raw=source))


def _database_for_layer(contract: SemanticContract, layer: str) -> str:
    current_layer = contract.target.layer
    namespace = contract.target.namespace or "default"
    if namespace.endswith(f".{current_layer}"):
        namespace = f"{namespace[: -(len(current_layer) + 1)]}.{layer}"
    elif namespace.endswith(f"_{current_layer}"):
        namespace = f"{namespace[: -(len(current_layer) + 1)]}_{layer}"
    proxy = SemanticContract(
        source=contract.source,
        target=type(contract.target)(
            name=contract.target.name,
            layer=layer,
            namespace=namespace,
            domain=contract.target.domain,
            catalog_type=contract.target.catalog_type,
        ),
        write=contract.write,
    )
    return glue_database_name(proxy)


def _target_catalog(contract: SemanticContract) -> str | None:
    namespace = contract.target.namespace
    if not namespace or "." not in namespace:
        return None
    return namespace.split(".", 1)[0]
