"""Cost reconciliation command handler."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def add_cost_parser(subcommands: Any) -> None:
    parser = subcommands.add_parser("reconcile-cost", help="Record delayed Snowflake query-history cost evidence.")
    _add_cost_args(parser)
    canonical = subcommands.add_parser("cost-report", help="Record delayed Snowflake query-history cost evidence.")
    _add_cost_args(canonical)


def _add_cost_args(parser: Any) -> None:
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--target-table", required=True)
    parser.add_argument("--environment", type=Path)
    parser.add_argument("--connect-options", type=Path)
    parser.add_argument("--wait", action="store_true")
    parser.add_argument("--poll-interval-seconds", type=float, default=30.0)
    parser.add_argument("--max-wait-seconds", type=float, default=0.0)


def handle_cost(args: argparse.Namespace) -> int:
    from contractforge_snowflake.cli import _connect
    from contractforge_snowflake.cli._helpers import _load_optional_yaml
    from contractforge_snowflake.runtime import reconcile_snowflake_cost_evidence

    connection = _connect(_load_optional_yaml(args.connect_options))
    try:
        result = reconcile_snowflake_cost_evidence(
            session=connection,
            environment=_load_optional_yaml(args.environment),
            run_id=args.run_id,
            target_table=args.target_table,
            wait=args.wait,
            poll_interval_seconds=args.poll_interval_seconds,
            max_wait_seconds=args.max_wait_seconds,
        )
    finally:
        if hasattr(connection, "close"):
            connection.close()
    print(
        json.dumps(
            {
                "status": result.status,
                "query_count": result.query_count,
                "warnings": result.warnings,
                "commands": result.commands,
            },
            indent=2,
        )
    )
    return 0
