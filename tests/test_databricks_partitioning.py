import pytest

from contractforge_databricks.partitioning import render_partition_in_predicate, render_replace_where


def test_render_partition_in_predicate_deduplicates_and_quotes_values() -> None:
    predicate = render_partition_in_predicate("country", ["BR", "US", "BR", "O'Hare"])

    assert predicate == "`country` IN ('BR', 'US', 'O''Hare')"


def test_render_partition_in_predicate_handles_null_partition_values() -> None:
    assert render_partition_in_predicate("country", ["BR", None, "BR"]) == "`country` IN ('BR') OR `country` IS NULL"
    assert render_partition_in_predicate("country", [None]) == "`country` IS NULL"


def test_render_partition_in_predicate_rejects_empty_values() -> None:
    with pytest.raises(ValueError, match="at least one value"):
        render_partition_in_predicate("country", [])


def test_render_partition_in_predicate_enforces_limit() -> None:
    with pytest.raises(ValueError, match="above limit"):
        render_partition_in_predicate("id", [1, 2, 3], max_values=2)


def test_render_replace_where() -> None:
    assert render_replace_where("dt", "2026-05-27") == "`dt` = '2026-05-27'"
    assert render_replace_where("dt", None) == "`dt` IS NULL"
