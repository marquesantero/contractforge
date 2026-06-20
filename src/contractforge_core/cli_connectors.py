"""Connector catalog commands for the core ContractForge CLI."""

from __future__ import annotations

import json
from typing import Any

from contractforge_core.connectors import (
    diagnose_source_connectors,
    list_source_connector_details,
    source_connector_details,
)


def handle_connector_command(args: Any) -> int | None:
    if args.command != "connectors":
        return None
    if args.connector_command == "list":
        return _print(list_source_connector_details(), args.indent)
    if args.connector_command == "show":
        return _print([source_connector_details(name) for name in args.names], args.indent)
    if args.connector_command == "doctor":
        return _print({"status": "SUCCESS", "items": diagnose_source_connectors(args.names)}, args.indent)
    raise ValueError(f"unsupported connectors command: {args.connector_command}")


def _print(payload: object, indent: int) -> int:
    print(json.dumps(payload, indent=indent, sort_keys=True, default=str))
    return 0
