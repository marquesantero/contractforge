"""AWS Glue Data Quality DQDL ruleset rendering."""

from __future__ import annotations

from contractforge_aws import render_aws_contract, render_aws_quality_dqdl
from contractforge_aws.rendering import unmapped_quality_rules
from contractforge_core.contracts import semantic_contract_from_mapping


def _contract(quality_rules: dict) -> dict:
    return {
        "source": {"type": "parquet", "path": "s3://landing/orders"},
        "target": {"catalog": "lake", "schema": "bronze", "table": "orders"},
        "mode": "scd0_append",
        "quality_rules": quality_rules,
    }


def test_dqdl_maps_portable_rules() -> None:
    dqdl = render_aws_quality_dqdl(
        _contract(
            {
                "required_columns": ["order_id", "customer_id"],
                "not_null": ["order_id"],
                "unique_key": ["order_id"],
                "min_rows": 1,
                "accepted_values": {"status": ["A", "B", "C"]},
                "max_null_ratio": {"email": 0.05},
            }
        )
    )

    assert dqdl.startswith("Rules = [")
    assert 'ColumnExists "order_id"' in dqdl
    assert 'ColumnExists "customer_id"' in dqdl
    assert 'IsComplete "order_id"' in dqdl
    assert 'IsUnique "order_id"' in dqdl
    assert "RowCount >= 1" in dqdl
    assert 'ColumnValues "status" in ["A", "B", "C"]' in dqdl
    assert 'Completeness "email" >= 0.95' in dqdl
    assert dqdl.rstrip().endswith("]")


def test_dqdl_composite_unique_key_uses_primary_key() -> None:
    dqdl = render_aws_quality_dqdl(_contract({"unique_key": ["order_id", "line_id"]}))
    assert 'IsPrimaryKey "order_id" "line_id"' in dqdl


def test_dqdl_accepted_values_numbers_are_unquoted() -> None:
    dqdl = render_aws_quality_dqdl(_contract({"accepted_values": {"grade": [1, 2, 3]}}))
    assert 'ColumnValues "grade" in [1, 2, 3]' in dqdl


def test_dqdl_expression_rule_is_unmapped() -> None:
    contract = semantic_contract_from_mapping(
        _contract(
            {
                "required_columns": ["order_id"],
                "expressions": [{"name": "amount_positive", "expression": "amount > 0", "severity": "quarantine"}],
            }
        )
    )

    assert "amount_positive" in unmapped_quality_rules(contract)
    dqdl = render_aws_quality_dqdl(
        _contract(
            {
                "required_columns": ["order_id"],
                "expressions": [{"name": "amount_positive", "expression": "amount > 0"}],
            }
        )
    )
    assert "amount_positive" not in dqdl
    assert 'ColumnExists "order_id"' in dqdl


def test_dqdl_empty_without_quality_rules() -> None:
    assert render_aws_quality_dqdl(
        {
            "source": {"type": "parquet", "path": "s3://landing/orders"},
            "target": {"catalog": "lake", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
        }
    ) == ""


def test_dqdl_artifact_is_published_in_rendered_artifacts() -> None:
    artifacts = render_aws_contract(_contract({"required_columns": ["order_id"], "unique_key": ["order_id"]}))

    assert "lake_bronze_orders.quality.dqdl" in artifacts.artifacts
    dqdl = artifacts.artifacts["lake_bronze_orders.quality.dqdl"]
    assert 'ColumnExists "order_id"' in dqdl


def test_dqdl_artifact_absent_without_quality_rules() -> None:
    artifacts = render_aws_contract(
        {
            "source": {"type": "parquet", "path": "s3://landing/orders"},
            "target": {"catalog": "lake", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
        }
    )

    assert "lake_bronze_orders.quality.dqdl" not in artifacts.artifacts
