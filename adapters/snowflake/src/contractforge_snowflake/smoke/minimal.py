"""CLI entry point for the minimal Snowflake adapter smoke test."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

from contractforge_snowflake.runtime import SnowflakeConnectorSession
from contractforge_snowflake.smoke.connection import require_smoke_connection, smoke_connect_options
from contractforge_snowflake.smoke.models import SnowflakeSmokeConfig
from contractforge_snowflake.smoke.runner import dry_run_payload, execute_smoke


def main(
    argv: list[str] | None = None,
    *,
    connect: Callable[[dict[str, Any] | None], Any] | None = None,
    load_connect_options: Callable[[Path | None], dict[str, Any] | None] | None = None,
) -> int:
    parser = argparse.ArgumentParser(prog="contractforge-snowflake smoke-minimal")
    parser.add_argument("--connection", help="Snowflake CLI connection name for operator reference.")
    parser.add_argument("--connect-options", type=Path, help="YAML options passed to snowflake.connector.connect.")
    parser.add_argument("--database", default="CONTRACTFORGE_TEST_DB")
    parser.add_argument("--source-schema", default="PUBLIC")
    parser.add_argument("--target-schema", default="PUBLIC")
    parser.add_argument("--evidence-schema", default="PUBLIC")
    parser.add_argument("--schema", dest="all_schema", help="Use one schema for source, target, and evidence.")
    parser.add_argument("--table-prefix", default="CF_SMOKE")
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
        command_name="Snowflake minimal smoke",
    )
    if not args.execute_cleanup:
        raise ValueError("Snowflake minimal smoke live execution requires --execute-cleanup")
    if connect is None or load_connect_options is None:
        raise ValueError("Snowflake minimal smoke connector hooks were not provided")

    connection = connect(
        smoke_connect_options(
            connection=args.connection,
            connect_options=args.connect_options,
            load_connect_options=load_connect_options,
        )
    )
    try:
        payload = execute_smoke(
            config,
            session=SnowflakeConnectorSession(connection),
            execute_cleanup=args.execute_cleanup,
        )
    finally:
        if hasattr(connection, "close"):
            connection.close()
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0 if payload["status"] == "SUCCESS" else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
