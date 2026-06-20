"""High-level Databricks adapter API."""

from __future__ import annotations

from typing import Any

from contractforge_core.adapters import RenderedArtifacts
from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_core.planner import PlanningResult
from contractforge_databricks.adapter import DatabricksAdapter
from contractforge_databricks.contract_extensions import normalize_databricks_contract


def plan_databricks_contract(
    contract: dict[str, Any],
    *,
    target_table: str | None = None,
    runtime_type: str | None = None,
    spark_version: str | None = None,
    spark_conf: dict[str, str] | None = None,
    environment: dict[str, Any] | None = None,
) -> PlanningResult:
    semantic = semantic_contract_from_mapping(normalize_databricks_contract(contract))
    adapter = DatabricksAdapter.from_evidence(
        target_table=target_table or _target_table(contract),
        runtime_type=runtime_type,
        spark_version=spark_version,
        spark_conf=spark_conf,
        environment=environment,
    )
    return adapter.plan(semantic)


def render_databricks_contract(
    contract: dict[str, Any],
    *,
    target_table: str | None = None,
    runtime_type: str | None = None,
    spark_version: str | None = None,
    spark_conf: dict[str, str] | None = None,
    environment: dict[str, Any] | None = None,
) -> RenderedArtifacts:
    semantic = semantic_contract_from_mapping(normalize_databricks_contract(contract))
    adapter = DatabricksAdapter.from_evidence(
        target_table=target_table or _target_table(contract),
        runtime_type=runtime_type,
        spark_version=spark_version,
        spark_conf=spark_conf,
        environment=environment,
    )
    return adapter.render_contract(semantic)


def _target_table(contract: dict[str, Any]) -> str | None:
    target = contract.get("target")
    if isinstance(target, dict):
        parts = [target.get("catalog"), target.get("schema"), target.get("table")]
        if all(parts):
            return ".".join(str(part) for part in parts)
    table = contract.get("target_table")
    catalog = contract.get("catalog")
    schema = contract.get("target_schema")
    if table and catalog and schema:
        return f"{catalog}.{schema}.{table}"
    return str(table) if table else None
