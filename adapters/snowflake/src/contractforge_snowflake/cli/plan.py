"""Plan command handler."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def add_plan_parser(subcommands: Any) -> None:
    parser = subcommands.add_parser("plan", help="Plan a ContractForge contract for Snowflake.")
    parser.add_argument("contract", type=Path)
    parser.add_argument("--environment", type=Path)


def handle_plan(args: argparse.Namespace) -> int:
    from contractforge_snowflake.api import plan_snowflake_contract
    from contractforge_snowflake.cli._helpers import _load_optional_yaml, _load_yaml

    result = plan_snowflake_contract(_load_yaml(args.contract), environment=_load_optional_yaml(args.environment))
    print(json.dumps({"status": result.status, "warnings": [w.code for w in result.warnings]}, indent=2))
    return 0 if result.status != "UNSUPPORTED" else 2
