"""Render Fabric notebook JDBC source readers."""

from __future__ import annotations

from typing import Any

from contractforge_core.connectors import jdbc_common_options
from contractforge_fabric.security import render_secret_aware_literal

_JDBC_RENDERABLE_CONNECTORS = {"jdbc", "sqlserver", "postgres"}


def is_fabric_jdbc_source(source: dict[str, Any]) -> bool:
    connector = str(source.get("connector") or source.get("type") or "").strip().lower()
    return connector in _JDBC_RENDERABLE_CONNECTORS


def render_jdbc_source_statement(source: dict[str, Any], *, dataframe_name: str = "df") -> str:
    options = _fabric_jdbc_options(source)
    return "\n".join(
        [
            f"_cf_jdbc_options = {_render_value(options)}",
            f"{dataframe_name} = spark.read.format('jdbc').options(**_cf_jdbc_options).load()",
        ]
    )


def _fabric_jdbc_options(source: dict[str, Any]) -> dict[str, str]:
    options = jdbc_common_options(source)
    connector = str(source.get("connector") or source.get("type") or "").strip().lower()
    url = str(options.get("url") or "")
    if connector == "sqlserver" or url.lower().startswith("jdbc:sqlserver:"):
        options.setdefault("driver", "com.microsoft.sqlserver.jdbc.SQLServerDriver")
    if connector == "postgres" or url.lower().startswith("jdbc:postgresql:"):
        options.setdefault("driver", "org.postgresql.Driver")
    return options


def _render_value(value: Any) -> str:
    if isinstance(value, dict):
        body = ", ".join(f"{key!r}: {_render_value(item)}" for key, item in value.items())
        return "{" + body + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_render_value(item) for item in value) + "]"
    if isinstance(value, str):
        return render_secret_aware_literal(value)
    return repr(value)


__all__ = ["is_fabric_jdbc_source", "render_jdbc_source_statement"]
