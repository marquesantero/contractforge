"""Run command handler."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def add_run_parser(subcommands: Any) -> None:
    parser = subcommands.add_parser("run", help="Run or dry-run a published Snowflake contract.")
    parser.add_argument("--contract-uri", required=True)
    parser.add_argument("--environment-uri")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--connect-options", type=Path)


def handle_run(args: argparse.Namespace) -> int:
    from contractforge_snowflake.cli._helpers import _run_contract

    result = _run_contract(args)
    print(json.dumps(result, indent=2))
    return 0
