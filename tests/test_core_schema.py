import pytest

from contractforge_core.schema import SchemaPolicyPlan, compare_schema, is_type_widening, validate_schema_diff


def test_core_compare_schema_detects_changes() -> None:
    diff = compare_schema(
        {"id": "bigint", "name": "string"},
        {
            "id": "int",
            "old_col": "string",
            "__run_id": "string",
            "row_hash": "binary",
            "ingestion_date": "date",
            "source_system": "string",
            "ingestion_sequence": "bigint",
        },
        allow_type_widening=True,
    )

    assert diff.added_columns == ("name",)
    assert diff.removed_columns == ("old_col",)
    assert diff.type_changes[0].as_dict() == {
        "column": "id",
        "source": "bigint",
        "target": "int",
        "allowed": True,
        "change": "type_widening",
    }


def test_core_validate_schema_diff_policies() -> None:
    strict_diff = compare_schema({"id": "bigint", "name": "string"}, {"id": "bigint"})
    with pytest.raises(ValueError, match="strict"):
        validate_schema_diff(strict_diff, "strict")

    additive_diff = compare_schema({"id": "bigint", "name": "string"}, {"id": "bigint"})
    assert validate_schema_diff(additive_diff, "additive_only") is additive_diff


def test_core_type_widening_rules_are_portable() -> None:
    assert is_type_widening("bigint", "int")
    assert is_type_widening("double", "float")
    assert is_type_widening("timestamp", "date")
    assert is_type_widening("decimal(12,2)", "decimal(10,2)")


def test_core_schema_policy_plan_serializes() -> None:
    plan = SchemaPolicyPlan(
        policy="additive_only",
        writer_options={"mergeSchema": "true"},
        preflight_required=True,
        reason="adapter preflight",
        warnings=("review type widening",),
    )

    assert plan.as_dict() == {
        "policy": "additive_only",
        "writer_options": {"mergeSchema": "true"},
        "preflight_required": True,
        "reason": "adapter preflight",
        "warnings": ["review type widening"],
    }
