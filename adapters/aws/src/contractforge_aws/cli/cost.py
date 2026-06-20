"""AWS operational cost report CLI command."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from contractforge_aws.cli.project_support import project_evidence_database
from contractforge_aws.cli.support import load_environment_input
from contractforge_aws.cost import CostModel, render_operational_cost_query


def add_cost_subparsers(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("cost-report", help="Render a query-only AWS Glue operational cost report.")
    parser.add_argument("--environment", type=Path)
    parser.add_argument("--database")
    parser.add_argument("--lookback-days", type=int, default=30)
    parser.add_argument("--group-by", action="append")
    parser.add_argument("--dpu-hour-usd", type=float)
    parser.add_argument("--currency", default="USD")
    parser.add_argument("--success-only", action="store_true")
    parser.add_argument("--limit", type=int, default=100)


def handle_cost_command(args: argparse.Namespace) -> int | None:
    if args.command != "cost-report":
        return None
    environment = load_environment_input(args.environment, None)
    database = args.database or project_evidence_database(environment)
    query = render_operational_cost_query(
        database=database,
        lookback_days=args.lookback_days,
        group_by=tuple(args.group_by) if args.group_by else None,
        cost_model=CostModel(dpu_hour_usd=args.dpu_hour_usd, currency=args.currency),
        include_failed=not args.success_only,
    )
    print(
        json.dumps(
            {
                "status": "QUERY_ONLY",
                "database": database,
                "lookback_days": args.lookback_days,
                "group_by": args.group_by,
                "include_failed": not args.success_only,
                "limit": args.limit,
                "cost_model": {
                    "enabled": args.dpu_hour_usd is not None,
                    "dpu_hour_usd": args.dpu_hour_usd,
                    "currency": args.currency,
                },
                "query": query,
                "rows": [],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0
