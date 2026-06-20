"""Databricks runtime source resolver registry."""

from __future__ import annotations

import re
from typing import Any, Protocol

_SOURCE_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
_CUSTOM_RESOLVERS: dict[str, "DatabricksSourceResolver"] = {}


class DatabricksSourceResolver(Protocol):
    def resolve(self, spark: Any, source: dict[str, Any]) -> Any:
        """Resolve a source mapping into a Databricks DataFrame-like object."""
        ...


def register_source_resolver(source_type: str, resolver: DatabricksSourceResolver, *, overwrite: bool = False) -> None:
    normalized = _normalize_source_name(source_type)
    if not hasattr(resolver, "resolve"):
        raise ValueError("resolver must implement resolve(spark, source)")
    if normalized in _CUSTOM_RESOLVERS and not overwrite:
        raise ValueError(f"source resolver already registered: {normalized}")
    _CUSTOM_RESOLVERS[normalized] = resolver


def unregister_source_resolver(source_type: str) -> None:
    _CUSTOM_RESOLVERS.pop(_normalize_source_name(source_type), None)


def get_source_resolver(source_type: str) -> DatabricksSourceResolver | None:
    return _CUSTOM_RESOLVERS.get(_normalize_source_name(source_type))


def list_source_resolvers() -> list[str]:
    return sorted(_CUSTOM_RESOLVERS)


def _normalize_source_name(source_type: str) -> str:
    normalized = str(source_type or "").strip()
    if not _SOURCE_NAME_RE.match(normalized):
        raise ValueError("source_type must start with a letter and contain only letters, numbers, '_' or '-'")
    return normalized
