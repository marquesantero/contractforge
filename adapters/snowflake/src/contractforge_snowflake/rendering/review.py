"""Build deterministic Snowflake planning and publish artifacts."""

from __future__ import annotations

import json

from contractforge_core.adapters import RenderedArtifacts
from contractforge_core.planner import ExecutionPlan, PlanningResult
from contractforge_core.semantic import SemanticContract
from contractforge_snowflake.environment import SnowflakeEnvironment
from contractforge_snowflake.publish import snowflake_publish_artifacts


def render_snowflake_review_artifacts(
    *,
    plan: ExecutionPlan | None,
    planning: PlanningResult | None,
    contract: SemanticContract | None = None,
    raw_contract: dict | None = None,
    environment: SnowflakeEnvironment | None = None,
) -> RenderedArtifacts:
    env = environment or SnowflakeEnvironment()
    artifacts = {
        "snowflake.capabilities.json": _capability_summary(plan=plan, planning=planning, environment=env),
        "snowflake.planning.md": _planning_markdown(plan=plan, planning=planning, contract=contract, environment=env),
    }
    if contract is not None:
        artifacts.update(
            snowflake_publish_artifacts(
                contract=contract,
                raw_contract=raw_contract,
                environment=env,
                planning=planning,
            )
        )
    artifacts["snowflake.publish_manifest.json"] = _publish_manifest(
        plan=plan,
        planning=planning,
        artifacts=artifacts,
    )
    return RenderedArtifacts(artifacts=artifacts)


def _capability_summary(
    *,
    plan: ExecutionPlan | None,
    planning: PlanningResult | None,
    environment: SnowflakeEnvironment,
) -> str:
    payload = {
        "adapter": "snowflake",
        "subtarget": plan.platform if plan else "snowflake_sql_warehouse",
        "planning_status": planning.status if planning else None,
        "evidence": {
            "database": environment.evidence_database,
            "schema": environment.evidence_schema,
            "store": "snowflake_audit_tables",
        },
        "runtime": {
            "execution_model": "library_runner",
            "warehouse": environment.warehouse,
            "role": environment.role,
            "artifact_uri": environment.artifact_uri,
        },
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def _planning_markdown(
    *,
    plan: ExecutionPlan | None,
    planning: PlanningResult | None,
    contract: SemanticContract | None,
    environment: SnowflakeEnvironment,
) -> str:
    lines = [
        "# Snowflake Planning Review",
        "",
        f"- status: `{planning.status if planning else 'UNKNOWN'}`",
        f"- target: `{contract.target.name if contract else 'UNKNOWN'}`",
        f"- write mode: `{contract.write.mode if contract else 'UNKNOWN'}`",
        f"- evidence: `{_evidence_name(environment)}`",
        "",
        "## Steps",
        "",
    ]
    if plan and plan.steps:
        lines.extend(f"- `{step.name}`: {step.intent}" for step in plan.steps)
    else:
        lines.append("- No executable plan was produced.")
    lines.extend(["", "## Warnings", ""])
    warnings = planning.warnings if planning else ()
    if warnings:
        lines.extend(f"- `{warning.code}`: {warning.message}" for warning in warnings)
    else:
        lines.append("- None.")
    lines.extend(["", "## Blockers", ""])
    blockers = planning.blockers if planning else ()
    if blockers:
        lines.extend(f"- `{blocker.code}`: {blocker.message}" for blocker in blockers)
    else:
        lines.append("- None.")
    return "\n".join(lines) + "\n"


def _publish_manifest(
    *,
    plan: ExecutionPlan | None,
    planning: PlanningResult | None,
    artifacts: dict[str, str],
) -> str:
    payload = {
        "adapter": "snowflake",
        "subtarget": plan.platform if plan else "snowflake_sql_warehouse",
        "planning_status": planning.status if planning else None,
        "artifact_summary": {
            "mode": "publish_bundle",
            "execution_model": "library_runner",
            "generated_ingestion_artifacts": False,
            "deployable": bool(planning and planning.status in {"SUPPORTED", "SUPPORTED_WITH_WARNINGS"}),
            "count": len(artifacts) + 1,
            "bytes": sum(len(body.encode("utf-8")) for body in artifacts.values()),
        },
        "artifacts": sorted(tuple(artifacts) + ("snowflake.publish_manifest.json",)),
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def _evidence_name(environment: SnowflakeEnvironment) -> str:
    database = environment.evidence_database or "CONTRACTFORGE"
    schema = environment.evidence_schema or "CF_EVIDENCE"
    return f"{database}.{schema}"
