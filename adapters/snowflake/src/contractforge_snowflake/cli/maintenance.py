"""Maintenance command handler."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def add_maintenance_parser(subcommands: Any) -> None:
    parser = subcommands.add_parser("maintenance", help="Render or execute Snowflake operational maintenance SQL.")
    maintenance_subcommands = parser.add_subparsers(dest="maintenance_command", required=True)
    retention = maintenance_subcommands.add_parser("ctrl-retention")
    retention.add_argument("--database", default="CONTRACTFORGE")
    retention.add_argument("--schema", default="CF_EVIDENCE")
    retention.add_argument("--retention-days", required=True, type=int)
    retention.add_argument("--target", dest="targets", action="append")
    retention.add_argument("--execute", action="store_true")
    retention.add_argument("--connect-options", type=Path)
    retention.add_argument("--indent", type=int, default=2)


def handle_maintenance(args: argparse.Namespace) -> int:
    from contractforge_snowflake.cli import _connect
    from contractforge_snowflake.cli._helpers import _load_optional_yaml
    from contractforge_snowflake.maintenance import build_control_retention_plan, execute_control_retention_plan

    if args.maintenance_command != "ctrl-retention":
        raise ValueError(f"unsupported maintenance command: {args.maintenance_command}")
    plan = build_control_retention_plan(
        database=args.database,
        schema=args.schema,
        retention_days=args.retention_days,
        targets=args.targets,
    )
    if not args.execute:
        print(json.dumps({"status": "DRY_RUN", "plan": plan}, indent=args.indent, sort_keys=True, default=str))
        return 0
    connection = _connect(_load_optional_yaml(args.connect_options))
    try:
        commands = execute_control_retention_plan(connection, plan)
    finally:
        if hasattr(connection, "close"):
            connection.close()
    print(json.dumps({"status": "SUCCESS", "commands": commands}, indent=args.indent, sort_keys=True, default=str))
    return 0
