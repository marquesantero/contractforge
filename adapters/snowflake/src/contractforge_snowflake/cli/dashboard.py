"""Dashboard command handler."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def add_dashboard_parser(subcommands: Any) -> None:
    parser = subcommands.add_parser("dashboard", help="Render Snowflake control-table dashboard artifacts.")
    parser.add_argument("--database", default="CONTRACTFORGE")
    parser.add_argument("--schema", default="CF_EVIDENCE")
    parser.add_argument("--lookback-days", type=int, default=7)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--indent", type=int, default=2)


def handle_dashboard(args: argparse.Namespace) -> int:
    from contractforge_snowflake.cli._helpers import _write_artifacts
    from contractforge_snowflake.dashboards import render_control_dashboard_artifacts

    artifacts = render_control_dashboard_artifacts(
        database=args.database,
        schema=args.schema,
        lookback_days=args.lookback_days,
    )
    if args.output_dir:
        _write_artifacts(args.output_dir, artifacts)
        print(json.dumps({"status": "SUCCESS", "written": sorted(artifacts)}, indent=args.indent))
        return 0
    print(json.dumps(artifacts, indent=args.indent, sort_keys=True))
    return 0
