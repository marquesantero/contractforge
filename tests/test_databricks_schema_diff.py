import pytest

from contractforge_databricks.schema import (
    compare_schema,
    is_type_widening,
    render_add_columns_sql,
    render_type_widening_sql,
    validate_schema_diff,
)


def test_compare_schema_detects_added_removed_and_type_changes() -> None:
    diff = compare_schema(
        {"id": "bigint", "name": "string", "amount": "double"},
        {
            "id": "int",
            "old_col": "string",
            "amount": "double",
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
    assert [change.as_dict() for change in diff.type_changes] == [
        {"column": "id", "source": "bigint", "target": "int", "allowed": True, "change": "type_widening"}
    ]


def test_validate_schema_diff_strict_blocks_any_difference() -> None:
    diff = compare_schema({"id": "bigint", "name": "string"}, {"id": "bigint"})

    with pytest.raises(ValueError, match="strict"):
        validate_schema_diff(diff, "strict")


def test_validate_schema_diff_additive_allows_added_columns() -> None:
    diff = compare_schema({"id": "bigint", "name": "string"}, {"id": "bigint"})

    assert validate_schema_diff(diff, "additive_only") is diff


def test_validate_schema_diff_permissive_blocks_destructive_type_change() -> None:
    diff = compare_schema({"id": "string"}, {"id": "bigint"})

    with pytest.raises(ValueError, match="permissive"):
        validate_schema_diff(diff, "permissive")


@pytest.mark.parametrize(
    ("source_type", "target_type"),
    [("bigint", "int"), ("BIGINT", "INT"), ("double", "float"), ("timestamp", "date"), ("decimal(12,2)", "decimal(10,2)")],
)
def test_is_type_widening(source_type: str, target_type: str) -> None:
    assert is_type_widening(source_type, target_type)


def test_render_schema_sync_sql() -> None:
    diff = compare_schema(
        {"id": "bigint", "name": "string"},
        {"id": "int"},
        allow_type_widening=True,
    )

    assert render_add_columns_sql(target_table="main.silver.orders", source_schema={"name": "string"}, diff=diff) == (
        "ALTER TABLE `main`.`silver`.`orders` ADD COLUMNS (`name` string)"
    )
    assert render_type_widening_sql(target_table="main.silver.orders", diff=diff) == (
        "ALTER TABLE `main`.`silver`.`orders` ALTER COLUMN `id` TYPE bigint;\n"
    )
