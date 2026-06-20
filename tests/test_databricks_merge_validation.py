import pytest

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_core.runtime import PreparedInput
from contractforge_databricks.runtime.merge_validation import (
    render_merge_key_duplicates_sql,
    render_merge_key_nulls_sql,
    validate_merge_source_safety,
)


def _contract():
    return semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"catalog": "main", "schema": "silver", "table": "orders"},
            "mode": "scd1_upsert",
            "merge_keys": ["order_id"],
        }
    )


def test_render_merge_key_safety_queries_quote_source_and_keys() -> None:
    assert render_merge_key_nulls_sql("prepared_orders", ("order_id",)) == (
        "SELECT count(*) AS all_keys_null_rows FROM `prepared_orders` WHERE `order_id` IS NULL"
    )
    assert render_merge_key_duplicates_sql("prepared_orders", ("order_id",)) == (
        "SELECT count(*) AS duplicate_key_groups, coalesce(sum(row_count), 0) AS duplicate_rows "
        "FROM (SELECT `order_id`, count(*) AS row_count FROM `prepared_orders` "
        "GROUP BY `order_id` HAVING count(*) > 1)"
    )


def test_validate_merge_source_safety_rejects_fully_null_merge_keys() -> None:
    def query_one(statement: str):
        return {"all_keys_null_rows": 3}

    with pytest.raises(ValueError, match="fully null merge_keys"):
        validate_merge_source_safety(
            contract=_contract(),
            prepared=PreparedInput(source_view="prepared_orders", source_columns=("order_id",), rows_read=3),
            query_one=query_one,
        )
