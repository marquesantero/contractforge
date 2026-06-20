"""Canonical Databricks adapter CLI commands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from contractforge_databricks.api import plan_databricks_contract
from contractforge_databricks.cli_io import load_contract_input, load_mapping
from contractforge_databricks.cost import CostModel, build_operational_cost_report
from contractforge_databricks.sources import list_databricks_source_support


def add_standard_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    plan = subparsers.add_parser("plan", help="Plan a contract against the Databricks target")
    plan.add_argument("contract", type=Path)
    plan.add_argument("--environment", type=Path)
    plan.add_argument("--indent", type=int, default=2)

    cost = subparsers.add_parser("cost-report", help="Render a query-only Databricks operational cost report")
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

    subparsers.add_parser("sources", help="Print Databricks source support metadata")


def standard_command(args: argparse.Namespace) -> int | None:
    if args.command == "plan":
        return _plan_contract(args)
    if args.command == "cost-report":
        return _cost_report(args)
    if args.command == "sources":
        print(json.dumps(list(list_databricks_source_support()), indent=2, sort_keys=True, default=str))
        return 0
    return None


def _plan_contract(args: argparse.Namespace) -> int:
    contract, bundle_environment = load_contract_input(args.contract)
    environment = load_mapping(args.environment) if args.environment else bundle_environment
    result = plan_databricks_contract(contract, environment=environment)
    payload = {
        "status": result.status,
        "blockers": [{"code": item.code, "message": item.message} for item in result.blockers],
        "warnings": [{"code": item.code, "message": item.message} for item in result.warnings],
        "plan": None
        if result.plan is None
        else {
            "platform": result.plan.platform,
            "evidence_required": result.plan.evidence_required,
            "steps": [{"name": step.name, "intent": step.intent} for step in result.plan.steps],
        },
    }
    print(json.dumps(payload, indent=args.indent, sort_keys=True, default=str))
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
