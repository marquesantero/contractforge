from __future__ import annotations

import sys
import types

import pytest

from contractforge_databricks.preparation.shape import apply_shape


class Expr:
    def __init__(self, value: str) -> None:
        self.value = value

    def getField(self, name: str) -> "Expr":
        return Expr(f"{self.value}.{name}")

    def cast(self, data_type: str) -> "Expr":
        return Expr(f"cast({self.value} as {data_type})")

    def alias(self, alias: str) -> "Expr":
        return Expr(f"{self.value} as {alias}")


class FakeFunctions:
    @staticmethod
    def col(name: str) -> Expr:
        return Expr(f"col({name})")

    @staticmethod
    def expr(value: str) -> Expr:
        return Expr(f"expr({value})")

    @staticmethod
    def from_json(column: Expr, schema: str) -> Expr:
        return Expr(f"from_json({column.value}, {schema})")

    @staticmethod
    def arrays_zip(*columns: Expr) -> Expr:
        return Expr("arrays_zip(" + ",".join(column.value for column in columns) + ")")

    @staticmethod
    def transform(column: Expr, func) -> Expr:
        return Expr(f"transform({column.value}, {func(Expr('item')).value})")

    @staticmethod
    def struct(*columns: Expr) -> Expr:
        return Expr("struct(" + ",".join(column.value for column in columns) + ")")

    @staticmethod
    def size(column: Expr) -> Expr:
        return Expr(f"size({column.value})")

    @staticmethod
    def to_json(column: Expr) -> Expr:
        return Expr(f"to_json({column.value})")

    @staticmethod
    def element_at(column: Expr, index: int) -> Expr:
        return Expr(f"element_at({column.value}, {index})")

    @staticmethod
    def explode(column: Expr) -> Expr:
        return Expr(f"explode({column.value})")

    @staticmethod
    def explode_outer(column: Expr) -> Expr:
        return Expr(f"explode_outer({column.value})")


class FakeDF:
    def __init__(self, columns: list[str]) -> None:
        self.columns = columns
        self.calls = []
        self.schema = types.SimpleNamespace(fields=[])

    def withColumn(self, name: str, expression: Expr) -> "FakeDF":
        self.calls.append(("withColumn", name, expression.value))
        if name not in self.columns:
            self.columns.append(name)
        return self

    def drop(self, *columns: str) -> "FakeDF":
        self.calls.append(("drop", columns))
        self.columns = [column for column in self.columns if column not in columns]
        return self

    def select(self, *expressions: Expr) -> "FakeDF":
        self.calls.append(("select", tuple(expression.value for expression in expressions)))
        return self


@pytest.fixture(autouse=True)
def fake_pyspark(monkeypatch):
    class StructType:
        def __init__(self, fields=None):
            self.fields = fields or []

    class ArrayType:
        def __init__(self, elementType=None):
            self.elementType = elementType

    class StringType:
        pass

    class StructField:
        def __init__(self, name, dataType):
            self.name = name
            self.dataType = dataType

    pyspark = types.ModuleType("pyspark")
    sql = types.ModuleType("pyspark.sql")
    sql.functions = FakeFunctions
    sql_types = types.ModuleType("pyspark.sql.types")
    sql_types.ArrayType = ArrayType
    sql_types.StringType = StringType
    sql_types.StructType = StructType
    sql_types.StructField = StructField
    monkeypatch.setitem(sys.modules, "pyspark", pyspark)
    monkeypatch.setitem(sys.modules, "pyspark.sql", sql)
    monkeypatch.setitem(sys.modules, "pyspark.sql.types", sql_types)
    yield


def test_apply_shape_parse_arrays_zip_and_projection() -> None:
    df = FakeDF(["payload", "time", "temperature"])

    result = apply_shape(
        df,
        {
            "parse_json": [{"column": "payload", "schema": "STRUCT<id: STRING>", "alias": "payload_obj"}],
            "zip_arrays": [{"alias": "hour", "columns": {"time": "time", "temperature": "temperature"}}],
            "arrays": [{"path": "hour", "mode": "size", "alias": "hour_count"}],
            "columns": {
                "payload_obj.id": {"alias": "event_id", "cast": "STRING"},
                "hour_count": "hour_count",
                "ingested_at": {"expression": "current_timestamp()", "alias": "ingested_at"},
            },
        },
    )

    assert result is df
    assert ("withColumn", "payload_obj", "from_json(col(`payload`), STRUCT<id: STRING>)") in df.calls
    assert ("withColumn", "__cf_shape_zip_0_0", "col(`time`)") in df.calls
    assert ("withColumn", "__cf_shape_zip_0_1", "col(`temperature`)") in df.calls
    assert (
        "withColumn",
        "hour",
        "transform(arrays_zip(col(__cf_shape_zip_0_0),col(__cf_shape_zip_0_1)), "
        "struct(item.__cf_shape_zip_0_0 as time,item.__cf_shape_zip_0_1 as temperature))",
    ) in df.calls
    assert ("withColumn", "hour_count", "size(col(`hour`))") in df.calls
    assert (
        "select",
        (
            "cast(col(`payload_obj`.`id`) as STRING) as event_id",
            "col(`hour_count`) as hour_count",
            "expr(current_timestamp()) as ingested_at",
        ),
    ) in df.calls


def test_apply_shape_blocks_bronze_cardinality_change_by_default() -> None:
    with pytest.raises(ValueError, match="blocked in bronze"):
        apply_shape(FakeDF(["items"]), {"arrays": [{"path": "items", "mode": "explode"}]}, layer="bronze")


def test_apply_shape_rejects_sibling_explodes_without_cartesian_flag() -> None:
    with pytest.raises(ValueError, match="cartesian product"):
        apply_shape(
            FakeDF(["payload"]),
            {
                "arrays": [
                    {"path": "payload.items", "mode": "explode", "allow_cartesian": True},
                    {"path": "payload.discounts", "mode": "explode"},
                ],
            },
        )


def test_apply_shape_requires_runtime_json_schema() -> None:
    with pytest.raises(ValueError, match="requires schema"):
        apply_shape(FakeDF(["payload"]), {"parse_json": [{"column": "payload", "schema_ref": "payload_schema"}]})


def test_apply_shape_flatten_honors_include_and_exclude() -> None:
    from pyspark.sql.types import StructField, StructType

    df = FakeDF(["payload", "metadata", "tenant_id"])
    df.schema = types.SimpleNamespace(
        fields=[
            StructField("payload", StructType([StructField("id", object()), StructField("secret", object())])),
            StructField("metadata", StructType([StructField("source", object())])),
            StructField("tenant_id", object()),
        ]
    )

    apply_shape(
        df,
        {
            "flatten": {
                "enabled": True,
                "separator": "__",
                "include": ["payload"],
                "exclude": ["payload.secret"],
            }
        },
    )

    assert (
        "select",
        (
            "col(`payload`.`id`) as payload__id",
            "col(`metadata`) as metadata",
            "col(`tenant_id`) as tenant_id",
        ),
    ) in df.calls


def test_apply_shape_validates_schema_types_when_schema_is_available() -> None:
    from pyspark.sql.types import ArrayType, StringType, StructField, StructType

    df = FakeDF(["payload", "items", "not_array"])
    df.schema = StructType(
        [
            StructField("payload", StringType()),
            StructField("items", ArrayType(StringType())),
            StructField("not_array", StringType()),
        ]
    )

    apply_shape(
        df,
        {
            "parse_json": [{"column": "payload", "schema": "STRUCT<id: STRING>", "alias": "payload_obj"}],
            "arrays": [{"path": "items", "mode": "size", "alias": "item_count"}],
        },
    )

    with pytest.raises(ValueError, match="must be array"):
        apply_shape(df, {"arrays": [{"path": "not_array", "mode": "size"}]})


def test_apply_shape_drops_zip_intermediate_consumed_by_array() -> None:
    df = FakeDF(["time", "temperature"])

    apply_shape(
        df,
        {
            "zip_arrays": [{"alias": "hour", "columns": {"time": "time", "temperature": "temperature"}}],
            "arrays": [{"path": "hour", "mode": "explode_outer", "alias": "hour_row"}],
        },
    )

    assert (
        "withColumn",
        "hour",
        "transform(arrays_zip(col(__cf_shape_zip_0_0),col(__cf_shape_zip_0_1)), "
        "struct(item.__cf_shape_zip_0_0 as time,item.__cf_shape_zip_0_1 as temperature))",
    ) in df.calls
    assert ("withColumn", "hour_row", "explode_outer(col(`hour`))") in df.calls
    assert ("drop", ("hour",)) in df.calls


def test_apply_shape_resolves_nested_arrays_declared_out_of_order() -> None:
    df = FakeDF(["payload"])

    apply_shape(
        df,
        {
            "arrays": [
                {"path": "item.children", "mode": "size", "alias": "child_count"},
                {"path": "payload.items", "mode": "explode", "alias": "item"},
            ],
        },
    )

    assert ("withColumn", "item", "explode(col(`payload`.`items`))") in df.calls
    assert ("withColumn", "child_count", "size(col(`item`.`children`))") in df.calls
    assert ("drop", ("item",)) in df.calls
