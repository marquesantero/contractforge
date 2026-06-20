import pytest

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_databricks.lakeflow import (
    render_lakeflow_auto_cdc_artifact,
    render_lakeflow_auto_cdc_python,
)


def test_render_lakeflow_auto_cdc_python_for_scd2() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "connector", "connector": "postgres"},
            "target": {"catalog": "main", "schema": "silver", "table": "customers_history"},
            "mode": "scd2_historical",
            "merge_keys": ["customer_id"],
            "scd2_change_columns": ["name", "status"],
            "scd2_sequence_by": "updated_at",
            "scd2_apply_as_deletes": "operation = 'DELETE'",
        }
    )

    code = render_lakeflow_auto_cdc_python(
        contract,
        source_name="live.customers_cdc",
        keys=("customer_id",),
        sequence_by="updated_at",
        flow_name="customers_auto_cdc",
        ignore_null_updates=True,
        once=True,
    )

    assert "dp.create_auto_cdc_flow(" in code
    assert "target='main.silver.customers_history'" in code
    assert "stored_as_scd_type=2" in code
    assert "ignore_null_updates=True" in code
    assert "sequence_by='updated_at'" in code
    assert "track_history_column_list=['name', 'status']" in code
    assert "name='customers_auto_cdc'" in code
    assert "once=True" in code


def test_render_lakeflow_auto_cdc_python_uses_contract_keys_and_sequence_by() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.customers_cdc"},
            "target": {"catalog": "main", "schema": "silver", "table": "customers_history"},
            "mode": "scd2_historical",
            "merge_keys": ["customer_id"],
            "scd2_sequence_by": "updated_at",
        }
    )

    code = render_lakeflow_auto_cdc_python(contract, source_name="live.customers_cdc")

    assert "keys=['customer_id']" in code
    assert "sequence_by='updated_at'" in code


def test_render_lakeflow_auto_cdc_artifact_includes_compatibility() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders_cdc"},
            "target": {"catalog": "main", "schema": "silver", "table": "orders"},
            "mode": "scd1_upsert",
            "merge_keys": ["order_id"],
        }
    )

    artifact = render_lakeflow_auto_cdc_artifact(
        contract,
        source_name="live.orders_cdc",
        keys=("order_id",),
        sequence_by="event_ts",
        apply_as_truncates="operation = 'TRUNCATE'",
    )

    payload = artifact.as_dict()

    assert artifact.language == "python"
    assert artifact.source_kind == "change_feed"
    assert "apply_as_truncates=\"operation = 'TRUNCATE'\"" in artifact.code
    assert payload["compatibility"]["mapped_fields"]["target"] == "main.silver.orders"
    assert payload["compatibility"]["mapped_fields"]["apply_as_truncates"] == "operation = 'TRUNCATE'"


def test_render_lakeflow_auto_cdc_snapshot_flow_for_scd1() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.customers_snapshot"},
            "target": {"catalog": "main", "schema": "silver", "table": "customers"},
            "mode": "scd1_upsert",
            "merge_keys": ["customer_id"],
        }
    )

    code = render_lakeflow_auto_cdc_python(
        contract,
        source_kind="snapshot",
        source_name="live.customers_snapshot",
        keys=("customer_id",),
        flow_name="customers_snapshot_cdc",
    )

    assert "dp.create_auto_cdc_from_snapshot_flow(" in code
    assert "target='main.silver.customers'" in code
    assert "source='live.customers_snapshot'" in code
    assert "stored_as_scd_type=1" in code
    assert "name='customers_snapshot_cdc'" in code


def test_lakeflow_snapshot_rejects_cdc_delete_predicate() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.customers_snapshot"},
            "target": {"table": "customers_history"},
            "mode": "scd2_historical",
            "merge_keys": ["customer_id"],
            "scd2_apply_as_deletes": "operation = 'DELETE'",
        }
    )

    with pytest.raises(ValueError, match="does not use CDC delete predicates"):
        render_lakeflow_auto_cdc_python(
            contract,
            source_kind="snapshot",
            source_name="live.customers_snapshot",
            keys=("customer_id",),
        )


def test_lakeflow_apply_as_truncates_rejected_for_scd2() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.customers_cdc"},
            "target": {"table": "customers_history"},
            "mode": "scd2_historical",
            "merge_keys": ["customer_id"],
        }
    )

    with pytest.raises(ValueError, match="apply_as_truncates"):
        render_lakeflow_auto_cdc_python(
            contract,
            source_name="live.customers_cdc",
            keys=("customer_id",),
            sequence_by="updated_at",
            apply_as_truncates="operation = 'TRUNCATE'",
        )


def test_render_lakeflow_auto_cdc_python_rejects_non_cdc_mode() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "connector", "connector": "postgres"},
            "target": {"table": "orders"},
            "mode": "scd0_append",
        }
    )

    with pytest.raises(ValueError, match="does not map directly"):
        render_lakeflow_auto_cdc_python(contract, source_name="live.orders", keys=("order_id",))
