"""Snowflake adapter CLI command handlers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from contractforge_snowflake.connection_options import validate_connect_options
from contractforge_snowflake.runtime import SnowflakeConnectorSession


def _connect(options: dict[str, Any] | None) -> Any:
    connect_options = validate_connect_options(options)
    try:
        import snowflake.connector
    except ImportError as exc:  # pragma: no cover - runtime extra path
        raise RuntimeError(
            "Snowflake CLI execution requires the runtime extra: pip install contractforge-snowflake[runtime]"
        ) from exc
    return snowflake.connector.connect(**connect_options)


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected mapping YAML: {path}")
    return payload


def _load_optional_yaml(path: Path | None) -> dict[str, Any] | None:
    return _load_yaml(path) if path else None


def _write_artifacts(output_dir: Path, artifacts: dict[str, str]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, body in artifacts.items():
        target = output_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")


def _run_contract(args: Any) -> dict[str, Any]:
    from contractforge_snowflake.cli import _connect as _connect_fn, run_snowflake_contract as run_contract_fn

    if args.dry_run:
        return run_contract_fn(
            contract_uri=args.contract_uri,
            environment_uri=args.environment_uri,
            dry_run=True,
        )
    connection = _connect_fn(_load_optional_yaml(args.connect_options))
    try:
        return run_contract_fn(
            contract_uri=args.contract_uri,
            environment_uri=args.environment_uri,
            session=SnowflakeConnectorSession(connection),
        )
    finally:
        if hasattr(connection, "close"):
            connection.close()


def _project_run_payload(result: Any, *, summary_only: bool) -> dict[str, Any]:
    payload = dict(result.__dict__)
    if summary_only:
        payload.pop("commands", None)
        wait = payload.get("wait")
        if isinstance(wait, dict):
            wait.pop("query", None)
    return payload


def _smoke_minimal_argv(args: Any) -> list[str]:
    argv: list[str] = []
    for name in (
        "connection",
        "connect_options",
        "database",
        "source_schema",
        "target_schema",
        "evidence_schema",
        "schema",
        "table_prefix",
        "warehouse",
        "role",
        "output_dir",
    ):
        value = getattr(args, name, None)
        if value is not None:
            argv.extend((f"--{name.replace('_', '-')}", str(value)))
    if args.execute:
        argv.append("--execute")
    if args.execute_cleanup:
        argv.append("--execute-cleanup")
    return argv


def _smoke_stage_publish_argv(args: Any) -> list[str]:
    argv = _smoke_minimal_argv(args)
    for name in ("stage_name", "prefix"):
        value = getattr(args, name)
        if value is not None:
            argv.extend((f"--{name.replace('_', '-')}", str(value)))
    return argv


def _smoke_procedure_argv(args: Any) -> list[str]:
    argv = _smoke_stage_publish_argv(args)
    for name in ("procedure_name", "core_wheel", "adapter_wheel"):
        value = getattr(args, name, None)
        if value is not None:
            argv.extend((f"--{name.replace('_', '-')}", str(value)))
    return argv
