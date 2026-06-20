"""Databricks REST auth headers: resolve secrets, then delegate to the core."""

from __future__ import annotations

from typing import Any

from contractforge_core.connectors.api.rest import rest_request_headers as _core_rest_request_headers
from contractforge_databricks.security import resolve_databricks_secret_placeholders


def rest_request_headers(
    source: dict[str, Any],
    incremental: dict[str, Any] | None = None,
    watermark: str | None = None,
) -> dict[str, str]:
    """Resolve Databricks secret placeholders in auth, then build headers via the core."""

    resolved = dict(source)
    if resolved.get("auth") is not None:
        resolved["auth"] = resolve_databricks_secret_placeholders(resolved.get("auth"))
    return _core_rest_request_headers(resolved, incremental, watermark)
