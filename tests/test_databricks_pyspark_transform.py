from __future__ import annotations

import sys
import types

import pytest

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_databricks.preparation.pyspark import apply_contract_preparation, apply_transform


class Expr:
    def __init__(self, value: str) -> None:
        self.value = value

    def cast(self, data_type: str) -> "Expr":
        return Expr(f"cast({self.value} as {data_type})")

    def otherwise(self, other: "Expr") -> "Expr":
        return Expr(f"otherwise({self.value}, {other.value})")

    def over(self, window: object) -> "Expr":
        return Expr(f"over({self.value})")

    def asc(self) -> "Expr":
        return Expr(f"{self.value} asc")

    def desc(self) -> "Expr":
        return Expr(f"{self.value} desc")

    def asc_nulls_last(self) -> "Expr":
        return Expr(f"{self.value} asc nulls last")

    def asc_nulls_first(self) -> "Expr":
        return Expr(f"{self.value} asc nulls first")

    def desc_nulls_last(self) -> "Expr":
        return Expr(f"{self.value} desc nulls last")

    def desc_nulls_first(self) -> "Expr":
        return Expr(f"{self.value} desc nulls first")

    def __eq__(self, other: object) -> "Expr":  # type: ignore[override]
        return Expr(f"{self.value} = {other!r}")


class FakeDataType:
    def __init__(self, name: str = "string") -> None:
        self.name = name

    def typeName(self) -> str:
        return self.name


class FakeField:
    def __init__(self, name: str, data_type: str = "string") -> None:
        self.name = name
        self.dataType = FakeDataType(data_type)


class FakeSchema:
    def __init__(self, columns: list[str]) -> None:
        self.fields = [FakeField(column) for column in columns]


class FakeFunctions:
    @staticmethod
    def col(name: str) -> Expr:
        return Expr(f"col({name})")

    @staticmethod
    def expr(value: str) -> Expr:
        return Expr(f"expr({value})")

    @staticmethod
    def regexp_replace(value: Expr, pattern: str, replacement: str) -> Expr:
        return Expr(f"regexp_replace({value.value})")

    @staticmethod
    def coalesce(*values: Expr) -> Expr:
        return Expr(f"coalesce({', '.join(value.value for value in values)})")

    @staticmethod
    def concat_ws(separator: str, *values: Expr) -> Expr:
        return Expr(f"concat_ws({separator}, {', '.join(value.value for value in values)})")

    @staticmethod
    def trim(value: Expr) -> Expr:
        return Expr(f"trim({value.value})")

    @staticmethod
    def lower(value: Expr) -> Expr:
        return Expr(f"lower({value.value})")

    @staticmethod
    def lit(value: object) -> Expr:
        return Expr(f"lit({value!r})")

    @staticmethod
    def when(condition: Expr, value: Expr) -> Expr:
        return Expr(f"when({condition.value}, {value.value})")

    @staticmethod
    def row_number() -> Expr:
        return Expr("row_number()")

    @staticmethod
    def decode(value: Expr, encoding: str) -> Expr:
        return Expr(f"decode({value.value}, {encoding})")


class FakeWindow:
    @staticmethod
    def partitionBy(*columns: str) -> "FakeWindow":
        window = FakeWindow()
        window.columns = columns
        return window

    def orderBy(self, *columns: Expr) -> "FakeWindow":
        self.order_columns = columns
        FakeWindow.last_order_columns = tuple(column.value for column in columns)
        return self


class FakeDF:
    def __init__(self, columns: list[str]) -> None:
        self.columns = columns
        self.calls = []
        self.schema = FakeSchema(columns)

    def withColumn(self, name: str, expression: Expr) -> "FakeDF":
        self.calls.append(("withColumn", name, expression.value))
        if name not in self.columns:
            self.columns.append(name)
            self.schema = FakeSchema(self.columns)
        return self

    def filter(self, expression: Expr) -> "FakeDF":
        self.calls.append(("filter", expression.value))
        return self

    def drop(self, *columns: str) -> "FakeDF":
        self.calls.append(("drop", columns))
        self.columns = [column for column in self.columns if column not in columns]
        self.schema = FakeSchema(self.columns)
        return self

    def select(self, *columns: str) -> "FakeDF":
        self.calls.append(("select", columns))
        self.columns = list(columns)
        self.schema = FakeSchema(self.columns)
        return self

    def withColumnRenamed(self, source: str, target: str) -> "FakeDF":
        self.calls.append(("withColumnRenamed", source, target))
        self.columns = [target if column == source else column for column in self.columns]
        self.schema = FakeSchema(self.columns)
        return self

    def where(self, expression: Expr | str) -> "FakeDF":
        value = expression.value if hasattr(expression, "value") else str(expression)
        self.calls.append(("where", value))
        return self


@pytest.fixture(autouse=True)
def fake_pyspark(monkeypatch):
    pyspark = types.ModuleType("pyspark")
    sql = types.ModuleType("pyspark.sql")
    sql.functions = FakeFunctions
    sql.Window = FakeWindow
    monkeypatch.setitem(sys.modules, "pyspark", pyspark)
    monkeypatch.setitem(sys.modules, "pyspark.sql", sql)
    yield


def test_apply_transform_cast_standardize_derive_and_deduplicate() -> None:
    df = FakeDF(["amount", "email", "updated_at", "order_id"])

    result = apply_transform(
        df,
        {
            "cast": {"amount": "double"},
            "standardize": {"email": {"trim": True, "lower": True, "empty_as_null": True}},
            "derive": {"order_date": "to_date(updated_at)"},
            "deduplicate": {"keys": ["order_id"], "order_by": [{"column": "updated_at", "direction": "desc"}]},
        },
    )

    assert result is df
    assert ("withColumn", "amount", "cast(col(amount) as double)") in df.calls
    assert ("withColumn", "email", "otherwise(when(lower(trim(col(email))) = '', lit(None)), lower(trim(col(email))))") in df.calls
    assert ("withColumn", "order_date", "expr(to_date(updated_at))") in df.calls
    assert ("withColumn", "__cf_row_number", "over(row_number())") in df.calls
    assert ("drop", ("__cf_row_number",)) in df.calls


def test_apply_transform_rejects_missing_columns() -> None:
    with pytest.raises(ValueError, match="transform.cast"):
        apply_transform(FakeDF(["id"]), {"cast": {"missing": "string"}})


def test_apply_contract_preparation_applies_portable_fields_before_write() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"table": "orders"},
            "select_columns": ["id", "amount", "updated_at"],
            "column_mapping": {"id": "order_id"},
            "filter_expression": "amount > 0",
            "transform": {"cast": {"amount": "double"}},
        }
    )
    df = FakeDF(["id", "amount", "updated_at", "ignored"])

    result = apply_contract_preparation(df, contract)

    assert result is df
    assert ("select", ("id", "amount", "updated_at")) in df.calls
    assert ("withColumnRenamed", "id", "order_id") in df.calls
    assert ("withColumn", "amount", "cast(col(amount) as double)") in df.calls
    assert ("where", "expr(amount > 0)") in df.calls


def test_apply_contract_preparation_applies_transform_deduplicate() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"table": "orders"},
            "mode": "scd1_upsert",
            "merge_keys": ["order_id"],
            "transform": {"deduplicate": {"keys": ["order_id"], "order_by": "updated_at DESC NULLS LAST"}},
        }
    )
    df = FakeDF(["order_id", "amount", "updated_at"])

    apply_contract_preparation(df, contract)

    assert FakeWindow.last_order_columns == ("col(updated_at) desc nulls last",)
    assert ("withColumn", "__cf_row_number", "over(row_number())") in df.calls
    assert ("filter", "col(__cf_row_number) = 1") in df.calls
    assert ("drop", ("__cf_row_number",)) in df.calls


def test_apply_contract_preparation_applies_composite_keys_before_deduplicate() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"table": "orders"},
            "mode": "scd1_upsert",
            "merge_keys": ["order_line_key"],
            "transform": {
                "composite_keys": {"order_line_key": ["order_id", "line_id"]},
                "deduplicate": {"keys": ["order_line_key"], "order_by": "updated_at DESC NULLS LAST"},
            },
        }
    )
    df = FakeDF(["order_id", "line_id", "amount", "updated_at"])

    apply_contract_preparation(df, contract)

    custom_key_call = next(i for i, call in enumerate(df.calls) if call[0:2] == ("withColumn", "order_line_key"))
    dedup_call = next(i for i, call in enumerate(df.calls) if call[0:2] == ("withColumn", "__cf_row_number"))
    assert custom_key_call < dedup_call
    assert (
        "withColumn",
        "order_line_key",
        "concat_ws(|, coalesce(cast(col(order_id) as string), lit('')), coalesce(cast(col(line_id) as string), lit('')))",
    ) in df.calls


def test_apply_contract_preparation_applies_watermark_after_mapping_before_deduplicate() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"table": "orders"},
            "mode": "scd1_upsert",
            "merge_keys": ["order_id"],
            "column_mapping": {"updated_raw": "updated_at"},
            "transform": {"deduplicate": {"keys": ["order_id"], "order_by": "updated_at DESC NULLS LAST"}},
        }
    )
    df = FakeDF(["order_id", "updated_raw", "amount"])

    apply_contract_preparation(
        df,
        contract,
        watermark_column="updated_at",
        watermark_previous='{"updated_at":{"type":"timestamp","value":"2026-01-01 00:00:00"}}',
    )

    mapping_call = next(i for i, call in enumerate(df.calls) if call[0:2] == ("withColumnRenamed", "updated_raw"))
    watermark_call = next(i for i, call in enumerate(df.calls) if call[0] == "where")
    dedup_call = next(i for i, call in enumerate(df.calls) if call[0:2] == ("withColumn", "__cf_row_number"))
    assert mapping_call < watermark_call < dedup_call
    assert ("where", "`updated_at` > CAST('2026-01-01 00:00:00' AS timestamp)") in df.calls


def test_apply_contract_preparation_applies_databricks_encoding_fix_last() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.customers"},
            "target": {"table": "customers"},
            "transform": {"derive": {"display_name": "concat(first_name, ' ', last_name)"}},
            "extensions": {
                "databricks": {
                    "fix_encoding": True,
                    "encoding": "windows-1252",
                    "encoding_columns": ["display_name"],
                }
            },
        }
    )
    df = FakeDF(["first_name", "last_name"])

    apply_contract_preparation(df, contract)

    derive_call = next(i for i, call in enumerate(df.calls) if call[0:2] == ("withColumn", "display_name"))
    encoding_call = next(i for i, call in enumerate(df.calls) if call == ("withColumn", "display_name", "decode(cast(col(display_name) as binary), windows-1252)"))
    assert derive_call < encoding_call


def test_apply_contract_preparation_rejects_mapping_collisions() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"table": "orders"},
            "column_mapping": {"id": "amount"},
        }
    )

    with pytest.raises(ValueError, match="collide"):
        apply_contract_preparation(FakeDF(["id", "amount"]), contract)


def test_apply_contract_preparation_rejects_mapping_to_reserved_control_columns() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"table": "orders"},
            "column_mapping": {"id": "row_hash"},
        }
    )

    with pytest.raises(ValueError, match="reserved control columns"):
        apply_contract_preparation(FakeDF(["id", "amount"]), contract)
