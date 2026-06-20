"""Databricks deployment CLI commands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable

from contractforge_databricks.runtime.deploy import (
    deploy_databricks_bundle,
    deploy_databricks_project,
    render_databricks_project_bundle_file,
)


def add_deploy_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    project = subparsers.add_parser("deploy-project", help="Validate/deploy/run a project Databricks Asset Bundle.")
    project.add_argument("project", type=Path)
    project.add_argument("--render-bundle", action="store_true", help="Render databricks.yml from project.yaml before deployment.")
    project.add_argument("--force-render", action="store_true", help="Overwrite the rendered bundle when --render-bundle is used.")
    _add_common_deploy_args(project)

    run_project = subparsers.add_parser("run-project", help="Deploy and run a project Databricks Asset Bundle.")
    run_project.add_argument("project", type=Path)
    run_project.add_argument("--render-bundle", action="store_true", help="Render databricks.yml from project.yaml before deployment.")
    run_project.add_argument("--force-render", action="store_true", help="Overwrite the rendered bundle when --render-bundle is used.")
    _add_common_deploy_args(run_project, include_run=False)

    bundle = subparsers.add_parser("deploy-bundle", help="Validate/deploy/run a Databricks Asset Bundle directory.")
    bundle.add_argument("bundle", type=Path)
    _add_common_deploy_args(bundle)

    render = subparsers.add_parser("render-project-bundle", help="Render databricks.yml from project.yaml scheduling metadata.")
    render.add_argument("project", type=Path)
    render.add_argument("--output", type=Path, default=Path("databricks.yml"))
    render.add_argument("--target", default="dev")
    render.add_argument("--force", action="store_true")
    render.add_argument("--indent", type=int, default=2)


def deploy_command(args: argparse.Namespace) -> int | None:
    handler = _COMMANDS.get(args.command)
    return None if handler is None else handler(args)


def _handle_project(args: argparse.Namespace) -> int:
    return _print(
        deploy_databricks_project(
            args.project,
            profile=args.profile,
            target=args.target,
            run=args.run,
            validate=not args.skip_validate,
            render_bundle=args.render_bundle,
            force_render=args.force_render,
        ),
        args.indent,
    )


def _handle_run_project(args: argparse.Namespace) -> int:
    return _print(
        deploy_databricks_project(
            args.project,
            profile=args.profile,
            target=args.target,
            run=True,
            validate=not args.skip_validate,
            render_bundle=args.render_bundle,
            force_render=args.force_render,
        ),
        args.indent,
    )


def _handle_bundle(args: argparse.Namespace) -> int:
    return _print(
        deploy_databricks_bundle(
            args.bundle,
            profile=args.profile,
            target=args.target,
            run=args.run,
            validate=not args.skip_validate,
        ),
        args.indent,
    )


def _handle_render_project_bundle(args: argparse.Namespace) -> int:
    return _print(
        render_databricks_project_bundle_file(
            args.project,
            args.output,
            target=args.target,
            force=args.force,
        ),
        args.indent,
    )


def _add_common_deploy_args(parser: argparse.ArgumentParser, *, include_run: bool = True) -> None:
    parser.add_argument("--profile")
    parser.add_argument("--target")
    if include_run:
        parser.add_argument("--run", action="store_true", help="Run the deployed bundle job after deployment.")
    parser.add_argument("--skip-validate", action="store_true")
    parser.add_argument("--indent", type=int, default=2)


def _print(payload: object, indent: int) -> int:
    print(json.dumps(payload, indent=indent, sort_keys=True, default=str))
    return 0


_COMMANDS: dict[str, Callable[[argparse.Namespace], int]] = {
    "deploy-project": _handle_project,
    "run-project": _handle_run_project,
    "deploy-bundle": _handle_bundle,
    "render-project-bundle": _handle_render_project_bundle,
}
