import pytest

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_core.preparation import (
    HASH_DELIMITER,
    HASH_NULL_SENTINEL,
    hash_diff_stage_spec_from_contract,
    resolved_hash_input_columns,
    scd2_stage_spec_from_contract,
    snapshot_stage_spec_from_contract,
)


def test_core_hash_staging_constants_match_contractforge_algorithm() -> None:
    assert HASH_DELIMITER == "\u001f"
    assert HASH_NULL_SENTINEL == "\u0000"


def test_core_hash_diff_stage_explicit_hash_keys_excludes_generated_columns() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "connector", "connector": "postgres"},
            "target": {"table": "orders_hash"},
            "mode": "scd1_hash_diff",
            "merge_keys": ["order_id"],
            "hash_keys": ["amount", "source_loaded_at_utc", "order_band"],
            "hash_exclude_columns": ["updated_at"],
            "transform": {"derive": {"order_band": "CASE WHEN amount > 100 THEN 'large' ELSE 'small' END"}},
        }
    )

    columns = ("order_id", "amount", "updated_at", "source_loaded_at_utc", "order_band")
    spec = hash_diff_stage_spec_from_contract(contract, source_columns=columns)

    assert spec.hash_strategy == "explicit"
    assert spec.hash_keys == ("amount", "source_loaded_at_utc", "order_band")
    assert resolved_hash_input_columns(contract, source_columns=columns) == ("amount",)


def test_core_hash_diff_stage_all_columns_except_strategy() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "connector", "connector": "postgres"},
            "target": {"table": "orders_hash"},
            "mode": "scd1_hash_diff",
            "merge_keys": ["order_id"],
            "hash_strategy": "all_columns_except",
            "hash_exclude_columns": ["updated_at"],
        }
    )

    columns = ("order_id", "amount", "status", "updated_at", "source_loaded_at_utc")
    spec = hash_diff_stage_spec_from_contract(contract, source_columns=columns)

    assert spec.hash_strategy == "all_columns_except"
    assert spec.hash_keys == columns
    assert resolved_hash_input_columns(contract, source_columns=columns) == ("amount", "status")


def test_core_scd2_stage_spec_from_contract() -> None:
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


def test_core_scd2_stage_spec_preserves_effective_from_column() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "connector", "connector": "postgres"},
            "target": {"table": "orders_history"},
            "mode": "scd2_historical",
            "merge_keys": ["order_id"],
            "scd2_effective_from_column": "source_valid_from",
        }
    )

    spec = scd2_stage_spec_from_contract(contract, source_columns=("order_id", "source_valid_from"))

    assert spec.effective_from_column == "source_valid_from"


def test_core_scd2_stage_spec_preserves_late_arriving_policy() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "connector", "connector": "postgres"},
            "target": {"table": "orders_history"},
            "mode": "scd2_historical",
            "merge_keys": ["order_id"],
            "scd2_sequence_by": "event_ts",
            "scd2_late_arriving_policy": "reject",
        }
    )

    spec = scd2_stage_spec_from_contract(contract, source_columns=("order_id", "event_ts"))

    assert spec.late_arriving_policy == "reject"


def test_core_scd2_stage_spec_excludes_hash_excluded_columns_from_default_change_hash() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "connector", "connector": "postgres"},
            "target": {"table": "orders_history"},
            "mode": "scd2_historical",
            "merge_keys": ["order_id"],
            "hash_exclude_columns": ["updated_at", "ingestion_ts_utc"],
        }
    )

    spec = scd2_stage_spec_from_contract(
        contract,
        source_columns=("order_id", "amount", "updated_at", "ingestion_ts_utc"),
    )

    assert spec.change_columns == ("amount",)


def test_core_scd2_stage_spec_rejects_wrong_mode() -> None:
    contract = semantic_contract_from_mapping(
        {"source": {"type": "connector", "connector": "postgres"}, "target": {"table": "orders"}, "mode": "scd0_append"}
    )

    with pytest.raises(ValueError, match="scd2_historical"):
        scd2_stage_spec_from_contract(contract, source_columns=("order_id",))


def test_core_snapshot_stage_spec_from_contract() -> None:
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
