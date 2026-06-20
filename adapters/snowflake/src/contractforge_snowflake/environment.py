"""Snowflake adapter environment binding."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SnowflakeEnvironment:
    """Adapter-owned interpretation of the core environment contract."""

    evidence_database: str | None = None
    evidence_schema: str | None = None
    evidence_create_database: bool = True
    evidence_create_schema: bool = True
    evidence_validate_only_ddl: bool = False
    artifact_uri: str | None = None
    warehouse: str | None = None
    role: str | None = None
    runtime_database: str | None = None
    runtime_schema: str | None = None
    runtime_wheel_uri: str | None = None
    runner_procedure: str | None = None
    task_database: str | None = None
    task_schema: str | None = None

    @classmethod
    def from_contract(cls, environment: dict[str, Any] | None = None) -> "SnowflakeEnvironment":
        if not environment:
            return cls()
        evidence = environment.get("evidence") if isinstance(environment.get("evidence"), dict) else {}
        artifacts = environment.get("artifacts") if isinstance(environment.get("artifacts"), dict) else {}
        parameters = environment.get("parameters") if isinstance(environment.get("parameters"), dict) else {}
        snowflake = parameters.get("snowflake") if isinstance(parameters.get("snowflake"), dict) else {}
        return cls(
            evidence_database=evidence.get("database") or evidence.get("catalog"),
            evidence_schema=evidence.get("schema"),
            evidence_create_database=_bool(evidence.get("create_database"), default=True),
            evidence_create_schema=_bool(evidence.get("create_schema"), default=True),
            evidence_validate_only_ddl=_bool(evidence.get("validate_only_ddl"), default=False),
            artifact_uri=artifacts.get("uri"),
            warehouse=snowflake.get("warehouse"),
            role=snowflake.get("role"),
            runtime_database=snowflake.get("runtime_database"),
            runtime_schema=snowflake.get("runtime_schema"),
            runtime_wheel_uri=snowflake.get("runtime_wheel_uri"),
            runner_procedure=snowflake.get("runner_procedure"),
            task_database=snowflake.get("task_database"),
            task_schema=snowflake.get("task_schema"),
        )


def _bool(value: object, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)
