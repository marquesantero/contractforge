"""Snowflake access policy smoke test."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

from contractforge_snowflake.naming import quote_identifier
from contractforge_snowflake.runtime import SnowflakeConnectorSession, run_snowflake_contract
from contractforge_snowflake.session_ops import collect_rows, execute, scalar_int
from contractforge_snowflake.smoke.connection import require_smoke_connection, smoke_connect_options
from contractforge_snowflake.smoke.models import SnowflakeSmokeConfig, environment_payload


def main(
    argv: list[str] | None = None,
    *,
    connect: Callable[[dict[str, Any] | None], Any] | None = None,
    load_connect_options: Callable[[Path | None], dict[str, Any] | None] | None = None,
) -> int:
    parser = argparse.ArgumentParser(prog="contractforge-snowflake smoke-access-policy")
    parser.add_argument("--connection", help="Snowflake CLI connection name for operator reference.")
    parser.add_argument("--connect-options", type=Path, help="YAML options passed to snowflake.connector.connect.")
    parser.add_argument("--database", default="CONTRACTFORGE_TEST_DB")
    parser.add_argument("--source-schema", default="PUBLIC")
    parser.add_argument("--target-schema", default="PUBLIC")
    parser.add_argument("--evidence-schema", default="PUBLIC")
    parser.add_argument("--schema", dest="all_schema", help="Use one schema for source, target, and evidence.")
    parser.add_argument("--table-prefix", default="CF_SMOKE_ACCESS")
    parser.add_argument("--warehouse", default="COMPUTE_WH")
    parser.add_argument("--role", default="CONTRACTFORGE_INGEST_ROLE")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--execute-cleanup", action="store_true")
    args = parser.parse_args(argv)

    schema = args.all_schema
    config = SnowflakeSmokeConfig(
        database=args.database,
        source_schema=schema or args.source_schema,
        target_schema=schema or args.target_schema,
        evidence_schema=schema or args.evidence_schema,
        table_prefix=args.table_prefix,
        warehouse=args.warehouse,
        role=args.role,
        connection=args.connection,
        output_dir=args.output_dir,
    )
    if not args.execute:
        print(json.dumps(dry_run_payload(config, execute=False, execute_cleanup=args.execute_cleanup), indent=2, sort_keys=True, default=str))
        return 0
    require_smoke_connection(
        connection=args.connection,
        connect_options=args.connect_options,
        command_name="Snowflake access policy smoke",
    )
    if not args.execute_cleanup:
        raise ValueError("Snowflake access policy smoke live execution requires --execute-cleanup")
    if connect is None or load_connect_options is None:
        raise ValueError("Snowflake access policy smoke connector hooks were not provided")

    connection = connect(
        smoke_connect_options(
            connection=args.connection,
            connect_options=args.connect_options,
            load_connect_options=load_connect_options,
        )
    )
    try:
        payload = execute_access_policy_smoke(
            config,
            session=SnowflakeConnectorSession(connection),
            execute_cleanup=args.execute_cleanup,
        )
    finally:
        if hasattr(connection, "close"):
            connection.close()
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0 if payload["status"] == "SUCCESS" else 1


def dry_run_payload(config: SnowflakeSmokeConfig, *, execute: bool = False, execute_cleanup: bool = False) -> dict[str, Any]:
    return {
        "status": "DRY_RUN",
        "execute": execute,
        "execute_cleanup": execute_cleanup,
        "config": config.summary_config(),
        "environment": environment_payload(config),
        "contracts": access_policy_contracts(config),
        "setup_commands": list(setup_commands(config, execute_cleanup=execute_cleanup)),
        "validation_queries": validation_queries(config),
    }


def execute_access_policy_smoke(
    config: SnowflakeSmokeConfig,
    *,
    session: Any,
    execute_cleanup: bool,
) -> dict[str, Any]:
    if not execute_cleanup:
        raise ValueError("Snowflake access policy smoke live execution requires --execute-cleanup")

    setup = setup_commands(config, execute_cleanup=execute_cleanup)
    for command in setup:
        execute(session, command)
    try:
        runs = _run_contracts(config, session=session)
        validations = _validations(config, session=session)
        control_counts = {
            "ctrl_ingestion_runs": _control_count(config, session, "ctrl_ingestion_runs"),
            "ctrl_ingestion_access": _control_count(config, session, "ctrl_ingestion_access"),
        }
        status = "SUCCESS" if all(result["ok"] for result in runs.values()) and validations["status"] == "PASS" else "FAILED"
        payload = {
            "status": status,
            "execute": True,
            "execute_cleanup": execute_cleanup,
            "config": config.summary_config(),
            "runs": runs,
            "validations": validations,
            "control_counts": control_counts,
            "setup_command_count": len(setup),
            "cleanup_commands": list(cleanup_commands(config)),
        }
        _write_summary(config, payload)
        return payload
    finally:
        for command in cleanup_commands(config):
            execute(session, command)


def access_policy_contracts(config: SnowflakeSmokeConfig) -> dict[str, dict[str, Any]]:
    source = f"{config.source_namespace}.{config.source_table('ACCESS_SOURCE')}"
    target = config.target_namespace
    return {
        "row_access": {
            "source": {"type": "table", "table": source},
            "target": {**target, "table": config.target_table("ROW_ACCESS_TARGET")},
            "layer": "silver",
            "mode": "scd0_overwrite",
            "access": {
                "grants": [{"principal": config.role, "privileges": ["select"]}],
                "row_filters": [
                    {
                        "name": "region_filter",
                        "function": policy_name(config, "REGION_RAP"),
                        "columns": ["REGION"],
                        "applies_to": {"principals": [config.role]},
                    }
                ],
            },
        },
        "masking": {
            "source": {"type": "table", "table": source},
            "target": {**target, "table": config.target_table("MASKING_TARGET")},
            "layer": "silver",
            "mode": "scd0_overwrite",
            "access": {
                "grants": [{"principal": config.role, "privileges": ["select"]}],
                "column_masks": [
                    {
                        "column": "EMAIL",
                        "function": policy_name(config, "EMAIL_MASK"),
                        "using_columns": ["REGION"],
                        "applies_to": {"principals": [config.role]},
                    }
                ],
            },
        },
    }


def setup_commands(config: SnowflakeSmokeConfig, *, execute_cleanup: bool = False) -> tuple[str, ...]:
    commands: list[str] = []
    if execute_cleanup:
        commands.extend(cleanup_commands(config))
    if config.source_schema.upper() != "PUBLIC":
        commands.append(f"CREATE SCHEMA IF NOT EXISTS {schema_name(config, config.source_schema)}")
    if config.target_schema.upper() != "PUBLIC":
        commands.append(f"CREATE SCHEMA IF NOT EXISTS {schema_name(config, config.target_schema)}")
    if config.evidence_schema.upper() != "PUBLIC":
        commands.append(f"CREATE SCHEMA IF NOT EXISTS {schema_name(config, config.evidence_schema)}")
    commands.extend(
        (
            f"""
CREATE OR REPLACE TABLE {config.qualified_source("ACCESS_SOURCE")} (
  CUSTOMER_ID NUMBER,
  REGION VARCHAR,
  EMAIL VARCHAR
)""".strip(),
            f"""
INSERT INTO {config.qualified_source("ACCESS_SOURCE")} (CUSTOMER_ID, REGION, EMAIL)
SELECT * FROM VALUES
  (1, 'BR', 'ada@example.com'),
  (2, 'US', 'ben@example.com')""".strip(),
            f"""
CREATE OR REPLACE ROW ACCESS POLICY {policy_name(config, "REGION_RAP")}
AS (REGION VARCHAR) RETURNS BOOLEAN -> REGION = 'BR'""".strip(),
            f"""
CREATE OR REPLACE MASKING POLICY {policy_name(config, "EMAIL_MASK")}
AS (VAL VARCHAR, REGION VARCHAR) RETURNS VARCHAR ->
  CASE WHEN REGION = 'BR' THEN VAL ELSE 'MASKED' END""".strip(),
        )
    )
    return tuple(commands)


def validation_queries(config: SnowflakeSmokeConfig) -> dict[str, str]:
    row_target = config.qualified_target("ROW_ACCESS_TARGET")
    mask_target = config.qualified_target("MASKING_TARGET")
    return {
        "row_access_allowed_count": f"SELECT COUNT(*) FROM {row_target}",
        "row_access_blocked_count": f"SELECT COUNT(*) FROM {row_target} WHERE CUSTOMER_ID = 2",
        "masking_allowed_email": f"SELECT EMAIL FROM {mask_target} WHERE CUSTOMER_ID = 1",
        "masking_blocked_email": f"SELECT EMAIL FROM {mask_target} WHERE CUSTOMER_ID = 2",
    }


def cleanup_commands(config: SnowflakeSmokeConfig) -> tuple[str, ...]:
    evidence_prefix = schema_name(config, config.evidence_schema)
    return (
        f"DROP TABLE IF EXISTS {config.qualified_target('ROW_ACCESS_TARGET')}",
        f"DROP TABLE IF EXISTS {config.qualified_target('MASKING_TARGET')}",
        f"DROP TABLE IF EXISTS {config.qualified_source('ACCESS_SOURCE')}",
        f"DROP ROW ACCESS POLICY IF EXISTS {policy_name(config, 'REGION_RAP')}",
        f"DROP MASKING POLICY IF EXISTS {policy_name(config, 'EMAIL_MASK')}",
        f"DROP TABLE IF EXISTS {evidence_prefix}.{quote_identifier('ctrl_ingestion_access')}",
        f"DROP TABLE IF EXISTS {evidence_prefix}.{quote_identifier('ctrl_ingestion_runs')}",
        f"DROP TABLE IF EXISTS {evidence_prefix}.{quote_identifier('ctrl_ingestion_errors')}",
        f"DROP TABLE IF EXISTS {evidence_prefix}.{quote_identifier('ctrl_ingestion_lineage')}",
        f"DROP TABLE IF EXISTS {evidence_prefix}.{quote_identifier('ctrl_ingestion_state')}",
    )


def policy_name(config: SnowflakeSmokeConfig, suffix: str) -> str:
    return f"{schema_name(config, config.target_schema)}.{quote_identifier(config.table_prefix + '_' + suffix)}"


def schema_name(config: SnowflakeSmokeConfig, schema: str) -> str:
    return f"{quote_identifier(config.database)}.{quote_identifier(schema)}"


def _run_contracts(config: SnowflakeSmokeConfig, *, session: Any) -> dict[str, Any]:
    base_dir = config.output_dir
    if base_dir is not None:
        base_dir.mkdir(parents=True, exist_ok=True)
        return _run_contracts_from_dir(base_dir, config, session=session)
    with tempfile.TemporaryDirectory(prefix="contractforge-snowflake-access-smoke-") as temp:
        return _run_contracts_from_dir(Path(temp), config, session=session)


def _run_contracts_from_dir(base_dir: Path, config: SnowflakeSmokeConfig, *, session: Any) -> dict[str, Any]:
    contracts = access_policy_contracts(config)
    environment = environment_payload(config)
    contract_dir = base_dir / "contracts"
    contract_dir.mkdir(parents=True, exist_ok=True)
    environment_path = base_dir / "environment.json"
    environment_path.write_text(json.dumps(environment, indent=2, sort_keys=True), encoding="utf-8")
    results: dict[str, Any] = {}
    for name, contract in contracts.items():
        contract_path = contract_dir / f"{name}.contract.json"
        contract_path.write_text(json.dumps(contract, indent=2, sort_keys=True), encoding="utf-8")
        try:
            result = run_snowflake_contract(contract_uri=str(contract_path), environment_uri=str(environment_path), session=session)
            results[name] = {"ok": True, "result": result}
        except Exception as exc:  # pragma: no cover - live diagnostic path
            results[name] = {"ok": False, "error": str(exc)}
    return results


def _validations(config: SnowflakeSmokeConfig, *, session: Any) -> dict[str, Any]:
    queries = validation_queries(config)
    row_access_allowed_count = scalar_int(session, queries["row_access_allowed_count"], key="COUNT")
    row_access_blocked_count = scalar_int(session, queries["row_access_blocked_count"], key="COUNT")
    masking_allowed_email = _single_value(session, queries["masking_allowed_email"])
    masking_blocked_email = _single_value(session, queries["masking_blocked_email"])
    checks = {
        "row_access_allowed_count": row_access_allowed_count == 1,
        "row_access_blocked_count": row_access_blocked_count == 0,
        "masking_allowed_email": masking_allowed_email == "ada@example.com",
        "masking_blocked_email": masking_blocked_email == "MASKED",
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "observed": {
            "row_access_allowed_count": row_access_allowed_count,
            "row_access_blocked_count": row_access_blocked_count,
            "masking_allowed_email": masking_allowed_email,
            "masking_blocked_email": masking_blocked_email,
        },
    }


def _single_value(session: Any, query: str) -> Any:
    rows = collect_rows(session, query)
    if not rows:
        return None
    row = rows[0]
    if isinstance(row, dict):
        return next(iter(row.values()), None)
    return row[0]


def _control_count(config: SnowflakeSmokeConfig, session: Any, table: str) -> int:
    return scalar_int(session, f"SELECT COUNT(*) FROM {schema_name(config, config.evidence_schema)}.{quote_identifier(table)}", key="COUNT")


def _write_summary(config: SnowflakeSmokeConfig, payload: dict[str, Any]) -> None:
    if config.output_dir is None:
        return
    config.output_dir.mkdir(parents=True, exist_ok=True)
    (config.output_dir / "summary.json").write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
