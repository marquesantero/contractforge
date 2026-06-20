"""AWS shape.arrays rendering (Spark explode/size/first/to_json)."""

from __future__ import annotations

from contractforge_aws import render_aws_contract


def _contract(shape: dict, *, layer: str | None = None) -> dict:
    contract = {
        "source": {"type": "parquet", "path": "s3://landing/events"},
        "target": {"catalog": "lake", "schema": "bronze", "table": "events"},
        "mode": "scd0_append",
        "shape": shape,
    }
    if layer is not None:
        contract["layer"] = layer
    return contract


def _glue_job(shape: dict, *, layer: str | None = None) -> str:
    artifacts = render_aws_contract(_contract(shape, layer=layer))
    job = artifacts.artifacts["lake_bronze_events.glue_job.py"]
    compile(job, "glue_job.py", "exec")
    return job


def test_non_cardinality_array_modes_render_in_bronze() -> None:
    job = _glue_job(
        {
            "arrays": [
                {"path": "items", "mode": "size", "alias": "item_count"},
                {"path": "tags", "mode": "to_json"},
                {"path": "events", "mode": "first", "alias": "first_event"},
            ]
        }
    )
    assert "from pyspark.sql import functions as F" in job
    assert "df = df.withColumn('item_count', F.size(F.col('items')))" in job
    assert "df = df.withColumn('tags', F.to_json(F.col('tags')))" in job
    assert "df = df.withColumn('first_event', F.element_at(F.col('events'), 1))" in job


def test_explode_in_bronze_is_review_only_by_default() -> None:
    artifacts = render_aws_contract(_contract({"arrays": [{"path": "items", "mode": "explode"}]}))
    assert "lake_bronze_events.glue_job.py" not in artifacts.artifacts
    assert "lake_bronze_events.glue_job.todo.md" in artifacts.artifacts


def test_explode_renders_with_cardinality_flag() -> None:
    job = _glue_job(
        {"allow_cardinality_change_on_bronze": True, "arrays": [{"path": "items", "mode": "explode", "alias": "item"}]}
    )
    assert "df = df.withColumn('item', F.explode(F.col('items')))" in job


def test_explode_renders_outside_bronze_layer() -> None:
    artifacts = render_aws_contract(_contract({"arrays": [{"path": "items", "mode": "explode"}]}, layer="silver"))
    job = artifacts.artifacts["lake_bronze_events.glue_job.py"]
    assert "df = df.withColumn('items', F.explode(F.col('items')))" in job


def test_sibling_explodes_without_allow_cartesian_are_review_only() -> None:
    artifacts = render_aws_contract(
        _contract(
            {
                "allow_cardinality_change_on_bronze": True,
                "arrays": [
                    {"path": "order.items", "mode": "explode"},
                    {"path": "order.refunds", "mode": "explode"},
                ],
            }
        )
    )
    assert "lake_bronze_events.glue_job.py" not in artifacts.artifacts


def test_parse_json_then_arrays_render_in_order() -> None:
    job = _glue_job(
        {
            "allow_cardinality_change_on_bronze": True,
            "parse_json": [{"column": "payload", "schema": "struct<items:array<string>>"}],
            "arrays": [{"path": "payload.items", "mode": "explode", "alias": "item"}],
        }
    )
    parse_idx = job.index("F.from_json(")
    explode_idx = job.index("F.explode(")
    assert parse_idx < explode_idx


def test_zip_arrays_renders_with_temp_columns_and_field_renames() -> None:
    job = _glue_job(
        {
            "zip_arrays": [
                {
                    "alias": "hourly",
                    "columns": {"payload.times": "time", "payload.temperatures": "temperature"},
                }
            ]
        }
    )

    assert "shape_zip_arrays = [{'alias': 'hourly', 'columns': {'payload.times': 'time'" in job
    assert "df = df.withColumn(temp, F.col(str(path)))" in job
    assert "zipped = F.arrays_zip(*[F.col(temp) for temp, _field in temp_columns])" in job
    assert "item.getField(temp).alias(field_alias)" in job
    assert "df = df.withColumn(alias, renamed).drop(*[temp for temp, _field in temp_columns])" in job
