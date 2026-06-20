"""Connection option helpers for Snowflake smoke CLIs."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def smoke_connect_options(
    *,
    connection: str | None,
    connect_options: Path | None,
    load_connect_options: Callable[[Path | None], dict[str, Any] | None],
) -> dict[str, Any] | None:
    options = load_connect_options(connect_options)
    if options is None:
        return {"connection_name": connection} if connection else None
    if connection and "connection_name" not in options:
        return {**options, "connection_name": connection}
    return options


def require_smoke_connection(*, connection: str | None, connect_options: Path | None, command_name: str) -> None:
    if not connection and not connect_options:
        raise ValueError(f"{command_name} live execution requires --connect-options or --connection")
