"""Publish command handlers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def add_publish_parsers(subcommands: Any) -> None:
    render_parser = subcommands.add_parser("render", help="Render Snowflake publish artifacts.")
    render_parser.add_argument("contract", type=Path)
    render_parser.add_argument("--environment", type=Path)
    render_parser.add_argument("--output-dir", type=Path)

    publish_parser = subcommands.add_parser("publish-bundle", help="Build Snowflake publish artifacts.")
    publish_parser.add_argument("contract", type=Path)
    publish_parser.add_argument("--output-dir", type=Path, required=True)

    stage_parser = subcommands.add_parser("publish", help="Publish Snowflake artifacts to a stage.")
    stage_parser.add_argument("contract", type=Path)
    stage_parser.add_argument("--stage")
    stage_parser.add_argument("--prefix")
    stage_parser.add_argument("--connect-options", type=Path)


def handle_publish_bundle(args: argparse.Namespace) -> int:
    from contractforge_snowflake.api import build_snowflake_publish_bundle
    from contractforge_snowflake.cli._helpers import _load_yaml, _write_artifacts

    rendered = build_snowflake_publish_bundle(_load_yaml(args.contract))
    _write_artifacts(args.output_dir, rendered.artifacts)
    return 0


def handle_render(args: argparse.Namespace) -> int:
    from contractforge_snowflake.api import build_snowflake_publish_bundle
    from contractforge_snowflake.cli._helpers import _load_optional_yaml, _load_yaml, _write_artifacts

    rendered = build_snowflake_publish_bundle(_load_yaml(args.contract), environment=_load_optional_yaml(args.environment))
    if args.output_dir:
        _write_artifacts(args.output_dir, rendered.artifacts)
        print(json.dumps({"status": "SUCCESS", "output_dir": str(args.output_dir), "artifacts": sorted(rendered.artifacts)}, indent=2))
        return 0
    print(json.dumps(rendered.artifacts, indent=2, sort_keys=True))
    return 0


def handle_publish(args: argparse.Namespace) -> int:
    from contractforge_snowflake.cli._helpers import _load_optional_yaml, _load_yaml
    from contractforge_snowflake.runtime import publish_snowflake_contract

    result = publish_snowflake_contract(
        _load_yaml(args.contract),
        stage=args.stage,
        prefix=args.prefix,
        connect_options=_load_optional_yaml(args.connect_options),
    )
    print(
        json.dumps(
            {
                "stage": result.stage,
                "prefix": result.prefix,
                "execution_model": result.execution_model,
                "manifest_uri": result.manifest_uri,
                "artifacts": [artifact.uri for artifact in result.artifacts],
            },
            indent=2,
        )
    )
    return 0
