from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_databricks.schema import plan_schema_policy


def _contract(schema_policy: str):
    return semantic_contract_from_mapping(
        {
            "source": {"type": "connector", "connector": "postgres"},
            "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
            "schema_policy": schema_policy,
        }
    )


def test_strict_schema_policy_requires_preflight_without_merge_schema() -> None:
    plan = plan_schema_policy(_contract("strict"))

    assert plan.preflight_required is True
    assert plan.writer_options == {}
    assert "Strict schema" in plan.reason


def test_additive_schema_policy_enables_delta_merge_schema() -> None:
    plan = plan_schema_policy(_contract("additive_only"))

    assert plan.writer_options == {"mergeSchema": "true"}
    assert plan.preflight_required is True


def test_permissive_schema_policy_warns_about_type_widening_evidence() -> None:
    plan = plan_schema_policy(_contract("permissive"))

    assert plan.writer_options == {"mergeSchema": "true"}
    assert plan.warnings == ("type widening must be recorded as schema-change evidence",)
