"""BigQuery naming helpers for rendered GCP artifacts."""

from __future__ import annotations

from contractforge_core.planner import ExecutionPlan
from contractforge_core.semantic import SemanticContract
from contractforge_gcp.capabilities import GCP_SUBTARGET_BIGQUERY
from contractforge_gcp.environment import GCPEnvironment


def artifact_prefix(contract: SemanticContract | None, plan: ExecutionPlan | None) -> str:
    if contract is None:
        return (plan.platform if plan else GCP_SUBTARGET_BIGQUERY).replace(".", "_")
    namespace = (contract.target.namespace or "default").replace(".", "_")
    return f"{namespace}_{contract.target.name}"


def target_project(contract: SemanticContract, env: GCPEnvironment) -> str | None:
    if contract.target.namespace and "." in contract.target.namespace:
        return contract.target.namespace.split(".", 1)[0]
    return env.project_id


def target_dataset(contract: SemanticContract, env: GCPEnvironment) -> str:
    if contract.target.namespace:
        return contract.target.namespace.split(".")[-1]
    return env.dataset or "contractforge"


def target_table_id(contract: SemanticContract, env: GCPEnvironment) -> str:
    project = target_project(contract, env)
    dataset = target_dataset(contract, env)
    return f"{project + '.' if project else ''}{dataset}.{contract.target.name}"


def target_table(contract: SemanticContract, env: GCPEnvironment) -> str:
    return f"`{target_table_id(contract, env)}`"


def staging_table(contract: SemanticContract, env: GCPEnvironment) -> str:
    project = target_project(contract, env)
    dataset = target_dataset(contract, env)
    return f"`{project + '.' if project else ''}{dataset}._staging_{contract.target.name}`"


def evidence_dataset(contract: SemanticContract | None, env: GCPEnvironment) -> str:
    if env.evidence_dataset:
        return env.evidence_dataset
    if contract is not None:
        return f"{target_dataset(contract, env)}_ops"
    return env.dataset or "contractforge_ops"


def table_prefix(project_id: str | None, dataset: str) -> str:
    return f"{project_id}.{dataset}" if project_id else dataset


def quote_table_ref(ref: str, env: GCPEnvironment) -> str:
    if ref.startswith("`") and ref.endswith("`"):
        return ref
    parts = ref.split(".")
    if len(parts) == 1:
        return f"`{env.project_id + '.' if env.project_id else ''}{env.dataset or 'contractforge'}.{parts[0]}`"
    return f"`{ref}`"


def identifier(value: str) -> str:
    return f"`{value.replace('`', '')}`"


def public_mode(mode: str) -> str:
    aliases = {
        "scd0_append": "append",
        "scd0_overwrite": "overwrite",
        "scd1_upsert": "upsert",
        "scd1_hash_diff": "hash_diff_upsert",
        "scd2_historical": "historical",
        "snapshot_soft_delete": "snapshot_reconcile_soft_delete",
    }
    return aliases.get(mode, mode)
