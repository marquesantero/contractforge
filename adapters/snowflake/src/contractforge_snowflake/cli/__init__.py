"""Snowflake adapter CLI."""

from __future__ import annotations

import argparse
import json

from contractforge_snowflake.cli._helpers import _connect, _load_optional_yaml  # noqa: F401 - re-exported for test mocking
from contractforge_snowflake.runtime import run_snowflake_contract  # noqa: F401 - re-exported for test mocking
from contractforge_snowflake.cli.cost import add_cost_parser, handle_cost
from contractforge_snowflake.cli.dashboard import add_dashboard_parser, handle_dashboard
from contractforge_snowflake.cli.lineage import add_lineage_parser, handle_lineage
from contractforge_snowflake.cli.maintenance import add_maintenance_parser, handle_maintenance
from contractforge_snowflake.cli.plan import add_plan_parser, handle_plan
from contractforge_snowflake.cli.project import add_project_parsers, handle_cleanup_plan, handle_deploy_project, handle_run_project
from contractforge_snowflake.cli.publish import add_publish_parsers, handle_publish, handle_publish_bundle, handle_render
from contractforge_snowflake.cli.run import add_run_parser, handle_run
from contractforge_snowflake.cli.smoke import (
    add_smoke_parsers,
    handle_smoke_access_policy,
    handle_smoke_failure_paths,
    handle_smoke_minimal,
    handle_smoke_procedure,
    handle_smoke_stage_publish,
    handle_smoke_task_graph,
)
from contractforge_snowflake.cli.stabilization import add_stabilization_parser, handle_stabilization
from contractforge_snowflake.sources.registry import _SOURCE_RENDERERS
from contractforge_snowflake.sources.review import REVIEW_REQUIRED_SOURCE_TYPES, UNSUPPORTED_SOURCE_TYPES


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="contractforge-snowflake")
    subcommands = parser.add_subparsers(dest="command", required=True)

    add_plan_parser(subcommands)
    add_publish_parsers(subcommands)
    add_run_parser(subcommands)
    add_cost_parser(subcommands)
    add_lineage_parser(subcommands)
    add_dashboard_parser(subcommands)
    add_maintenance_parser(subcommands)
    add_project_parsers(subcommands)
    add_smoke_parsers(subcommands)
    subcommands.add_parser("sources", help="Print Snowflake source support metadata.")
    add_stabilization_parser(subcommands)

    args = parser.parse_args(argv)

    if args.command == "plan":
        return handle_plan(args)
    if args.command == "render":
        return handle_render(args)
    if args.command == "publish-bundle":
        return handle_publish_bundle(args)
    if args.command == "publish":
        return handle_publish(args)
    if args.command == "run":
        return handle_run(args)
    if args.command in {"cost-report", "reconcile-cost"}:
        return handle_cost(args)
    if args.command == "reconcile-lineage":
        return handle_lineage(args)
    if args.command == "dashboard":
        return handle_dashboard(args)
    if args.command == "maintenance":
        return handle_maintenance(args)
    if args.command == "deploy-project":
        return handle_deploy_project(args)
    if args.command == "run-project":
        return handle_run_project(args)
    if args.command == "cleanup-plan":
        return handle_cleanup_plan(args)
    if args.command in {"smoke", "smoke-minimal"}:
        return handle_smoke_minimal(args)
    if args.command == "sources":
        return _handle_sources()
    if args.command == "smoke-failure-paths":
        return handle_smoke_failure_paths(args)
    if args.command == "smoke-access-policy":
        return handle_smoke_access_policy(args)
    if args.command == "smoke-stage-publish":
        return handle_smoke_stage_publish(args)
    if args.command == "smoke-procedure":
        return handle_smoke_procedure(args)
    if args.command == "smoke-task-graph":
        return handle_smoke_task_graph(args)
    result = handle_stabilization(args)
    if result is not None:
        return result
    return 1


def _handle_sources() -> int:
    supported = [
        {"source_type": source_type, "status": "SUPPORTED", "renderable": True}
        for source_type in sorted(_SOURCE_RENDERERS)
    ]
    review_required = [
        {"source_type": source_type, "status": "REVIEW_REQUIRED", "renderable": False}
        for source_type in sorted(REVIEW_REQUIRED_SOURCE_TYPES)
    ]
    unsupported = [
        {"source_type": source_type, "status": "UNSUPPORTED", "renderable": False}
        for source_type in sorted(UNSUPPORTED_SOURCE_TYPES)
    ]
    print(json.dumps([*supported, *review_required, *unsupported], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
