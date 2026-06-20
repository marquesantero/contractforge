"""Core ContractForge CLI for platform-neutral contract utilities."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from contractforge_core.cli_connectors import handle_connector_command
from contractforge_core.cli_contracts import handle_contract_command
from contractforge_core.config import PUBLIC_WRITE_MODES, VALID_SCHEMA_POLICIES


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="contractforge")
    sub = parser.add_subparsers(dest="command", required=True)
    _add_contract_parsers(sub)
    _add_connector_parser(sub)
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
    contract_result = handle_contract_command(args)
    if contract_result is not None:
        return contract_result
    connector_result = handle_connector_command(args)
    if connector_result is not None:
        return connector_result
    raise ValueError(f"unsupported command: {args.command}")


def _add_contract_parsers(subparsers: Any) -> None:
    validate = subparsers.add_parser("validate", help="Validate contract files without executing a platform")
    validate.add_argument("paths", nargs="+", type=Path)
    validate.add_argument("--indent", type=int, default=2)
    validate_bundle = subparsers.add_parser("validate-bundle", help="Validate split contract bundles")
    validate_bundle.add_argument("paths", nargs="+", type=Path)
    validate_bundle.add_argument("--indent", type=int, default=2)
    validate_project = subparsers.add_parser("validate-project", help="Discover and validate contracts recursively")
    validate_project.add_argument("paths", nargs="+", type=Path)
    validate_project.add_argument("--indent", type=int, default=2)
    schema = subparsers.add_parser("schema", help="Print generated core contract JSON Schemas")
    schema.add_argument("--indent", type=int, default=2)
    init = subparsers.add_parser("init", help="Generate a starter split ContractForge contract")
    init.add_argument("--output", required=True, type=Path)
    init.add_argument("--source", required=True)
    init.add_argument("--target-table", required=True)
    init.add_argument("--catalog", default="main")
    init.add_argument("--layer", default="bronze")
    init.add_argument("--target-schema")
    init.add_argument("--adapter", default="generic")
    init.add_argument("--mode", default="append", choices=sorted(PUBLIC_WRITE_MODES))
    init.add_argument("--schema-policy", default="additive_only", choices=sorted(VALID_SCHEMA_POLICIES))
    init.add_argument("--merge-keys")
    init.add_argument("--hash-keys")
    init.add_argument("--watermark-columns")
    init.add_argument("--description")
    init.add_argument("--domain")
    init.add_argument("--owner")
    init.add_argument("--technical-owner")
    init.add_argument("--support-group")
    init.add_argument("--criticality", default="medium")
    init.add_argument("--expected-frequency", default="daily")
    init.add_argument("--freshness-sla-minutes", type=int, default=1440)
    init.add_argument("--runbook-url")
    init.add_argument("--access-principal")
    init.add_argument("--force", action="store_true")
    init.add_argument("--indent", type=int, default=2)


def _add_connector_parser(subparsers: Any) -> None:
    parser = subparsers.add_parser("connectors", help="List or inspect source connector portability")
    sub = parser.add_subparsers(dest="connector_command", required=True)
    list_parser = sub.add_parser("list", help="List known portable source types")
    list_parser.add_argument("--indent", type=int, default=2)
    show = sub.add_parser("show", help="Show connector details")
    show.add_argument("names", nargs="+")
    show.add_argument("--indent", type=int, default=2)
    doctor = sub.add_parser("doctor", help="Diagnose connector portability without opening external connections")
    doctor.add_argument("names", nargs="*")
    doctor.add_argument("--indent", type=int, default=2)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
