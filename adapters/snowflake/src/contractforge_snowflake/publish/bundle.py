"""Publish artifacts for the Snowflake library-runner execution model."""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from typing import Any

from contractforge_core.planner import PlanningResult
from contractforge_core.semantic import SemanticContract
from contractforge_snowflake.environment import SnowflakeEnvironment
from contractforge_snowflake.evidence import render_create_evidence_tables_sql, render_create_state_tables_sql


def snowflake_publish_artifacts(
    *,
    contract: SemanticContract,
    raw_contract: dict[str, Any] | None,
    environment: SnowflakeEnvironment,
    planning: PlanningResult | None,
) -> dict[str, str]:
    """Return publishable artifacts consumed by a stable Snowflake runner.

    These artifacts are configuration and bootstrap metadata. They deliberately
    do not include per-contract ingestion SQL such as source or write scripts.
    """

    prefix = _artifact_prefix(contract)
    contract_name = f"runtime/{prefix}.contract.json"
    environment_name = f"runtime/{prefix}.environment.json"
    invocation_name = f"runtime/{prefix}.runner_invocation.json"
    infrastructure_name = f"infrastructure/{prefix}.evidence_ddl.sql"
    runtime_contract = raw_contract if raw_contract is not None else asdict(contract)
    artifacts = {
        contract_name: _json(runtime_contract),
        environment_name: _json(_environment_payload(environment)),
        invocation_name: _json(
            {
                "adapter": "snowflake",
                "execution_model": "library_runner",
                "runner_module": "contractforge_snowflake.runtime",
                "runner_function": "run_snowflake_contract",
                "contract_artifact": contract_name,
                "environment_artifact": environment_name,
                "planning_status": planning.status if planning else None,
                "warehouse": environment.warehouse,
                "role": environment.role,
            }
        ),
        infrastructure_name: _evidence_bootstrap_sql(environment),
    }
    return artifacts


def _artifact_prefix(contract: SemanticContract) -> str:
    namespace = contract.target.namespace or contract.target.layer
    text = "_".join(part for part in (namespace, contract.target.name) if part)
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("._-")
    return normalized or "contract"


def _environment_payload(environment: SnowflakeEnvironment) -> dict[str, Any]:
    return {
        "evidence": {
            "database": environment.evidence_database,
            "schema": environment.evidence_schema,
            "store": "snowflake_audit_tables",
            "create_database": environment.evidence_create_database,
            "create_schema": environment.evidence_create_schema,
            "validate_only_ddl": environment.evidence_validate_only_ddl,
        },
        "artifacts": {"uri": environment.artifact_uri},
        "parameters": {
            "snowflake": {
                "warehouse": environment.warehouse,
                "role": environment.role,
                "runtime_database": environment.runtime_database,
                "runtime_schema": environment.runtime_schema,
                "task_database": environment.task_database,
                "task_schema": environment.task_schema,
            }
        },
    }


def _evidence_bootstrap_sql(environment: SnowflakeEnvironment) -> str:
    database = environment.evidence_database or "CONTRACTFORGE"
    schema = environment.evidence_schema or "CF_EVIDENCE"
    return "\n".join(
        (
            "-- ContractForge Snowflake evidence bootstrap.",
            "-- Infrastructure artifact only; ingestion logic lives in contractforge_snowflake runtime.",
            render_create_evidence_tables_sql(
                database=database,
                schema=schema,
                create_database=environment.evidence_create_database,
                create_schema=environment.evidence_create_schema,
            ).rstrip(),
            render_create_state_tables_sql(
                database=database,
                schema=schema,
                create_database=environment.evidence_create_database,
                create_schema=environment.evidence_create_schema,
            ).rstrip(),
            "",
        )
    )


def _json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n"
