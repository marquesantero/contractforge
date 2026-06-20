import pytest

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_databricks.preparation.hashing import HASH_DELIMITER, HASH_NULL_SENTINEL, render_row_hash_expression
from contractforge_databricks.preparation.staging import (
    scd2_stage_spec_from_contract,
    snapshot_stage_spec_from_contract,
)


def test_render_row_hash_expression() -> None:
    expression = render_row_hash_expression(("id", "amount", "updated_at"), exclude=("updated_at",))

    assert expression == (
        f"sha2(concat_ws('{HASH_DELIMITER}', coalesce(cast(`id` as string), "
        f"'{HASH_NULL_SENTINEL}'), coalesce(cast(`amount` as string), '{HASH_NULL_SENTINEL}')), 256)"
    )


def test_render_row_hash_expression_rejects_empty_selection() -> None:
    with pytest.raises(ValueError, match="at least one"):
        render_row_hash_expression(("id",), exclude=("id",))


def test_scd2_stage_spec_from_contract() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "connector", "connector": "postgres"},
            "target": {"table": "orders_history"},
            "mode": "scd2_historical",
            "merge_keys": ["order_id"],
            "scd2_change_columns": ["amount", "status"],
            "scd2_sequence_by": "updated_at",
        }
    )

    spec = scd2_stage_spec_from_contract(contract, source_columns=("order_id", "amount", "status", "updated_at"))

    assert spec.merge_keys == ("order_id",)
    assert spec.change_columns == ("amount", "status")
    assert spec.sequence_by == "updated_at"
    assert "row_hash" in spec.insert_columns


def test_snapshot_stage_spec_from_contract() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "connector", "connector": "postgres"},
            "target": {"table": "orders_snapshot"},
            "mode": "snapshot_soft_delete",
            "merge_keys": ["order_id"],
        }
    )

    spec = snapshot_stage_spec_from_contract(contract, source_columns=("order_id", "amount"))

    assert spec.source_columns == ("order_id", "amount", "is_active", "deleted_at", "row_hash")
