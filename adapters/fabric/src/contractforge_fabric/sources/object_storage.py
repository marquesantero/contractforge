"""Fabric object-storage source rendering helpers."""

from __future__ import annotations

import re
from typing import Any

from contractforge_core.connectors import OBJECT_STORAGE_TYPES
from contractforge_fabric.security import render_secret_aware_literal


_FABRIC_OBJECT_STORAGE_SCHEMES = ("abfss://", "wasbs://", "wasb://")


def is_fabric_object_storage_source(source: dict[str, Any]) -> bool:
    return _source_type(source) in OBJECT_STORAGE_TYPES


def fabric_object_storage_runtime_path(
    source: dict[str, Any],
    fabric_extensions: dict[str, Any] | None = None,
) -> str | None:
    """Return the Fabric-readable path for an object-storage source.

    Object-storage contracts keep the portable source descriptor. Fabric can
    read the source when the contract points at a Fabric-readable external path
    directly, or when an adapter binding supplies the Lakehouse shortcut/staged
    path through ``extensions.fabric.source_runtime_path``.
    """

    fabric = dict(fabric_extensions or {})
    if not fabric:
        extensions = source.get("extensions") if isinstance(source.get("extensions"), dict) else {}
        fabric = extensions.get("fabric") if isinstance(extensions.get("fabric"), dict) else {}
    runtime_path = fabric.get("source_runtime_path")
    if isinstance(runtime_path, str) and runtime_path.strip():
        return runtime_path.strip()

    path = str(source.get("path") or "").strip()
    if _is_fabric_readable_object_path(path):
        return path
    return None


def is_fabric_object_storage_renderable(source: dict[str, Any]) -> bool:
    return fabric_object_storage_runtime_path(source) is not None


def source_with_fabric_runtime_binding(
    source: dict[str, Any],
    fabric_extensions: dict[str, Any] | None,
) -> dict[str, Any]:
    if not is_fabric_object_storage_source(source):
        return source
    runtime_path = fabric_object_storage_runtime_path(source, fabric_extensions)
    if not runtime_path:
        return source
    bound = dict(source)
    extensions = dict(bound.get("extensions") or {}) if isinstance(bound.get("extensions"), dict) else {}
    fabric = dict(fabric_extensions or {})
    fabric.update(dict(extensions.get("fabric") or {}) if isinstance(extensions.get("fabric"), dict) else {})
    fabric["source_runtime_path"] = runtime_path
    extensions["fabric"] = fabric
    bound["extensions"] = extensions
    return bound


def render_object_storage_credential_setup(source: dict[str, Any]) -> str:
    if not is_fabric_object_storage_source(source):
        return ""
    extensions = source.get("extensions") if isinstance(source.get("extensions"), dict) else {}
    fabric = extensions.get("fabric") if isinstance(extensions.get("fabric"), dict) else {}
    secret = fabric.get("storage_account_key_secret")
    if not isinstance(secret, str) or not secret.strip():
        return ""
    runtime_path = fabric_object_storage_runtime_path(source)
    account = str(fabric.get("storage_account") or _storage_account_from_runtime_path(runtime_path or "")).strip()
    if not account:
        raise ValueError("Fabric private object-storage source requires extensions.fabric.storage_account")
    conf_key = f"fs.azure.account.key.{account}.blob.core.windows.net"
    return f"spark.conf.set({conf_key!r}, {render_secret_aware_literal(secret)})"


def _is_fabric_readable_object_path(path: str) -> bool:
    normalized = path.strip()
    if not normalized:
        return False
    if normalized.startswith(_FABRIC_OBJECT_STORAGE_SCHEMES):
        return True
    return normalized.startswith("Files/") or normalized.startswith("/Files/")


def _storage_account_from_runtime_path(path: str) -> str | None:
    match = re.search(r"@([^.@]+)\.blob\.core\.windows\.net", path)
    return match.group(1) if match else None


def _source_type(source: dict[str, Any]) -> str:
    return str(source.get("connector") or source.get("type") or "").strip().lower()


__all__ = [
    "fabric_object_storage_runtime_path",
    "is_fabric_object_storage_renderable",
    "render_object_storage_credential_setup",
    "is_fabric_object_storage_source",
    "source_with_fabric_runtime_binding",
]
