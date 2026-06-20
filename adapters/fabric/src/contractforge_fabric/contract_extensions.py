"""Fabric contract extension utilities."""

from __future__ import annotations

from typing import Any


FABRIC_EXTENSION_FIELDS = {
    "allow_type_widening",
    "access_apply",
    "bootstrap_evidence_tables",
    "governance_apply",
    "lock_enabled",
    "lock_owner",
    "lock_ttl_minutes",
    "source_runtime_path",
    "storage_account_key_secret",
}


def fabric_extensions(contract: Any) -> dict[str, Any]:
    extensions = getattr(contract, "extensions", None)
    if not isinstance(extensions, dict):
        return {}
    fabric = extensions.get("fabric")
    return dict(fabric) if isinstance(fabric, dict) else {}


def fabric_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def fabric_positive_int(value: object, *, default: int) -> int:
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


__all__ = ["FABRIC_EXTENSION_FIELDS", "fabric_bool", "fabric_extensions", "fabric_positive_int"]
