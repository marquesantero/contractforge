"""CLI entry point for Snowflake runtime procedure smoke tests."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

from contractforge_snowflake.deployment.procedure import render_runtime_procedure_sql
from contractforge_snowflake.naming import quote_identifier, quote_multipart_identifier
from contractforge_snowflake.runtime import SnowflakeConnectorSession, publish_snowflake_contract, run_snowflake_contract
from contractforge_snowflake.session_ops import execute, scalar_int
from contractforge_snowflake.smoke.connection import require_smoke_connection, smoke_connect_options
from contractforge_snowflake.smoke.models import SnowflakeSmokeConfig
from contractforge_snowflake.sql import sql_string


def main(
    argv: list[str] | None = None,
    *,
    connect: Callable[[dict[str, Any] | None], Any] | None = None,
    load_connect_options: Callable[[Path | None], dict[str, Any] | None] | None = None,
) -> int:
    parser = argparse.ArgumentParser(prog="contractforge-snowflake smoke-procedure")
    parser.add_argument("--connection")
    parser.add_argument("--connect-options", type=Path)
    parser.add_argument("--database", default="CONTRACTFORGE_TEST_DB")
    parser.add_argument("--source-schema", default="PUBLIC")
    parser.add_argument("--target-schema", default="PUBLIC")
    parser.add_argument("--evidence-schema", default="PUBLIC")
    parser.add_argument("--schema", dest="all_schema")
    parser.add_argument("--table-prefix", default="CF_SMOKE_PROC")
    parser.add_argument("--warehouse", default="COMPUTE_WH")
    parser.add_argument("--role", default="CONTRACTFORGE_INGEST_ROLE")
    parser.add_argument("--stage-name")
    parser.add_argument("--prefix")
    parser.add_argument("--procedure-name")
    parser.add_argument("--core-wheel", type=Path)
    parser.add_argument("--adapter-wheel", type=Path)
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
    procedure_name = args.procedure_name or f"{config.table_prefix}_RUNNER"
    procedure = f"{config.database}.{config.evidence_schema}.{procedure_name}"
    if not args.execute:
        print(
            json.dumps(
                {
                    "execute": False,
                    "execute_cleanup": args.execute_cleanup,
                    "config": config.summary_config(),
                    "stage": stage,
                    "prefix": prefix,
                    "procedure": procedure,
                    "core_wheel": str(args.core_wheel) if args.core_wheel else None,
                    "adapter_wheel": str(args.adapter_wheel) if args.adapter_wheel else None,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    require_smoke_connection(
        connection=args.connection,
        connect_options=args.connect_options,
        command_name="Snowflake procedure smoke",
    )
    if not args.core_wheel or not args.adapter_wheel:
        raise ValueError("Snowflake procedure smoke requires --core-wheel and --adapter-wheel")
    if not args.execute_cleanup:
        raise ValueError("Snowflake procedure smoke live execution requires --execute-cleanup")
    if connect is None or load_connect_options is None:
        raise ValueError("Snowflake procedure smoke connector hooks were not provided")

    connection = connect(
        smoke_connect_options(
            connection=args.connection,
            connect_options=args.connect_options,
            load_connect_options=load_connect_options,
        )
    )
    session = SnowflakeConnectorSession(connection)
    try:
        payload = _execute_procedure_smoke(
            config=config,
            stage=stage,
            prefix=prefix,
            procedure=procedure,
            core_wheel=args.core_wheel,
            adapter_wheel=args.adapter_wheel,
            connection=connection,
            session=session,
            execute_cleanup=args.execute_cleanup,
        )
    finally:
        if hasattr(connection, "close"):
            connection.close()
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0 if payload["status"] == "SUCCESS" else 1


def _execute_procedure_smoke(
    *,
    config: SnowflakeSmokeConfig,
    stage: str,
    prefix: str,
    procedure: str,
    core_wheel: Path,
    adapter_wheel: Path,
    connection: Any,
    session: SnowflakeConnectorSession,
    execute_cleanup: bool,
) -> dict[str, Any]:
    for wheel in (core_wheel, adapter_wheel):
        if not wheel.exists() or wheel.suffix != ".whl":
            raise ValueError(f"Snowflake procedure smoke wheel does not exist: {wheel}")
    if execute_cleanup:
        execute(session, f"DROP PROCEDURE IF EXISTS {quote_multipart_identifier(procedure)}(STRING, STRING)")
        execute(session, f"DROP TABLE IF EXISTS {config.qualified_target('PROCEDURE_TARGET')}")
        execute(session, f"DROP TABLE IF EXISTS {config.qualified_source('PROCEDURE_SOURCE')}")
    execute(session, f"CREATE TEMPORARY STAGE {_qualified_stage_object(config.database, config.evidence_schema, stage.lstrip('@'))}")
    execute(
        session,
        f"""
CREATE OR REPLACE TABLE {config.qualified_source("PROCEDURE_SOURCE")} (
  id NUMBER,
  email VARCHAR
)""".strip(),
    )
    execute(
        session,
        f"""
INSERT INTO {config.qualified_source("PROCEDURE_SOURCE")} (id, email)
SELECT * FROM VALUES
  (1, 'ada@example.com'),
  (2, 'ben@example.com')""".strip(),
    )
    core_uri = _put_wheel(connection, wheel=core_wheel, stage=stage, prefix=f"{prefix}/libs")
    adapter_uri = _put_wheel(connection, wheel=adapter_wheel, stage=stage, prefix=f"{prefix}/libs")
    artifact_root = f"{stage}/{prefix}/artifacts"
    environment = _environment(config, artifact_uri=artifact_root, procedure=procedure, core_uri=core_uri, adapter_uri=adapter_uri)
    contract = _contract(config)
    published = publish_snowflake_contract(contract, environment=environment, connection=connection)
    for statement in _procedure_statements(render_runtime_procedure_sql(environment)):
        execute(session, statement)
    contract_uri = _artifact_uri(published, suffix=".contract.json")
    environment_uri = _artifact_uri(published, suffix=".environment.json")
    call_sql = (
        f"CALL {quote_multipart_identifier(procedure)}"
        f"({sql_string(contract_uri)}, {sql_string(environment_uri)})"
    )
    call_result = session.sql(call_sql)
    rows = call_result.collect()
    procedure_payload = json.loads(rows[0][0]) if rows else {}
    target_count = scalar_int(session, f"SELECT COUNT(*) FROM {config.qualified_target('PROCEDURE_TARGET')}", key="COUNT")
    if execute_cleanup:
        execute(session, f"DROP PROCEDURE IF EXISTS {quote_multipart_identifier(procedure)}(STRING, STRING)")
        execute(session, f"DROP TABLE IF EXISTS {config.qualified_target('PROCEDURE_TARGET')}")
        execute(session, f"DROP TABLE IF EXISTS {config.qualified_source('PROCEDURE_SOURCE')}")
    return {
        "status": "SUCCESS",
        "run_status": procedure_payload.get("status"),
        "procedure_query_id": call_result.query_id,
        "procedure": procedure,
        "stage": stage,
        "prefix": prefix,
        "core_import": core_uri,
        "adapter_import": adapter_uri,
        "contract_uri": contract_uri,
        "environment_uri": environment_uri,
        "target_count": target_count,
    }


def _contract(config: SnowflakeSmokeConfig) -> dict[str, Any]:
    return {
        "source": {"type": "table", "table": f"{config.source_namespace}.{config.source_table('PROCEDURE_SOURCE')}"},
        "target": {**config.target_namespace, "table": config.target_table("PROCEDURE_TARGET")},
        "mode": "scd0_append",
        "schema_policy": "additive_only",
    }


def _environment(
    config: SnowflakeSmokeConfig,
    *,
    artifact_uri: str,
    procedure: str,
    core_uri: str,
    adapter_uri: str,
) -> dict[str, Any]:
    return {
        "evidence": {
            "database": config.database,
            "schema": config.evidence_schema,
            "create_database": False,
            "create_schema": False,
        },
        "artifacts": {"uri": artifact_uri},
        "parameters": {
            "snowflake": {
                "warehouse": config.warehouse,
                "role": config.role,
                "runner_procedure": procedure,
                "runtime_wheel_uri": adapter_uri,
                "runtime_imports": [core_uri],
                "runtime_create_database": False,
                "runtime_create_schema": False,
            }
        },
    }


def _put_wheel(connection: Any, *, wheel: Path, stage: str, prefix: str) -> str:
    """Upload a wheel archive using Snowflake's ZIP import-compatible suffix."""

    with tempfile.TemporaryDirectory(prefix="contractforge-snowflake-runtime-") as tmpdir:
        archive = _zip_copy_for_snowflake_import(wheel, root=Path(tmpdir))
        return _put_file(connection, file=archive, stage=stage, prefix=prefix)


def _put_file(connection: Any, *, file: Path, stage: str, prefix: str) -> str:
    target = f"{stage.rstrip('/')}/{prefix.strip('/')}"
    cursor = connection.cursor()
    try:
        cursor.execute(f"PUT '{_file_uri(file)}' {target} AUTO_COMPRESS=FALSE OVERWRITE=TRUE")
    finally:
        cursor.close()
    return f"{target}/{file.name}"


def _zip_copy_for_snowflake_import(wheel: Path, *, root: Path) -> Path:
    archive = root / f"{wheel.stem}.zip"
    shutil.copyfile(wheel, archive)
    return archive


def _procedure_statements(sql: str) -> tuple[str, ...]:
    body = "\n".join(line for line in sql.splitlines() if not line.strip().startswith("--"))
    return tuple(part.strip() for part in body.split(";\n") if part.strip())


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


def _file_uri(path: Path) -> str:
    return "file://" + path.resolve().as_posix().replace("'", "''")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
