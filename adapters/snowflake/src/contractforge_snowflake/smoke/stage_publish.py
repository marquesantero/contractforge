"""CLI entry point for Snowflake stage publish smoke tests."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

from contractforge_snowflake.naming import quote_identifier
from contractforge_snowflake.runtime import SnowflakeConnectorSession, publish_snowflake_contract, run_snowflake_contract
from contractforge_snowflake.runtime.artifacts import load_json_artifact
from contractforge_snowflake.session_ops import execute, scalar_int
from contractforge_snowflake.smoke.connection import require_smoke_connection, smoke_connect_options
from contractforge_snowflake.smoke.models import SnowflakeSmokeConfig


def main(
    argv: list[str] | None = None,
    *,
    connect: Callable[[dict[str, Any] | None], Any] | None = None,
    load_connect_options: Callable[[Path | None], dict[str, Any] | None] | None = None,
) -> int:
    parser = argparse.ArgumentParser(prog="contractforge-snowflake smoke-stage-publish")
    parser.add_argument("--connection", help="Snowflake CLI connection name for operator reference.")
    parser.add_argument("--connect-options", type=Path, help="YAML options passed to snowflake.connector.connect.")
    parser.add_argument("--database", default="CONTRACTFORGE_TEST_DB")
    parser.add_argument("--source-schema", default="PUBLIC")
    parser.add_argument("--target-schema", default="PUBLIC")
    parser.add_argument("--evidence-schema", default="PUBLIC")
    parser.add_argument("--schema", dest="all_schema", help="Use one schema for source, target, and evidence.")
    parser.add_argument("--table-prefix", default="CF_SMOKE_STAGE")
    parser.add_argument("--warehouse", default="COMPUTE_WH")
    parser.add_argument("--role", default="CONTRACTFORGE_INGEST_ROLE")
    parser.add_argument("--stage-name")
    parser.add_argument("--prefix")
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
    )
    stage_name = args.stage_name or f"{config.table_prefix}_ARTIFACTS"
    stage = _qualified_stage(config.database, config.evidence_schema, stage_name)
    prefix = args.prefix or config.table_prefix.lower()
    contract = _contract(config)
    environment = _environment(config, artifact_uri=f"{stage}/{prefix}")
    if not args.execute:
        print(
            json.dumps(
                {
                    "execute": False,
                    "execute_cleanup": args.execute_cleanup,
                    "config": config.summary_config(),
                    "stage": stage,
                    "prefix": prefix,
                    "contract_target": contract["target"],
                    "artifact_uri": environment["artifacts"]["uri"],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    require_smoke_connection(
        connection=args.connection,
        connect_options=args.connect_options,
        command_name="Snowflake stage publish smoke",
    )
    if not args.execute_cleanup:
        raise ValueError("Snowflake stage publish smoke live execution requires --execute-cleanup")
    if connect is None or load_connect_options is None:
        raise ValueError("Snowflake stage publish smoke connector hooks were not provided")

    connection = connect(
        smoke_connect_options(
            connection=args.connection,
            connect_options=args.connect_options,
            load_connect_options=load_connect_options,
        )
    )
    session = SnowflakeConnectorSession(connection)
    try:
        payload = _execute_stage_publish_smoke(
            config=config,
            contract=contract,
            environment=environment,
            stage=stage,
            prefix=prefix,
            connection=connection,
            session=session,
            execute_cleanup=args.execute_cleanup,
        )
    finally:
        if hasattr(connection, "close"):
            connection.close()
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0 if payload["status"] == "SUCCESS" else 1


def _execute_stage_publish_smoke(
    *,
    config: SnowflakeSmokeConfig,
    contract: dict[str, Any],
    environment: dict[str, Any],
    stage: str,
    prefix: str,
    connection: Any,
    session: SnowflakeConnectorSession,
    execute_cleanup: bool,
) -> dict[str, Any]:
    if execute_cleanup:
        execute(session, f"DROP TABLE IF EXISTS {config.qualified_target('PUBLISH_TARGET')}")
        execute(session, f"DROP TABLE IF EXISTS {config.qualified_source('PUBLISH_SOURCE')}")
    execute(session, f"CREATE TEMPORARY STAGE {_qualified_stage_object(config.database, config.evidence_schema, stage.lstrip('@'))}")
    execute(
        session,
        f"""
CREATE OR REPLACE TABLE {config.qualified_source("PUBLISH_SOURCE")} (
  id NUMBER,
  email VARCHAR
)""".strip(),
    )
    execute(
        session,
        f"""
INSERT INTO {config.qualified_source("PUBLISH_SOURCE")} (id, email)
SELECT * FROM VALUES
  (1, 'ada@example.com'),
  (2, 'ben@example.com')""".strip(),
    )
    published = publish_snowflake_contract(contract, environment=environment, connection=connection)
    manifest = load_json_artifact(published.manifest_uri, session=session)
    contract_uri = _artifact_uri(published, suffix=".contract.json")
    environment_uri = _artifact_uri(published, suffix=".environment.json")
    result = run_snowflake_contract(contract_uri=contract_uri, environment_uri=environment_uri, session=session)
    target_count = scalar_int(session, f"SELECT COUNT(*) FROM {config.qualified_target('PUBLISH_TARGET')}", key="COUNT")
    if execute_cleanup:
        execute(session, f"DROP TABLE IF EXISTS {config.qualified_target('PUBLISH_TARGET')}")
        execute(session, f"DROP TABLE IF EXISTS {config.qualified_source('PUBLISH_SOURCE')}")
    return {
        "status": "SUCCESS",
        "run_status": result["status"],
        "stage": published.stage,
        "prefix": published.prefix,
        "manifest_uri": published.manifest_uri,
        "contract_uri": contract_uri,
        "environment_uri": environment_uri,
        "artifact_count": len(published.artifacts),
        "manifest_artifact_count": manifest.get("artifact_summary", {}).get("count"),
        "target_count": target_count,
    }


def _contract(config: SnowflakeSmokeConfig) -> dict[str, Any]:
    return {
        "source": {"type": "table", "table": f"{config.source_namespace}.{config.source_table('PUBLISH_SOURCE')}"},
        "target": {**config.target_namespace, "table": config.target_table("PUBLISH_TARGET")},
        "mode": "scd0_append",
        "schema_policy": "additive_only",
    }


def _environment(config: SnowflakeSmokeConfig, *, artifact_uri: str) -> dict[str, Any]:
    return {
        "evidence": {
            "database": config.database,
            "schema": config.evidence_schema,
            "create_database": False,
            "create_schema": False,
        },
        "artifacts": {"uri": artifact_uri},
        "parameters": {"snowflake": {"warehouse": config.warehouse, "role": config.role}},
    }


def _artifact_uri(result: Any, *, suffix: str) -> str:
    for artifact in result.artifacts:
        if artifact.name.endswith(suffix):
            return artifact.uri
    raise RuntimeError(f"Published artifact not found: {suffix}")


def _qualified_stage(database: str, schema: str, stage_name: str) -> str:
    return f"@{quote_identifier(database)}.{quote_identifier(schema)}.{quote_identifier(stage_name)}"


def _qualified_stage_object(database: str, schema: str, stage_reference: str) -> str:
    name = stage_reference.split(".")[-1].strip('"')
    return f"{quote_identifier(database)}.{quote_identifier(schema)}.{quote_identifier(name)}"


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
