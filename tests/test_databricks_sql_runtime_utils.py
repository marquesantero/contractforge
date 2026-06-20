from __future__ import annotations

import uuid

import pytest

from contractforge_databricks.runtime import as_list, new_run_id, safe_truncate, validate_columns
from contractforge_databricks.sql import sql_json, sql_literal


class FakeDataFrame:
    columns = ["id", "amount"]


def test_sql_literal_supports_generic_literals() -> None:
    assert sql_literal(None) == "NULL"
    assert sql_literal(True) == "true"
    assert sql_literal(12) == "12"
    assert sql_literal("O'Reilly") == "'O''Reilly'"
    assert sql_json({"b": 2, "a": 1}) == '\'{"a": 1, "b": 2}\''


def test_runtime_utility_conveniences_are_spark_free() -> None:
    assert as_list("a | b || c") == ["a", "b", "c"]
    assert safe_truncate("abcdef", max_len=3) == "abc\n...TRUNCATED..."
    uuid.UUID(new_run_id())

    validate_columns(FakeDataFrame(), ["id"], "merge_keys")
    with pytest.raises(ValueError, match="merge_keys"):
        validate_columns(FakeDataFrame(), ["missing"], "merge_keys")
