"""Lineage command handler."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def add_lineage_parser(subcommands: Any) -> None:
    parser = subcommands.add_parser(
        "reconcile-lineage",
        help="Record delayed Snowflake Access History lineage evidence.",
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--environment", type=Path)
    parser.add_argument("--connect-options", type=Path)


def handle_lineage(args: argparse.Namespace) -> int:
    from contractforge_snowflake.cli import _connect
    from contractforge_snowflake.cli._helpers import _load_optional_yaml
    from contractforge_snowflake.runtime import reconcile_snowflake_access_history_lineage

    connection = _connect(_load_optional_yaml(args.connect_options))
    try:
        result = reconcile_snowflake_access_history_lineage(
            session=connection,
            environment=_load_optional_yaml(args.environment),
            run_id=args.run_id,
        )
    finally:
        if hasattr(connection, "close"):
            connection.close()
    print(
        json.dumps(
            {
                "status": result.status,
                "row_count": result.row_count,
                "warnings": result.warnings,
                "commands": result.commands,
            },
            indent=2,
        )
    )
    return 0
