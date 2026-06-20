"""Fabric source connector support declarations."""

from __future__ import annotations

from typing import Any

from contractforge_core.connectors.registry import CONNECTOR_CATALOG
from contractforge_fabric.sources.classification import FabricSourceClassification, classify_fabric_source

_NON_RUNTIME_SOURCE_TYPES = frozenset({"connection"})


def fabric_source_support(source: dict[str, Any] | str) -> dict[str, Any]:
    """Return Fabric Lakehouse support metadata for a source connector."""

    return _entry(classify_fabric_source(source))


def list_fabric_source_support() -> tuple[dict[str, Any], ...]:
    sources = tuple(name for name in CONNECTOR_CATALOG if name not in _NON_RUNTIME_SOURCE_TYPES)
    return tuple(fabric_source_support(source) for source in sources)


def _entry(classification: FabricSourceClassification) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "adapter": "fabric",
        "source_type": classification.source_type,
        "status": classification.status,
        "note": classification.note,
        "renderable": classification.renderable,
    }
    if classification.native_mapping:
        entry["native_mapping"] = classification.native_mapping
    return entry
