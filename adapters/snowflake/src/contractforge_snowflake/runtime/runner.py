"""Stable Snowflake runtime runner entry point."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_core.security.redaction import redact_text
from contractforge_snowflake.contract_extensions import snowflake_extensions
from contractforge_snowflake.environment import SnowflakeEnvironment
from contractforge_snowflake.evidence import bootstrap_evidence_tables, record_error_evidence, record_run_evidence
from contractforge_snowflake.api import plan_snowflake_contract
from contractforge_snowflake.naming import snowflake_target_name
from contractforge_snowflake.runtime.artifacts import load_json_artifact
from contractforge_snowflake.runtime.execution import execute_snowflake_contract
from contractforge_snowflake.state import acquire_snowflake_lock, find_idempotent_run, record_snowflake_state, release_snowflake_lock


def run_snowflake_contract(
    *,
    contract_uri: str,
    environment_uri: str | None = None,
    session: Any | None = None,
    dry_run: bool = False,
    run_id: str | None = None,
    set_query_tag: bool = True,
) -> dict[str, Any]:
    """Run a published ContractForge contract through the Snowflake adapter.

    The entry point targets the stable Snowflake library-runner model. Published
    artifacts are configuration; ingestion logic stays in this package.
    """

    contract = load_json_artifact(contract_uri, session=session)
    environment = load_json_artifact(environment_uri, session=session) if environment_uri else None
    planning = plan_snowflake_contract(contract, environment=environment)
    result = {
        "status": "DRY_RUN" if dry_run else "PLANNED",
        "planning_status": planning.status,
        "warnings": [warning.code for warning in planning.warnings],
        "blockers": [blocker.code for blocker in planning.blockers],
    }
    if dry_run:
        return result
    if planning.status not in {"SUPPORTED", "SUPPORTED_WITH_WARNINGS"}:
        raise RuntimeError(f"Snowflake contract is not executable with planning status {planning.status}")
    if session is None:
        raise ValueError("Snowflake runtime execution requires a Snowflake session")
    run_id = run_id or str(uuid4())
    semantic = semantic_contract_from_mapping(contract)
    env = SnowflakeEnvironment.from_contract(environment)
    bootstrap = bootstrap_evidence_tables(session, env)
    idempotency = find_idempotent_run(session=session, environment=env, contract=semantic)
    idempotency_commands = (idempotency.command,) if idempotency.command else ()
    if idempotency.run_id:
        policy = _idempotency_policy(semantic)
        if policy == "fail_if_success":
            raise ValueError(f"idempotency_key={_idempotency_key(semantic)!r} already succeeded")
        metrics = {
            "idempotency_key": _idempotency_key(semantic),
            "idempotency_policy": policy,
            "skip_reason": "idempotency_key_already_succeeded",
            "skipped_by_run_id": idempotency.run_id,
            "metrics_source": "snowflake_idempotency",
            "quality_status": "SKIPPED",
        }
        run_evidence = record_run_evidence(
            session,
            environment=env,
            contract=semantic,
            run_id=run_id,
            status="SKIPPED",
            command_count=len(bootstrap.commands) + len(idempotency_commands),
            metrics=metrics,
        )
        return {
            **result,
            "status": "SKIPPED",
            "run_id": run_id,
            "target": snowflake_target_name(semantic),
            "write_mode": semantic.write.mode,
            "commands": list((*bootstrap.commands, *idempotency_commands, *run_evidence.commands)),
            "bootstrap_skips": list(bootstrap.skipped_commands),
            "metrics": metrics,
            "skip_reason": "idempotency_key_already_succeeded",
        }
    lock = _lock_options(semantic)
    target = snowflake_target_name(semantic)
    lock_commands: tuple[str, ...] = ()
    release_commands: tuple[str, ...] = ()
    try:
        if lock["enabled"]:
            lock_result = acquire_snowflake_lock(
                session=session,
                environment=env,
                target_table=target,
                run_id=run_id,
                owner=lock["owner"],
                ttl_minutes=lock["ttl_minutes"],
            )
            lock_commands = lock_result.commands
        executed = execute_snowflake_contract(
            contract,
            environment=env,
            run_id=run_id,
            session=session,
            set_query_tag=set_query_tag,
        )
    except Exception as exc:
        error_message = redact_text(str(exc))
        error_evidence = record_error_evidence(session, environment=env, contract=semantic, run_id=run_id, error=exc)
        state_evidence = record_snowflake_state(
            session=session,
            environment=env,
            contract=semantic,
            run_id=run_id,
            status="FAILED",
            source_sql=None,
            error_message=error_message,
        )
        run_evidence = record_run_evidence(
            session,
            environment=env,
            contract=semantic,
            run_id=run_id,
            status="FAILED",
            error_message=error_message,
            command_count=len(bootstrap.commands) + len(idempotency_commands) + len(lock_commands) + len(error_evidence.commands) + len(state_evidence.commands),
        )
        _attach_error_note(
            exc,
            f"ContractForge Snowflake run_id={run_id}; evidence_commands={len(error_evidence.commands) + len(run_evidence.commands)}",
        )
        raise
    finally:
        if lock_commands:
            release_result = release_snowflake_lock(session=session, environment=env, target_table=target, run_id=run_id)
            release_commands = release_result.commands
    run_evidence = record_run_evidence(
        session,
        environment=env,
        contract=semantic,
        run_id=run_id,
        status="SUCCESS",
        command_count=len(bootstrap.commands) + len(idempotency_commands) + len(lock_commands) + len(executed.commands) + len(release_commands),
        metrics=executed.metrics,
    )
    return {
        **result,
        "status": executed.status,
        "run_id": run_id,
        "target": executed.target,
        "write_mode": executed.write_mode,
        "commands": list((*bootstrap.commands, *idempotency_commands, *lock_commands, *executed.commands, *release_commands, *run_evidence.commands)),
        "bootstrap_skips": list(bootstrap.skipped_commands),
        "metrics": executed.metrics,
    }


def _attach_error_note(error: BaseException, note: str) -> None:
    add_note = getattr(error, "add_note", None)
    if callable(add_note):
        add_note(note)
        return
    setattr(error, "_contractforge_note", note)


def _idempotency_key(contract: Any) -> str | None:
    metadata = contract.operations.metadata or {}
    value = metadata.get("idempotency_key")
    return str(value) if value not in (None, "") else None


def _idempotency_policy(contract: Any) -> str:
    metadata = contract.operations.metadata or {}
    return str(metadata.get("idempotency_policy") or "always_run")


def _lock_options(contract: Any) -> dict[str, Any]:
    snowflake = snowflake_extensions(contract)
    return {
        "enabled": bool(snowflake.get("lock_enabled", False)),
        "owner": str(snowflake["lock_owner"]) if snowflake.get("lock_owner") not in (None, "") else None,
        "ttl_minutes": int(snowflake.get("lock_ttl_minutes") or 60),
    }
