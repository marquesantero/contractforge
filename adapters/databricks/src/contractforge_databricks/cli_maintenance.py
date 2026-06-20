"""Maintenance CLI commands for the Databricks adapter."""

from __future__ import annotations

import argparse
import json

from contractforge_databricks.cost import CostModel, build_operational_cost_report
from contractforge_databricks.maintenance import build_control_retention_plan


def add_maintenance_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    maintenance = subparsers.add_parser("maintenance", help="Render Databricks operational maintenance SQL")
    maintenance_sub = maintenance.add_subparsers(dest="maintenance_command", required=True)
    retention = maintenance_sub.add_parser("ctrl-retention")
    retention.add_argument("--catalog", default="main")
    retention.add_argument("--schema", default="ops")
    retention.add_argument("--retention-days", required=True, type=int)
    retention.add_argument("--target", dest="targets", action="append")
    retention.add_argument("--vacuum", action="store_true")
    retention.add_argument("--vacuum-retention-hours", type=int, default=168)
    retention.add_argument("--indent", type=int, default=2)
    cost = maintenance_sub.add_parser("cost-report")
    cost.add_argument("--catalog", default="main")
    cost.add_argument("--schema", default="ops")
    cost.add_argument("--lookback-days", type=int, default=30)
    cost.add_argument("--group-by", action="append")
    cost.add_argument("--dbu-per-hour", type=float)
    cost.add_argument("--currency-per-dbu", type=float)
    cost.add_argument("--currency", default="USD")
    cost.add_argument("--success-only", action="store_true")
    cost.add_argument("--limit", type=int, default=100)
    cost.add_argument("--indent", type=int, default=2)


def maintenance_command(args: argparse.Namespace) -> int:
    if args.maintenance_command == "cost-report":
        return _cost_report(args)
    if args.maintenance_command != "ctrl-retention":
        raise ValueError(f"unsupported maintenance command: {args.maintenance_command}")
    plan = build_control_retention_plan(
        catalog=args.catalog,
        schema=args.schema,
        retention_days=args.retention_days,
        vacuum=args.vacuum,
        vacuum_retention_hours=args.vacuum_retention_hours,
        targets=args.targets,
    )
    print(json.dumps({"status": "DRY_RUN", "plan": plan}, indent=args.indent, sort_keys=True, default=str))
    return 0


def _cost_report(args: argparse.Namespace) -> int:
    report = build_operational_cost_report(
        catalog=args.catalog,
        schema=args.schema,
        lookback_days=args.lookback_days,
        group_by=tuple(args.group_by or ("target_table", "mode", "status")),
        cost_model=CostModel(
            dbu_per_hour=args.dbu_per_hour,
            currency_per_dbu=args.currency_per_dbu,
            currency=args.currency,
        ),
        include_failed=not args.success_only,
        query_only=True,
        limit=args.limit,
    )
    print(json.dumps(report, indent=args.indent, sort_keys=True, default=str))
    return 0
