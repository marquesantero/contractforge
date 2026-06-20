"""AWS artifact and table naming helpers."""

from __future__ import annotations

import re

from contractforge_core.semantic import SemanticContract

_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_]+")


def artifact_prefix(contract: SemanticContract) -> str:
    namespace = (contract.target.namespace or "default").replace(".", "_")
    return _safe_name(f"{namespace}_{contract.target.name}")


def glue_database_name(contract: SemanticContract) -> str:
    namespace = contract.target.namespace or "default"
    parts = [part for part in namespace.split(".") if part]
    return _safe_name("_".join(parts) if parts else "default")


def iceberg_table_name(contract: SemanticContract) -> str:
    return f"glue_catalog.{glue_database_name(contract)}.{_safe_name(contract.target.name)}"


def glue_table_name(contract: SemanticContract) -> str:
    return _safe_name(contract.target.name)


def _safe_name(value: str) -> str:
    text = _SAFE_NAME_RE.sub("_", str(value).strip())
    text = text.strip("_")
    return text or "contractforge"
