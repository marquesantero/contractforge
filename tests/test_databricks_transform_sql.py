from __future__ import annotations

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_databricks.transforms import render_transform_sql


def test_render_transform_sql_for_cast_standardize_and_derive() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"table": "orders"},
            "transform": {
                "cast": {"amount": "double"},
                "standardize": {"email": {"trim": True, "lower": True, "empty_as_null": True}},
                "derive": {"order_date": "to_date(updated_at)"},
            },
        }
    )

    sql = render_transform_sql(contract, source_view="tmp.orders_raw", output_view="tmp.orders_prepared")

    assert "CREATE OR REPLACE TEMP VIEW `tmp`.`orders_prepared` AS" in sql
    assert "CAST(`amount` AS double) AS `amount`" in sql
    assert "nullif(lower(trim(`email`)), '') AS `email`" in sql
    assert "to_date(updated_at) AS `order_date`" in sql
    assert "FROM `tmp`.`orders_raw`" in sql


def test_render_transform_sql_for_composite_keys() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"table": "orders"},
            "transform": {"composite_keys": {"order_line_key": ["order_id", "line_id"]}},
        }
    )

    sql = render_transform_sql(contract, source_view="tmp.orders_raw", output_view="tmp.orders_prepared")

    assert "concat_ws('|', coalesce(CAST(`order_id` AS STRING), ''), coalesce(CAST(`line_id` AS STRING), '')) AS `order_line_key`" in sql


def test_render_transform_sql_for_structured_deduplicate() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"table": "orders"},
            "transform": {
                "deduplicate": {
                    "keys": ["order_id", "tenant_id"],
                    "order_by": [
                        {"column": "updated_at", "direction": "desc", "nulls": "last"},
                        {"column": "sequence", "direction": "desc"},
                    ],
                }
            },
        }
    )

    sql = render_transform_sql(contract)

    assert "WITH transformed AS" in sql
    assert "row_number() OVER (PARTITION BY `order_id`, `tenant_id` ORDER BY `updated_at` DESC NULLS LAST, `sequence` DESC)" in sql
    assert "WHERE __cf_row_number = 1" in sql


def test_render_transform_sql_without_transform() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"table": "orders"},
        }
    )

    assert render_transform_sql(contract) == "-- No transform declared.\n"
