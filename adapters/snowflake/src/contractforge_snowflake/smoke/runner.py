"""Runner for the minimal Snowflake adapter smoke test."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from contractforge_core.security.redaction import redact_text
from contractforge_snowflake.runtime import run_snowflake_contract
from contractforge_snowflake.session_ops import execute, scalar_int
from contractforge_snowflake.smoke.models import (
    SnowflakeSmokeConfig,
    bootstrap_skips,
    cleanup_commands,
    control_count_queries,
    environment_payload,
    failure_contracts,
    setup_commands,
    smoke_contracts,
    target_count_queries,
)


def dry_run_payload(config: SnowflakeSmokeConfig, *, execute: bool = False, execute_cleanup: bool = False) -> dict[str, Any]:
    return {
        "status": "DRY_RUN",
        "execute": execute,
        "execute_cleanup": execute_cleanup,
        "config": config.summary_config(),
        "environment": environment_payload(config),
        "contracts": smoke_contracts(config),
        "setup_commands": list(setup_commands(config, execute_cleanup=execute_cleanup)),
        "bootstrap_skips": list(bootstrap_skips(config)),
    }


def dry_run_failure_payload(
    config: SnowflakeSmokeConfig,
    *,
    execute: bool = False,
    execute_cleanup: bool = False,
) -> dict[str, Any]:
    return {
        "status": "DRY_RUN",
        "execute": execute,
        "execute_cleanup": execute_cleanup,
        "config": config.summary_config(),
        "environment": environment_payload(config),
        "contracts": failure_contracts(config),
        "setup_commands": list(setup_commands(config, execute_cleanup=execute_cleanup)),
        "bootstrap_skips": list(bootstrap_skips(config)),
    }


def execute_smoke(
    config: SnowflakeSmokeConfig,
    *,
    session: Any,
    execute_cleanup: bool,
) -> dict[str, Any]:
    if not execute_cleanup:
        raise ValueError("Snowflake minimal smoke live execution requires --execute-cleanup")

    commands: list[str] = []
    for command in setup_commands(config, execute_cleanup=execute_cleanup):
        execute(session, command)
        commands.append(command)

    try:
        run_results = _run_contracts(config, session=session)
        summary = {
            "status": "SUCCESS" if all(result["ok"] for result in run_results.values()) else "FAILED",
            "execute": True,
            "execute_cleanup": execute_cleanup,
            "config": config.summary_config(),
            "runs": run_results,
            "target_counts": _counts(session, target_count_queries(config)),
            "control_counts": _counts(session, control_count_queries(config)),
            "setup_command_count": len(commands),
            "bootstrap_skips": list(bootstrap_skips(config)),
        }
        _write_summary(config, summary)
        return summary
    finally:
        for command in cleanup_commands(config):
            execute(session, command)


def execute_failure_smoke(
    config: SnowflakeSmokeConfig,
    *,
    session: Any,
    execute_cleanup: bool,
) -> dict[str, Any]:
    if not execute_cleanup:
        raise ValueError("Snowflake failure-path smoke live execution requires --execute-cleanup")

    commands: list[str] = []
    for command in setup_commands(config, execute_cleanup=execute_cleanup):
        execute(session, command)
        commands.append(command)

    try:
        run_results = _run_expected_failure_contracts(config, session=session)
        summary = {
            "status": "SUCCESS" if all(result["ok"] for result in run_results.values()) else "FAILED",
            "execute": True,
            "execute_cleanup": execute_cleanup,
            "config": config.summary_config(),
            "runs": run_results,
            "control_counts": _counts(session, control_count_queries(config)),
            "setup_command_count": len(commands),
            "bootstrap_skips": list(bootstrap_skips(config)),
        }
        _write_summary(config, summary)
        return summary
    finally:
        for command in cleanup_commands(config):
            execute(session, command)


def _run_contracts(config: SnowflakeSmokeConfig, *, session: Any) -> dict[str, Any]:
    contracts = smoke_contracts(config)
    environment = environment_payload(config)
    base_dir: Path | None = config.output_dir
    if base_dir is not None:
        base_dir.mkdir(parents=True, exist_ok=True)
        return _run_contracts_from_dir(base_dir, contracts, environment, session=session)
    with tempfile.TemporaryDirectory(prefix="contractforge-snowflake-smoke-") as temp:
        return _run_contracts_from_dir(Path(temp), contracts, environment, session=session)


def _run_expected_failure_contracts(config: SnowflakeSmokeConfig, *, session: Any) -> dict[str, Any]:
    contracts = failure_contracts(config)
    environment = environment_payload(config)
    base_dir: Path | None = config.output_dir
    if base_dir is not None:
        base_dir.mkdir(parents=True, exist_ok=True)
        return _run_expected_failure_contracts_from_dir(base_dir, contracts, environment, session=session)
    with tempfile.TemporaryDirectory(prefix="contractforge-snowflake-failure-smoke-") as temp:
        return _run_expected_failure_contracts_from_dir(Path(temp), contracts, environment, session=session)


def _run_contracts_from_dir(
    base_dir: Path,
    contracts: dict[str, dict[str, Any]],
    environment: dict[str, Any],
    *,
    session: Any,
) -> dict[str, Any]:
    contract_dir = base_dir / "contracts"
    contract_dir.mkdir(parents=True, exist_ok=True)
    environment_path = base_dir / "environment.json"
    environment_path.write_text(json.dumps(environment, indent=2, sort_keys=True), encoding="utf-8")

    results: dict[str, Any] = {}
    for name, contract in contracts.items():
        contract_path = contract_dir / f"{name}.contract.json"
        contract_path.write_text(json.dumps(contract, indent=2, sort_keys=True), encoding="utf-8")
        try:
            result = run_snowflake_contract(
                contract_uri=str(contract_path),
                environment_uri=str(environment_path),
                session=session,
            )
            results[name] = {"ok": True, "result": result}
        except Exception as exc:  # pragma: no cover - live diagnostic path
            results[name] = {"ok": False, "error": redact_text(str(exc)), "notes": list(getattr(exc, "__notes__", ()))}
    return results


def _run_expected_failure_contracts_from_dir(
    base_dir: Path,
    contracts: dict[str, dict[str, Any]],
    environment: dict[str, Any],
    *,
    session: Any,
) -> dict[str, Any]:
    contract_dir = base_dir / "contracts"
    contract_dir.mkdir(parents=True, exist_ok=True)
    environment_path = base_dir / "environment.json"
    environment_path.write_text(json.dumps(environment, indent=2, sort_keys=True), encoding="utf-8")

    results: dict[str, Any] = {}
    for name, contract in contracts.items():
        contract_path = contract_dir / f"{name}.contract.json"
        contract_path.write_text(json.dumps(contract, indent=2, sort_keys=True), encoding="utf-8")
        try:
            result = run_snowflake_contract(
                contract_uri=str(contract_path),
                environment_uri=str(environment_path),
                session=session,
            )
            results[name] = {"ok": False, "unexpected_success": result}
        except Exception as exc:
            results[name] = {
                "ok": True,
                "error": redact_text(str(exc)),
                "notes": list(getattr(exc, "__notes__", ())),
            }
    return results


def _counts(session: Any, queries: dict[str, str]) -> dict[str, int | str]:
    return {name: _count(session, query) for name, query in queries.items()}


def _count(session: Any, query: str) -> int | str:
    try:
        return scalar_int(session, query, key="COUNT")
    except Exception as exc:  # pragma: no cover - live diagnostic path
        return repr(exc)


def _write_summary(config: SnowflakeSmokeConfig, summary: dict[str, Any]) -> None:
    if config.output_dir is None:
        return
    config.output_dir.mkdir(parents=True, exist_ok=True)
    (config.output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
