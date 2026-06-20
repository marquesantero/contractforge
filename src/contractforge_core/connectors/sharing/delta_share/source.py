"""Platform-neutral Delta Sharing source helpers."""

from __future__ import annotations

from typing import Any


def is_delta_share_source(source: dict[str, Any]) -> bool:
    return source.get("type") == "delta_share" or source.get("connector") == "delta_share"


def delta_share_options(source: dict[str, Any]) -> dict[str, str]:
    options = {str(key): str(value) for key, value in source.get("options", {}).items()}
    profile_file = source.get("profile_file") or options.get("profileFile")
    table = source.get("table") or options.get("table")
    if not profile_file:
        raise ValueError("delta_share source requires profile_file or options.profileFile")
    if not table:
        raise ValueError("delta_share source requires table or options.table")
    options["profileFile"] = str(profile_file)
    options["table"] = str(table)
    return options
