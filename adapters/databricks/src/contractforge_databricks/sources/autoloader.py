"""Databricks Auto Loader rendering for incremental file sources."""

from __future__ import annotations

from typing import Any


def render_autoloader_python(source: dict[str, Any], *, dataframe_name: str = "df") -> str:
    source_type = source.get("type")
    if source_type != "incremental_files":
        raise ValueError("Auto Loader rendering requires source.type incremental_files")
    path = source.get("path")
    if not path:
        raise ValueError("Auto Loader source requires path")
    file_format = source.get("format") or "json"
    options = {
        "cloudFiles.format": file_format,
        **{str(key): str(value) for key, value in source.get("options", {}).items()},
    }
    schema_location = source.get("schema_tracking_location")
    if schema_location:
        options["cloudFiles.schemaLocation"] = schema_location
    if source.get("schema_hints"):
        options["cloudFiles.schemaHints"] = source["schema_hints"]

    lines = [
        f"{dataframe_name} = (",
        "    spark.readStream",
        "    .format('cloudFiles')",
    ]
    for key, value in sorted(options.items()):
        lines.append(f"    .option({key!r}, {value!r})")
    lines.extend(
        [
            f"    .load({path!r})",
            ")",
        ]
    )
    checkpoint = source.get("progress_location")
    if checkpoint:
        lines.extend(
            [
                "",
                "# Use this checkpoint when writing the available-now stream.",
                f"checkpoint_location = {checkpoint!r}",
            ]
        )
    return "\n".join(lines) + "\n"
