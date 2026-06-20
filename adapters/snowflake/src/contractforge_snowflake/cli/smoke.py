"""Smoke command handlers."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any


def _shared_smoke_args(parser: Any, *, table_prefix: str) -> None:
    parser.add_argument("--connection")
    parser.add_argument("--connect-options", type=Path)
    parser.add_argument("--database", default="CONTRACTFORGE_TEST_DB")
    parser.add_argument("--source-schema", default="PUBLIC")
    parser.add_argument("--target-schema", default="PUBLIC")
    parser.add_argument("--evidence-schema", default="PUBLIC")
    parser.add_argument("--schema")
    parser.add_argument("--table-prefix", default=table_prefix)
    parser.add_argument("--warehouse", default="COMPUTE_WH")
    parser.add_argument("--role", default="CONTRACTFORGE_INGEST_ROLE")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--execute-cleanup", action="store_true")


def _extended_smoke_args(parser: Any, *, table_prefix: str) -> None:
    _shared_smoke_args(parser, table_prefix=table_prefix)
    parser.add_argument("--stage-name")
    parser.add_argument("--prefix")


def add_smoke_parsers(subcommands: Any) -> None:
    smoke = subcommands.add_parser("smoke", help="Run the minimal Snowflake adapter smoke test.")
    _shared_smoke_args(smoke, table_prefix="CF_SMOKE")

    minimal = subcommands.add_parser("smoke-minimal", help="Run the minimal Snowflake adapter smoke test.")
    _shared_smoke_args(minimal, table_prefix="CF_SMOKE")

    failure = subcommands.add_parser("smoke-failure-paths", help="Run Snowflake failure-path smoke tests.")
    _shared_smoke_args(failure, table_prefix="CF_SMOKE")

    access = subcommands.add_parser("smoke-access-policy", help="Run Snowflake access policy smoke tests.")
    _shared_smoke_args(access, table_prefix="CF_SMOKE_ACCESS")

    stage = subcommands.add_parser("smoke-stage-publish", help="Publish and run Snowflake artifacts from a stage.")
    _extended_smoke_args(stage, table_prefix="CF_SMOKE_STAGE")

    procedure = subcommands.add_parser("smoke-procedure", help="Deploy and call the Snowflake runtime procedure.")
    _extended_smoke_args(procedure, table_prefix="CF_SMOKE_PROC")
    procedure.add_argument("--procedure-name")
    procedure.add_argument("--core-wheel", type=Path)
    procedure.add_argument("--adapter-wheel", type=Path)

    task = subcommands.add_parser("smoke-task-graph", help="Deploy and execute a Snowflake task graph smoke.")
    _extended_smoke_args(task, table_prefix="CF_SMOKE_TASK")
    task.add_argument("--procedure-name")
    task.add_argument("--core-wheel", type=Path)
    task.add_argument("--adapter-wheel", type=Path)


def handle_smoke_minimal(args: argparse.Namespace) -> int:
    from contractforge_snowflake.cli import _connect
    from contractforge_snowflake.cli._helpers import _load_optional_yaml, _smoke_minimal_argv
    from contractforge_snowflake.smoke.minimal import main as smoke_minimal_main

    return smoke_minimal_main(
        _smoke_minimal_argv(args),
        connect=_connect,
        load_connect_options=_load_optional_yaml,
    )


def handle_smoke_failure_paths(args: argparse.Namespace) -> int:
    from contractforge_snowflake.cli import _connect
    from contractforge_snowflake.cli._helpers import _load_optional_yaml, _smoke_minimal_argv
    from contractforge_snowflake.smoke.failure_paths import main as smoke_failure_paths_main

    return smoke_failure_paths_main(
        _smoke_minimal_argv(args),
        connect=_connect,
        load_connect_options=_load_optional_yaml,
    )


def handle_smoke_access_policy(args: argparse.Namespace) -> int:
    from contractforge_snowflake.cli import _connect
    from contractforge_snowflake.cli._helpers import _load_optional_yaml, _smoke_minimal_argv
    from contractforge_snowflake.smoke.access_policy import main as smoke_access_policy_main

    return smoke_access_policy_main(
        _smoke_minimal_argv(args),
        connect=_connect,
        load_connect_options=_load_optional_yaml,
    )


def handle_smoke_stage_publish(args: argparse.Namespace) -> int:
    from contractforge_snowflake.cli import _connect
    from contractforge_snowflake.cli._helpers import _load_optional_yaml, _smoke_stage_publish_argv
    from contractforge_snowflake.smoke.stage_publish import main as smoke_stage_publish_main

    return smoke_stage_publish_main(
        _smoke_stage_publish_argv(args),
        connect=_connect,
        load_connect_options=_load_optional_yaml,
    )


def handle_smoke_procedure(args: argparse.Namespace) -> int:
    from contractforge_snowflake.cli import _connect
    from contractforge_snowflake.cli._helpers import _load_optional_yaml, _smoke_procedure_argv
    from contractforge_snowflake.smoke.procedure import main as smoke_procedure_main

    return smoke_procedure_main(
        _smoke_procedure_argv(args),
        connect=_connect,
        load_connect_options=_load_optional_yaml,
    )


def handle_smoke_task_graph(args: argparse.Namespace) -> int:
    from contractforge_snowflake.cli import _connect
    from contractforge_snowflake.cli._helpers import _load_optional_yaml, _smoke_procedure_argv
    from contractforge_snowflake.smoke.task_graph import main as smoke_task_graph_main

    return smoke_task_graph_main(
        _smoke_procedure_argv(args),
        connect=_connect,
        load_connect_options=_load_optional_yaml,
    )
