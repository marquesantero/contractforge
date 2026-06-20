"""Databricks JDBC source rendering."""

from __future__ import annotations

from typing import Any

from contractforge_core.connectors import JDBC_CONNECTORS, jdbc_common_options
from contractforge_databricks.security import assert_no_inline_jdbc_secrets, redact_value


def render_jdbc_python(source: dict[str, Any], *, dataframe_name: str = "df") -> str:
    connector = source.get("connector") or source.get("type")
    if connector not in JDBC_CONNECTORS and source.get("type") != "jdbc":
        raise ValueError("JDBC rendering requires a JDBC source connector")
    options = jdbc_options(source)
    lines = [
        f"{dataframe_name} = (",
        "    spark.read",
        "    .format('jdbc')",
    ]
    for key, value in sorted(options.items()):
        lines.append(f"    .option({key!r}, {value!r})")
    lines.extend([")", ""])
    lines.append("# Rendered JDBC options with sensitive values redacted for review:")
    lines.append(f"jdbc_options_review = {redact_value(options)!r}")
    return "\n".join(lines) + "\n"


def jdbc_options(source: dict[str, Any]) -> dict[str, str]:
    options = jdbc_common_options(source)
    assert_no_inline_jdbc_secrets(options)
    return options
