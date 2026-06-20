from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_databricks.lakeflow import evaluate_lakeflow_compatibility


def test_lakeflow_scd1_requires_keys_and_source_name() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "connector", "connector": "postgres"},
            "target": {"table": "orders"},
            "mode": "scd1_upsert",
        }
    )

    compatibility = evaluate_lakeflow_compatibility(contract)

    assert compatibility.status == "unsupported"
    assert compatibility.scd_type == 1
    assert set(compatibility.required_fields) == {"source_name", "keys"}


def test_lakeflow_scd2_can_be_compatible_with_required_fields() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "connector", "connector": "postgres"},
            "target": {"table": "orders_history"},
            "mode": "scd2_historical",
        }
    )

    compatibility = evaluate_lakeflow_compatibility(
        contract,
        source_name="live.orders_cdc",
        keys=("order_id",),
        sequence_by="updated_at",
    )

    assert compatibility.status == "compatible"
    assert compatibility.scd_type == 2
    assert compatibility.source_kind == "change_feed"
    assert compatibility.target_table == "orders_history"
    assert compatibility.mapped_fields == {
        "target": "orders_history",
        "source": "live.orders_cdc",
        "keys": ["order_id"],
        "sequence_by": "updated_at",
        "stored_as_scd_type": 2,
    }
    assert compatibility.warnings == (
        "SCD2 without scd2_change_columns maps to Lakeflow's default of tracking all output columns.",
    )
    assert compatibility.as_dict()["supported"] is True


def test_lakeflow_uses_core_write_keys_and_sequence_by_by_default() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders_cdc"},
            "target": {"table": "orders_history"},
            "mode": "scd2_historical",
            "merge_keys": ["order_id"],
            "scd2_sequence_by": "updated_at",
        }
    )

    compatibility = evaluate_lakeflow_compatibility(contract, source_name="live.orders_cdc")

    assert compatibility.status == "compatible"
    assert compatibility.mapped_fields["keys"] == ["order_id"]
    assert compatibility.mapped_fields["sequence_by"] == "updated_at"


def test_lakeflow_does_not_claim_snapshot_soft_delete_equivalence() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "connector", "connector": "postgres"},
            "target": {"table": "orders"},
            "mode": "snapshot_soft_delete",
        }
    )

    compatibility = evaluate_lakeflow_compatibility(
        contract,
        source_name="live.orders_snapshot",
        keys=("order_id",),
    )

    assert compatibility.status == "unsupported"
    assert compatibility.unsupported_fields == ("mode",)


def test_lakeflow_marks_shape_and_transform_as_translation_required() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders_cdc"},
            "target": {"table": "orders_history"},
            "mode": "scd2_historical",
            "merge_keys": ["order_id"],
            "scd2_sequence_by": "updated_at",
            "shape": {"flatten": True},
            "transform": {"derive": {"loaded_at": "current_timestamp()"}},
        }
    )

    compatibility = evaluate_lakeflow_compatibility(
        contract,
        source_name="live.orders_cdc_prepared",
        keys=("order_id",),
        sequence_by="updated_at",
    )

    assert compatibility.status == "requires_translation"
    assert set(compatibility.translation_required) == {"shape", "transform"}


def test_lakeflow_marks_runtime_preparation_fields_as_translation_required() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders_cdc"},
            "target": {"table": "orders_history"},
            "mode": "scd2_historical",
            "merge_keys": ["order_id"],
            "scd2_sequence_by": "updated_at",
            "select_columns": ["order_id", "status", "updated_at"],
            "column_mapping": {"status": "order_status"},
            "filter_expression": "is_valid = true",
            "watermark_columns": ["updated_at"],
        }
    )

    compatibility = evaluate_lakeflow_compatibility(
        contract,
        source_name="live.orders_cdc_prepared",
        keys=("order_id",),
        sequence_by="updated_at",
    )

    assert compatibility.status == "requires_translation"
    assert set(compatibility.translation_required) == {
        "column_mapping",
        "filter_expression",
        "select_columns",
        "watermark_columns",
    }
    assert any("Watermark filtering/state" in reason for reason in compatibility.reasons)
