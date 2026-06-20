"""Databricks artifact naming helpers."""

from __future__ import annotations

from contractforge_core.planner import ExecutionPlan
from contractforge_core.semantic import SemanticContract
from contractforge_core.naming import derive_names, naming_config_from_mapping


def target_full_name(contract: SemanticContract) -> str:
    if contract.target.namespace:
        return f"{contract.target.namespace}.{contract.target.name}"
    return contract.target.name


def artifact_prefix(contract: SemanticContract) -> str:
    if contract.naming:
        return derive_names(
            target_table=contract.target.name,
            layer=contract.target.layer,
            domain=contract.target.domain,
            config=naming_config_from_mapping(contract.naming.raw),
        ).contract_basename
    namespace = contract.target.namespace.replace(".", "_") if contract.target.namespace else contract.target.layer
    return f"{namespace}_{contract.target.name}"


def bundle_name(contract: SemanticContract) -> str:
    return derive_names(
        target_table=contract.target.name,
        layer=contract.target.layer,
        domain=contract.target.domain,
        config=naming_config_from_mapping(contract.naming.raw if contract.naming else None),
    ).bundle_name


def job_name(contract: SemanticContract) -> str:
    return derive_names(
        target_table=contract.target.name,
        layer=contract.target.layer,
        domain=contract.target.domain,
        config=naming_config_from_mapping(contract.naming.raw if contract.naming else None),
    ).job_name


def task_key(contract: SemanticContract) -> str:
    return derive_names(
        target_table=contract.target.name,
        layer=contract.target.layer,
        domain=contract.target.domain,
        config=naming_config_from_mapping(contract.naming.raw if contract.naming else None),
    ).task_key


def plan_title(plan: ExecutionPlan) -> str:
    return f"ContractForge Databricks plan for {plan.platform}"
