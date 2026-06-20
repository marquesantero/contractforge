import pytest

from contractforge_core.config import MAX_INLINE_ACCEPTED_VALUES
from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_databricks.quality import render_quality_check_sql


def test_render_quality_check_sql_for_portable_rules() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "connector", "connector": "postgres"},
            "target": {"catalog": "main", "schema": "silver", "table": "orders"},
            "mode": "scd0_append",
            "quality_rules": {
                "required_columns": ["order_id", "status"],
                "not_null": ["order_id"],
                "unique_key": ["order_id"],
                "accepted_values": {"status": ["open", "closed"]},
                "min_rows": 1,
                "max_null_ratio": {"status": 0.25},
                "expressions": [
                    {
                        "name": "positive_amount",
                        "expression": "amount > 0",
                        "severity": "warn",
                        "message": "amount should be positive",
                    }
                ],
            },
        }
    )

    sql = render_quality_check_sql(contract, source_view="tmp.orders_prepared")

    assert "quality: required_columns" in sql
    assert "WHERE `order_id` IS NULL" in sql
    assert "GROUP BY `order_id` HAVING count(*) > 1" in sql
    assert "`status` NOT IN ('open', 'closed')" in sql
    assert "count(*) >= 1" in sql
    assert "`status` IS NULL" in sql
    assert "WHERE NOT (amount > 0) OR (amount > 0) IS NULL" in sql


def test_render_quality_check_sql_without_rules() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "connector", "connector": "postgres"},
            "target": {"table": "orders"},
            "mode": "scd0_append",
        }
    )

    assert render_quality_check_sql(contract) == "-- No quality rules declared.\n"


def test_render_required_columns_sql_for_qualified_target() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "connector", "connector": "postgres"},
            "target": {"catalog": "main", "schema": "silver", "table": "orders"},
            "quality_rules": {"required_columns": ["order_id", "status"]},
        }
    )

    sql = render_quality_check_sql(contract)

    assert "system.information_schema.columns" in sql
    assert "table_catalog = 'main'" in sql
    assert "table_schema = 'silver'" in sql
    assert "table_name = 'orders'" in sql


def test_render_quality_check_sql_rejects_large_inline_accepted_values() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"catalog": "main", "schema": "silver", "table": "orders"},
            "quality_rules": {"accepted_values": {"status": list(range(MAX_INLINE_ACCEPTED_VALUES + 1))}},
        }
    )

    with pytest.raises(ValueError, match="accepted_values.status"):
        render_quality_check_sql(contract)
