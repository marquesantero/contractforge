"""Resolvers para fontes declarativas."""
from __future__ import annotations

from typing import Dict, Protocol, Tuple

from pyspark.sql import DataFrame

from ._spark import spark
from .plan import IngestionPlan, SourceSpec


class SourceResolver(Protocol):
    """Contrato de um resolver de source declarativo."""

    def resolve_stream(self, spec: SourceSpec, plan: IngestionPlan) -> Tuple[DataFrame, str]:
        """Resolve source como streaming DataFrame e devolve ``(df, label)``."""
        ...


SOURCE_RESOLVER_REGISTRY: Dict[str, SourceResolver] = {}


def register_source_resolver(source_type: str, resolver: SourceResolver, *, overwrite: bool = False) -> None:
    """Registra resolver declarativo por ``source.type``."""
    normalized = str(source_type or "").strip()
    if not normalized:
        raise ValueError("source_type não pode ser vazio")
    if not hasattr(resolver, "resolve_stream"):
        raise ValueError("resolver deve implementar resolve_stream(spec, plan)")
    if normalized in SOURCE_RESOLVER_REGISTRY and not overwrite:
        raise ValueError(f"source resolver já registrado: {normalized}")
    SOURCE_RESOLVER_REGISTRY[normalized] = resolver


def get_source_resolver(source_type: str) -> SourceResolver:
    """Retorna resolver registrado para ``source_type``."""
    normalized = str(source_type or "").strip()
    resolver = SOURCE_RESOLVER_REGISTRY.get(normalized)
    if resolver is None:
        raise ValueError(f"source.type={normalized!r} não tem resolver registrado")
    return resolver


class AutoloaderResolver:
    """Resolver Databricks Auto Loader (`cloudFiles`) em modo available_now."""

    def resolve_stream(self, spec: SourceSpec, plan: IngestionPlan) -> Tuple[DataFrame, str]:
        reader = (
            spark.readStream.format("cloudFiles")
            .option("cloudFiles.format", spec.format)
            .option("cloudFiles.schemaLocation", spec.schema_location)
            .option("cloudFiles.includeExistingFiles", "true" if spec.include_existing_files else "false")
            .options(**(spec.options or {}))
        )
        if spec.schema_hints:
            reader = reader.option("cloudFiles.schemaHints", spec.schema_hints)
        if spec.max_files_per_trigger is not None:
            reader = reader.option("cloudFiles.maxFilesPerTrigger", str(spec.max_files_per_trigger))
        return reader.load(spec.path), f"autoloader:{spec.path}"


register_source_resolver("autoloader", AutoloaderResolver())
