from __future__ import annotations

from contractforge_core.watermark import encode_watermark_values
from contractforge_databricks.watermark import (
    render_select_watermark_candidate_sql,
    render_watermark_filter_predicate,
)


def test_render_simple_watermark_filter_predicate() -> None:
    watermark = encode_watermark_values(
        {"updated_at": "2026-01-01 00:00:00"},
        {"updated_at": "timestamp"},
    )

    predicate = render_watermark_filter_predicate(
        columns=("updated_at",),
        watermark_value=watermark,
    )

    assert predicate == "`updated_at` > CAST('2026-01-01 00:00:00' AS timestamp)"


def test_render_composite_watermark_filter_predicate() -> None:
    watermark = encode_watermark_values(
        {"updated_at": "2026-01-01", "version": 3},
        {"updated_at": "date", "version": "bigint"},
    )

    predicate = render_watermark_filter_predicate(
        columns=("updated_at", "version"),
        watermark_value=watermark,
    )

    assert "`updated_at` > CAST('2026-01-01' AS date)" in predicate
    assert "`updated_at` = CAST('2026-01-01' AS date)" in predicate
    assert "`version` > CAST('3' AS bigint)" in predicate
    assert " OR " in predicate


def test_render_watermark_candidate_sql_for_single_column() -> None:
    sql = render_select_watermark_candidate_sql(
        table_name="main.silver.orders",
        columns=("updated_at",),
        types={"updated_at": "timestamp"},
    )

    assert "FROM `main`.`silver`.`orders`" in sql
    assert "MAX(`updated_at`)" in sql
    assert "'type', 'timestamp'" in sql
    assert "AS watermark_value" in sql


def test_render_watermark_candidate_sql_for_composite_columns() -> None:
    sql = render_select_watermark_candidate_sql(
        table_name="main.silver.orders",
        columns=("updated_at", "version"),
        types={"updated_at": "date", "version": "bigint"},
    )

    assert "MAX(named_struct('updated_at', `updated_at`, 'version', `version`)) AS wm" in sql
    assert "'type', 'date'" in sql
    assert "'type', 'bigint'" in sql
    assert "CAST(wm.`version` AS STRING)" in sql
