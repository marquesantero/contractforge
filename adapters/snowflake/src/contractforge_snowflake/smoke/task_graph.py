"""CLI entry point for Snowflake task graph smoke tests."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

import yaml

from contractforge_snowflake.deployment import render_task_history_query, render_task_lifecycle_sql
from contractforge_snowflake.naming import quote_identifier, quote_multipart_identifier
from contractforge_snowflake.runtime import SnowflakeConnectorSession, deploy_snowflake_project, wait_snowflake_project_tasks
from contractforge_snowflake.session_ops import execute, scalar_int, scalar_value
from contractforge_snowflake.smoke.connection import require_smoke_connection, smoke_connect_options
from contractforge_snowflake.smoke.models import SnowflakeSmokeConfig
from contractforge_snowflake.smoke.procedure import _put_wheel


def main(
    argv: list[str] | None = None,
    *,
    connect: Callable[[dict[str, Any] | None], Any] | None = None,
    load_connect_options: Callable[[Path | None], dict[str, Any] | None] | None = None,
) -> int:
    parser = argparse.ArgumentParser(prog="contractforge-snowflake smoke-task-graph")
    parser.add_argument("--connection")
    parser.add_argument("--connect-options", type=Path)
    parser.add_argument("--database", default="CONTRACTFORGE_TEST_DB")
    parser.add_argument("--source-schema", default="PUBLIC")
    parser.add_argument("--target-schema", default="PUBLIC")
    parser.add_argument("--evidence-schema", default="PUBLIC")
    parser.add_argument("--schema", dest="all_schema")
    parser.add_argument("--table-prefix", default="CF_SMOKE_TASK")
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
    environment = _environment(config, artifact_uri=f"{stage}/{prefix}/artifacts", procedure=procedure)
    task_names = ("bronze_customers", "silver_customers")
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
                    "task_names": task_names,
                    "resume_sql": render_task_lifecycle_sql(environment=environment, task_names=task_names, action="resume"),
                    "execute_sql": render_task_lifecycle_sql(environment=environment, task_names=("bronze_customers",), action="execute"),
                    "suspend_sql": render_task_lifecycle_sql(environment=environment, task_names=task_names, action="suspend"),
                    "history_sql": render_task_history_query(environment=environment, task_names=task_names, limit=20),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    require_smoke_connection(
        connection=args.connection,
        connect_options=args.connect_options,
        command_name="Snowflake task graph smoke",
    )
    if not args.core_wheel or not args.adapter_wheel:
        raise ValueError("Snowflake task graph smoke requires --core-wheel and --adapter-wheel")
    if not args.execute_cleanup:
        raise ValueError("Snowflake task graph smoke live execution requires --execute-cleanup")
    if connect is None or load_connect_options is None:
        raise ValueError("Snowflake task graph smoke connector hooks were not provided")

    connection = connect(
        smoke_connect_options(
            connection=args.connection,
            connect_options=args.connect_options,
            load_connect_options=load_connect_options,
        )
    )
    session = SnowflakeConnectorSession(connection)
    try:
        payload = _execute_task_graph_smoke(
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


def _execute_task_graph_smoke(
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
    environment = _environment(config, artifact_uri=f"{stage}/{prefix}/artifacts", procedure=procedure)
    if execute_cleanup:
        _cleanup(session, config=config, procedure=procedure, stage=stage)
    execute(session, f"CREATE OR REPLACE STAGE {_qualified_stage_object(config.database, config.evidence_schema, stage.lstrip('@'))}")
    _setup_source(session, config)
    core_uri = _put_wheel(connection, wheel=core_wheel, stage=stage, prefix=f"{prefix}/libs")
    adapter_uri = _put_wheel(connection, wheel=adapter_wheel, stage=stage, prefix=f"{prefix}/libs")
    environment["parameters"]["snowflake"]["runtime_imports"] = [core_uri]
    environment["parameters"]["snowflake"]["runtime_wheel_uri"] = adapter_uri
    with tempfile.TemporaryDirectory(prefix="contractforge-snowflake-task-") as tmpdir:
        project_file = _write_project(Path(tmpdir), config=config, environment=environment)
        deployment = deploy_snowflake_project(project_file, stage=stage, prefix=f"{prefix}/artifacts", connection=connection)
    task_names = tuple(step.name for step in deployment.steps)
    execution_started_at = scalar_value(session, "SELECT CURRENT_TIMESTAMP()", key="CURRENT_TIMESTAMP()")
    lifecycle_commands = _run_lifecycle(session, environment=environment, task_names=task_names)
    wait_payload = wait_snowflake_project_tasks(
        connection=connection,
        environment=environment,
        task_names=task_names,
        poll_interval_seconds=2,
        max_wait_seconds=180,
        started_after=execution_started_at,
    )
    bronze_count = scalar_int(session, f"SELECT COUNT(*) FROM {config.qualified_target('TASK_BRONZE')}", key="COUNT")
    silver_count = scalar_int(session, f"SELECT COUNT(*) FROM {config.qualified_target('TASK_SILVER')}", key="COUNT")
    if execute_cleanup:
        _cleanup(session, config=config, procedure=procedure, task_names=task_names, stage=stage)
    return {
        "status": "SUCCESS",
        "stage": stage,
        "prefix": prefix,
        "procedure": procedure,
        "task_names": task_names,
        "artifact_counts": [step.artifact_count for step in deployment.steps],
        "deployment_command_count": len(deployment.applied_deployment_commands),
        "lifecycle_command_count": len(lifecycle_commands),
        "task_wait": wait_payload,
        "history_rows": len(wait_payload["tasks"]),
        "bronze_count": bronze_count,
        "silver_count": silver_count,
    }


def _run_lifecycle(session: SnowflakeConnectorSession, *, environment: dict[str, Any], task_names: tuple[str, ...]) -> tuple[str, ...]:
    commands: list[str] = []
    for sql in (
        render_task_lifecycle_sql(environment=environment, task_names=tuple(reversed(task_names)), action="resume"),
        render_task_lifecycle_sql(environment=environment, task_names=(task_names[0],), action="execute"),
    ):
        for command in _split_sql(sql):
            execute(session, command)
            commands.append(command)
    return tuple(commands)


def _setup_source(session: SnowflakeConnectorSession, config: SnowflakeSmokeConfig) -> None:
    execute(
        session,
        f"""
CREATE OR REPLACE TABLE {config.qualified_source("TASK_SOURCE")} (
  id NUMBER,
  email VARCHAR
)""".strip(),
    )
    execute(
        session,
        f"""
INSERT INTO {config.qualified_source("TASK_SOURCE")} (id, email)
SELECT * FROM VALUES
  (1, 'ada@example.com'),
  (2, 'ben@example.com')""".strip(),
    )


def _cleanup(
    session: SnowflakeConnectorSession,
    *,
    config: SnowflakeSmokeConfig,
    procedure: str,
    stage: str | None = None,
    task_names: tuple[str, ...] = ("bronze_customers", "silver_customers"),
) -> None:
    for task_name in task_names:
        execute(session, f"ALTER TASK IF EXISTS {_task_identifier(config, task_name)} SUSPEND")
    for task_name in reversed(task_names):
        execute(session, f"DROP TASK IF EXISTS {_task_identifier(config, task_name)}")
    execute(session, f"DROP PROCEDURE IF EXISTS {quote_multipart_identifier(procedure)}(STRING, STRING)")
    for suffix in ("TASK_SILVER", "TASK_BRONZE", "TASK_SOURCE"):
        execute(session, f"DROP TABLE IF EXISTS {config.qualified_target(suffix)}")
        if suffix == "TASK_SOURCE":
            execute(session, f"DROP TABLE IF EXISTS {config.qualified_source(suffix)}")
    if stage:
        execute(session, f"DROP STAGE IF EXISTS {_qualified_stage_object(config.database, config.evidence_schema, stage.lstrip('@'))}")


def _write_project(root: Path, *, config: SnowflakeSmokeConfig, environment: dict[str, Any]) -> Path:
    contracts = root / "contracts"
    envs = root / "envs"
    contracts.mkdir()
    envs.mkdir()
    (envs / "snowflake.yaml").write_text(yaml.safe_dump(environment, sort_keys=False), encoding="utf-8")
    (contracts / "bronze.yaml").write_text(yaml.safe_dump(_bronze_contract(config), sort_keys=False), encoding="utf-8")
    (contracts / "silver.yaml").write_text(yaml.safe_dump(_silver_contract(config), sort_keys=False), encoding="utf-8")
    project = {
        "name": "snowflake_task_smoke",
        "environments": {"snowflake": "envs/snowflake.yaml"},
        "schedule": {"cron": "0 6 * * *", "timezone": "UTC"},
        "execution_order": [
            {"name": "bronze_customers", "contracts": {"snowflake": "contracts/bronze.yaml"}},
            {
                "name": "silver_customers",
                "depends_on": ["bronze_customers"],
                "contracts": {"snowflake": "contracts/silver.yaml"},
            },
        ],
    }
    project_file = root / "project.yaml"
    project_file.write_text(yaml.safe_dump(project, sort_keys=False), encoding="utf-8")
    return project_file


def _bronze_contract(config: SnowflakeSmokeConfig) -> dict[str, Any]:
    return {
        "source": {"type": "table", "table": f"{config.source_namespace}.{config.source_table('TASK_SOURCE')}"},
        "target": {**config.target_namespace, "table": config.target_table("TASK_BRONZE")},
        "mode": "scd0_append",
        "schema_policy": "additive_only",
    }


def _silver_contract(config: SnowflakeSmokeConfig) -> dict[str, Any]:
    return {
        "source": {"type": "table", "table": f"{config.database}.{config.target_schema}.{config.target_table('TASK_BRONZE')}"},
        "target": {**config.target_namespace, "table": config.target_table("TASK_SILVER")},
        "mode": "scd0_append",
        "schema_policy": "additive_only",
    }


def _environment(config: SnowflakeSmokeConfig, *, artifact_uri: str, procedure: str) -> dict[str, Any]:
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
                "runtime_create_database": False,
                "runtime_create_schema": False,
                "task_database": config.database,
                "task_schema": config.evidence_schema,
                "task_create_database": False,
                "task_create_schema": False,
            }
        },
    }


def _split_sql(sql: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in sql.split(";") if part.strip())


def _qualified_stage(database: str, schema: str, stage_name: str) -> str:
    return f"@{quote_identifier(database)}.{quote_identifier(schema)}.{quote_identifier(stage_name)}"


def _qualified_stage_object(database: str, schema: str, stage_reference: str) -> str:
    name = stage_reference.split(".")[-1].strip('"')
    return f"{quote_identifier(database)}.{quote_identifier(schema)}.{quote_identifier(name)}"


def _task_identifier(config: SnowflakeSmokeConfig, task_name: str) -> str:
    return ".".join((quote_identifier(config.database), quote_identifier(config.evidence_schema), quote_identifier(task_name)))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
