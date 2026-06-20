"""Runtime write-engine evidence for Databricks ingestion."""

from __future__ import annotations

from typing import Any

from contractforge_core.semantic import SemanticContract
from contractforge_databricks.capabilities import evaluate_databricks_capabilities
from contractforge_databricks.contract_extensions import databricks_extensions
from contractforge_databricks.write_modes import choose_write_strategy


def write_strategy_evidence(contract: SemanticContract, target: str, runtime: dict[str, Any]) -> dict[str, str]:
    capabilities = evaluate_databricks_capabilities(
        target_table=target,
        runtime_type=str(runtime.get("runtime_type") or "serverless"),
        spark_version=str(runtime["spark_version"]) if runtime.get("spark_version") else None,
    )
    strategy = choose_write_strategy(contract, capabilities)
    return {
        "write_engine_requested": _requested_engine(contract),
        "write_engine_selected": strategy.engine,
        "write_engine_status": strategy.kind,
        "write_engine_reason": strategy.reason,
        "write_engine_fallback_policy": _fallback_policy(contract),
    }


def _requested_engine(contract: SemanticContract) -> str:
    write_engine = databricks_extensions(contract).get("write_engine")
    if isinstance(write_engine, dict):
        return str(write_engine.get("requested") or write_engine.get("engine") or "auto")
    return str(write_engine or "auto")


def _fallback_policy(contract: SemanticContract) -> str:
    write_engine = databricks_extensions(contract).get("write_engine")
    if isinstance(write_engine, dict):
        return str(write_engine.get("fallback_policy") or "fail")
    return "fail"
