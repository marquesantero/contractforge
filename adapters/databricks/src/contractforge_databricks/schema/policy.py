"""Databricks schema policy planning."""

from __future__ import annotations

from contractforge_core.schema import SchemaPolicyPlan
from contractforge_core.semantic import SemanticContract

DatabricksSchemaPolicyPlan = SchemaPolicyPlan


def plan_schema_policy(contract: SemanticContract) -> DatabricksSchemaPolicyPlan:
    policy = contract.write.schema_policy
    if policy == "strict":
        return DatabricksSchemaPolicyPlan(
            policy=policy,
            writer_options={},
            preflight_required=True,
            reason="Strict schema requires adapter preflight comparison before Delta write.",
        )
    if policy == "additive_only":
        return DatabricksSchemaPolicyPlan(
            policy=policy,
            writer_options={"mergeSchema": "true"},
            preflight_required=True,
            reason="Additive-only schema allows new nullable columns after preflight validation.",
        )
    return DatabricksSchemaPolicyPlan(
        policy=policy,
        writer_options={"mergeSchema": "true"},
        preflight_required=True,
        reason="Permissive schema can use Delta schema merge, but type widening still requires evidence.",
        warnings=("type widening must be recorded as schema-change evidence",),
    )
