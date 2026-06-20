import pytest

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_databricks import DatabricksAdapter
from contractforge_databricks.sources import render_catalog_source_python, render_file_source_python
from contractforge_databricks.sources.table_refs import databricks_table_ref_resolver


def test_render_file_source_python_for_csv() -> None:
    code = render_file_source_python(
        {
            "type": "csv",
            "path": "s3://bucket/orders",
            "options": {"header": True, "inferSchema": False},
        }
    )

    assert ".format('csv')" in code
    assert ".option('header', 'true')" in code
    assert ".load('s3://bucket/orders')" in code


def test_render_file_source_python_for_object_storage_format() -> None:
    code = render_file_source_python({"type": "s3", "format": "parquet", "path": "s3://bucket/orders"})

    assert ".format('parquet')" in code


def test_render_file_source_python_for_xml() -> None:
    code = render_file_source_python(
        {"type": "xml", "path": "s3://bucket/events", "options": {"rowTag": "event"}}
    )

    assert ".format('xml')" in code
    assert ".option('rowTag', 'event')" in code


def test_render_file_source_requires_path() -> None:
    with pytest.raises(ValueError, match="path"):
        render_file_source_python({"type": "json"})


def test_render_catalog_source_for_table_and_sql() -> None:
    assert render_catalog_source_python({"type": "table", "table": "main.raw.orders"}) == (
        "df = spark.table('main.raw.orders')\n"
    )
    assert render_catalog_source_python({"type": "sql", "query": "select * from main.raw.orders"}) == (
        "df = spark.sql('select * from main.raw.orders')\n"
    )


def test_render_catalog_source_resolves_logical_refs_for_databricks() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "ref": "bronze.orders"},
            "target": {"catalog": "workspace", "schema": "cf_demo_silver", "table": "orders_curated"},
            "layer": "silver",
        }
    )
    resolver = databricks_table_ref_resolver(contract)

    assert render_catalog_source_python(contract.source.raw, table_ref_resolver=resolver) == (
        "df = spark.table('workspace.cf_demo_bronze.orders')\n"
    )
    assert render_catalog_source_python(
        {"type": "sql", "query": "select * from {{ table_ref:bronze.orders }}"},
        table_ref_resolver=resolver,
    ) == "df = spark.sql('select * from workspace.cf_demo_bronze.orders')\n"


def test_databricks_bundle_renders_file_and_catalog_source_artifacts() -> None:
    adapter = DatabricksAdapter.from_evidence(
        target_table="main.bronze.orders",
        runtime_type="serverless",
        spark_conf={"spark.databricks.serverless.enabled": "true"},
    )
    file_contract = semantic_contract_from_mapping(
        {
            "source": {"type": "parquet", "path": "s3://bucket/orders"},
            "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
        }
    )
    table_contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
        }
    )

    assert "main_bronze_orders.source_files.py" in adapter.render_contract(file_contract).artifacts
    assert "main_bronze_orders.source_catalog.py" in adapter.render_contract(table_contract).artifacts
