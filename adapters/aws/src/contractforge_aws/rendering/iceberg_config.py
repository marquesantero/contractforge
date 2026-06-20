"""AWS Iceberg rendering configuration helpers."""

from __future__ import annotations

from typing import Any

from contractforge_core.semantic import SemanticContract
from contractforge_aws.contract_extensions import aws_extensions


def resolve_iceberg_warehouse(
    contract: SemanticContract,
    *,
    environment_parameters: dict[str, object] | None = None,
) -> str | None:
    """Resolve the Iceberg warehouse from environment defaults plus contract overrides."""

    iceberg: dict[str, Any] = {}
    env_iceberg = (environment_parameters or {}).get("iceberg")
    if isinstance(env_iceberg, dict):
        iceberg.update(env_iceberg)
    contract_iceberg = aws_extensions(contract).get("iceberg")
    if isinstance(contract_iceberg, dict):
        iceberg.update(contract_iceberg)
    warehouse = str(iceberg.get("warehouse") or "").strip()
    if not warehouse:
        return None
    _validate_warehouse_uri(warehouse)
    return warehouse


def render_create_namespace_sql(namespace: str, *, warehouse: str | None = None) -> str:
    """Render namespace creation, optionally pinning a deterministic S3 location."""

    sql = f"CREATE DATABASE IF NOT EXISTS glue_catalog.{_quote_identifier(namespace)}"
    if warehouse:
        sql += f" LOCATION {_sql_string(_namespace_location(warehouse, namespace))}"
    return sql


def _validate_warehouse_uri(value: str) -> None:
    if not value.startswith("s3://"):
        raise ValueError("extensions.aws.iceberg.warehouse must be an s3:// URI")
    lowered = value.lower()
    unresolved_markers = ("replace-with", "example-", "{{", "}}", "<", ">")
    if any(marker in lowered for marker in unresolved_markers):
        raise ValueError("extensions.aws.iceberg.warehouse contains an unresolved placeholder")


def _namespace_location(warehouse: str, namespace: str) -> str:
    return f"{warehouse.rstrip('/')}/{namespace}.db/"


def _quote_identifier(value: str | None) -> str:
    if value is None:
        raise ValueError("identifier is required")
    text = str(value).strip()
    if not text:
        raise ValueError("identifier must not be empty")
    return f"`{text.replace('`', '``')}`"


def _sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"
