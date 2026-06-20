"""Notebook runtime helpers for Fabric state evidence rendering."""

from __future__ import annotations

from typing import Any

from contractforge_core.semantic import SemanticContract
from contractforge_fabric.contract_extensions import fabric_bool, fabric_extensions, fabric_positive_int


def notebook_state_lock_options(contract: SemanticContract) -> dict[str, object]:
    extensions = fabric_extensions(contract)
    metadata = contract.operations.metadata if contract.operations else {}
    metadata = metadata if isinstance(metadata, dict) else {}
    lock_enabled = fabric_bool(extensions.get("lock_enabled", metadata.get("lock_enabled", False)))
    lock_owner = extensions.get("lock_owner", metadata.get("lock_owner"))
    ttl_minutes = extensions.get("lock_ttl_minutes", metadata.get("lock_ttl_minutes", 60))
    return {
        "enabled": lock_enabled,
        "owner": str(lock_owner) if lock_owner else None,
        "ttl_minutes": fabric_positive_int(ttl_minutes, default=60),
    }


def notebook_state_watermark_column(contract: SemanticContract) -> str | None:
    source = contract.source.raw or {}
    incremental = _mapping(source.get("incremental"))
    if incremental.get("watermark_column"):
        return str(incremental["watermark_column"])
    watermark = _mapping(source.get("watermark"))
    if watermark.get("column"):
        return str(watermark["column"])
    metadata = contract.operations.metadata if contract.operations else None
    watermark_columns = _mapping(metadata).get("watermark_columns")
    values = _as_list(watermark_columns)
    return values[0] if len(values) == 1 else None


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split("|") if item.strip()]
    return [str(item).strip() for item in value if str(item).strip()]  # type: ignore[union-attr]


__all__ = ["notebook_state_lock_options", "notebook_state_watermark_column"]
