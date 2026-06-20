"""Databricks Delta Sharing source rendering."""

from __future__ import annotations

from typing import Any

from contractforge_core.connectors import delta_share_options, is_delta_share_source as is_delta_share_source
from contractforge_databricks.security import redact_value


def render_delta_share_python(source: dict[str, Any], *, dataframe_name: str = "df") -> str:
    options = delta_share_options(source)
    lines = [
        f"{dataframe_name} = (",
        "    spark.read",
        "    .format('deltaSharing')",
    ]
    for key, value in sorted(options.items()):
        lines.append(f"    .option({key!r}, {value!r})")
    lines.extend([")", "", f"delta_share_options_review = {redact_value(options)!r}"])
    return "\n".join(lines) + "\n"
