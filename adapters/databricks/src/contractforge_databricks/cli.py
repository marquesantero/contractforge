"""CLI entrypoint for Databricks adapter utilities."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from contractforge_databricks.api import render_databricks_contract
from contractforge_databricks.cli_deploy import add_deploy_parser, deploy_command
from contractforge_databricks.cli_governance import add_governance_parser, governance_command
from contractforge_databricks.cli_io import load_contract_input, load_mapping, write_artifacts, write_mapping
from contractforge_databricks.cli_maintenance import add_maintenance_parser, maintenance_command
from contractforge_databricks.cli_stabilization import add_stabilization_parser, handle_stabilization
from contractforge_databricks.cli_standard import add_standard_parser, standard_command
from contractforge_databricks.dashboards import render_control_dashboard_artifacts
from contractforge_databricks.presets import list_presets, preset_details
from contractforge_databricks.templates import (
    contract_template_details,
    contract_template_files,
    get_contract_template,
    list_contract_templates,
    recommend_contract_templates,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="contractforge-databricks")
    sub = parser.add_subparsers(dest="command", required=True)

    presets = sub.add_parser("presets", help="List or inspect Databricks adapter presets")
    presets_sub = presets.add_subparsers(dest="preset_command", required=True)
    presets_list = presets_sub.add_parser("list")
    presets_list.add_argument("--indent", type=int, default=2)
    presets_show = presets_sub.add_parser("show")
    presets_show.add_argument("names", nargs="+")
    presets_show.add_argument("--indent", type=int, default=2)

    templates = sub.add_parser("templates", help="List, show, recommend or write Databricks contract templates")
    templates_sub = templates.add_subparsers(dest="template_command", required=True)
    templates_list = templates_sub.add_parser("list")
    templates_list.add_argument("--indent", type=int, default=2)
    templates_show = templates_sub.add_parser("show")
    templates_show.add_argument("name")
    templates_show.add_argument("--metadata-only", action="store_true")
    templates_show.add_argument("--indent", type=int, default=2)
    templates_write = templates_sub.add_parser("write")
    templates_write.add_argument("name")
    templates_write.add_argument("--output", required=True, type=Path)
    templates_write.add_argument("--force", action="store_true")
    templates_write.add_argument("--indent", type=int, default=2)
    templates_wizard = templates_sub.add_parser("wizard")
    templates_wizard.add_argument("--layer")
    templates_wizard.add_argument("--source")
    templates_wizard.add_argument("--mode")
    templates_wizard.add_argument("--pattern")
    templates_wizard.add_argument("--limit", type=int, default=5)
    templates_wizard.add_argument("--name")
    templates_wizard.add_argument("--output", type=Path)
    templates_wizard.add_argument("--force", action="store_true")
    templates_wizard.add_argument("--indent", type=int, default=2)

    render = sub.add_parser("render", help="Render Databricks review artifacts for a contract JSON/YAML file")
    render.add_argument("contract", type=Path)
    render.add_argument("--environment", type=Path)
    render.add_argument("--output-dir", type=Path)
    render.add_argument("--indent", type=int, default=2)

    dashboard = sub.add_parser("dashboard", help="Render Databricks control-table dashboard artifacts")
    dashboard.add_argument("--catalog", default="main")
    dashboard.add_argument("--schema", default="ops")
    dashboard.add_argument("--lookback-days", type=int, default=7)
    dashboard.add_argument("--output-dir", type=Path)
    dashboard.add_argument("--indent", type=int, default=2)

    add_standard_parser(sub)
    add_governance_parser(sub)
    add_maintenance_parser(sub)
    add_deploy_parser(sub)
    add_stabilization_parser(sub)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return _dispatch(args)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def _dispatch(args: argparse.Namespace) -> int:
    if args.command == "presets":
        return _presets(args)
    if args.command == "templates":
        return _templates(args)
    if args.command == "render":
        return _render_contract(args)
    if args.command == "dashboard":
        return _dashboard(args)
    standard_result = standard_command(args)
    if standard_result is not None:
        return standard_result
    stabilization_result = handle_stabilization(args)
    if stabilization_result is not None:
        return stabilization_result
    governance_result = governance_command(args)
    if governance_result is not None:
        return governance_result
    if args.command == "maintenance":
        return maintenance_command(args)
    deploy_result = deploy_command(args)
    if deploy_result is not None:
        return deploy_result
    raise ValueError(f"unsupported command: {args.command}")


def _presets(args: argparse.Namespace) -> int:
    if args.preset_command == "list":
        return _print([preset_details(name) for name in list_presets()], args.indent)
    if args.preset_command == "show":
        return _print([preset_details(name) for name in args.names], args.indent)
    raise ValueError(f"unsupported presets command: {args.preset_command}")


def _templates(args: argparse.Namespace) -> int:
    if args.template_command == "list":
        return _print([contract_template_details(name) for name in list_contract_templates()], args.indent)
    if args.template_command == "show":
        payload = contract_template_details(args.name) if args.metadata_only else get_contract_template(args.name)
        return _print(payload, args.indent)
    if args.template_command == "write":
        written = _write_template_files(args.name, args.output, force=args.force)
        return _print({"status": "SUCCESS", "template": args.name, "written": written}, args.indent)
    if args.template_command == "wizard":
        recommendations = recommend_contract_templates(
            layer=args.layer,
            source=args.source,
            mode=args.mode,
            pattern=args.pattern,
            limit=args.limit,
        )
        result: dict[str, Any] = {
            "status": "SUCCESS",
            "criteria": {
                "layer": args.layer,
                "source": args.source,
                "mode": args.mode,
                "pattern": args.pattern,
            },
            "recommendations": recommendations,
        }
        if args.output:
            if not recommendations:
                raise ValueError("no compatible template found for the provided criteria")
            selected = args.name or str(recommendations[0]["name"])
            result["selected_template"] = selected
            result["written"] = _write_template_files(selected, args.output, force=args.force)
        return _print(result, args.indent)
    raise ValueError(f"unsupported templates command: {args.template_command}")


def _render_contract(args: argparse.Namespace) -> int:
    contract, bundle_environment = load_contract_input(args.contract)
    environment = load_mapping(args.environment) if args.environment else bundle_environment
    artifacts = render_databricks_contract(contract, environment=environment).artifacts
    if args.output_dir:
        written = write_artifacts(args.output_dir, artifacts)
        return _print({"status": "SUCCESS", "written": written}, args.indent)
    return _print(artifacts, args.indent)


def _dashboard(args: argparse.Namespace) -> int:
    artifacts = render_control_dashboard_artifacts(
        catalog=args.catalog,
        schema=args.schema,
        lookback_days=args.lookback_days,
    )
    if args.output_dir:
        written = write_artifacts(args.output_dir, artifacts)
        return _print({"status": "SUCCESS", "written": written}, args.indent)
    return _print(artifacts, args.indent)


def _write_template_files(name: str, output: Path, *, force: bool) -> list[str]:
    files = contract_template_files(name)
    written = []
    for kind, payload in files.items():
        path = output.with_suffix(f".{kind}.yaml")
        write_mapping(path, payload, force=force)
        written.append(str(path))
    return written


def _print(payload: object, indent: int) -> int:
    print(json.dumps(payload, indent=indent, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
