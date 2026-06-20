from __future__ import annotations

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_fabric import can_render_transform, render_fabric_contract


def _contract(transform: dict[str, object]) -> dict[str, object]:
    return {
        "source": {"type": "sql", "query": "SELECT 1 AS order_id, ' North ' AS region, 42 AS amount"},
        "target": {"catalog": "workspace", "schema": "silver", "table": "orders"},
        "mode": "overwrite",
        "transform": transform,
    }


def test_fabric_notebook_renders_portable_transform_steps_before_quality() -> None:
    notebook = render_fabric_contract(
        _contract(
            {
                "cast": {"amount": "double"},
                "standardize": {"region": {"trim": True, "upper": True, "empty_as_null": True}},
                "derive": {"amount_band": "CASE WHEN amount > 100 THEN 'HIGH' ELSE 'LOW' END"},
                "composite_keys": {"order_key": ["order_id", "region"]},
                "deduplicate": {
                    "keys": ["order_key"],
                    "order_by": [{"column": "amount", "direction": "desc", "nulls": "last"}],
                },
            }
        )
    ).artifacts["workspace_silver_orders.fabric.notebook.py"]

    compile(notebook, "workspace_silver_orders.fabric.notebook.py", "exec")
    assert "from pyspark.sql.window import Window" in notebook
    assert "# Apply portable transform intent." in notebook
    assert "transform_casts = {'amount': 'double'}" in notebook
    assert "df = df.withColumn(column_name, F.col(column_name).cast(data_type))" in notebook
    assert "transform_standardize = {'region': {'trim': True, 'lower': False, 'upper': True" in notebook
    assert "column_expr = F.when(column_expr == '', F.lit(None)).otherwise(column_expr)" in notebook
    assert "transform_derive = {'amount_band': \"CASE WHEN amount > 100 THEN 'HIGH' ELSE 'LOW' END\"}" in notebook
    assert "transform_composite_keys = {'order_key': ['order_id', 'region']}" in notebook
    assert "deduplicate_keys = ['order_key']" in notebook
    assert "Window.partitionBy(*deduplicate_keys).orderBy(F.col('amount').desc_nulls_last())" in notebook

    read_pos = notebook.index("    _cf_rows_read = df.count()")
    transform_pos = notebook.index("    # Apply portable transform intent.")
    schema_pos = notebook.index("    _cf_validate_schema_policy(dataframe=df)")
    write_pos = notebook.index('    df.write.format("delta").mode("overwrite").saveAsTable(TARGET_TABLE)')
    assert read_pos < transform_pos < schema_pos < write_pos


def test_fabric_transform_deduplicate_string_order_by_is_parsed() -> None:
    notebook = render_fabric_contract(
        _contract({"deduplicate": {"keys": "order_id", "order_by": "amount ASC NULLS FIRST"}})
    ).artifacts["workspace_silver_orders.fabric.notebook.py"]

    compile(notebook, "workspace_silver_orders.fabric.notebook.py", "exec")
    assert "deduplicate_keys = ['order_id']" in notebook
    assert "Window.partitionBy(*deduplicate_keys).orderBy(F.col('amount').asc_nulls_first())" in notebook


def test_fabric_does_not_emit_notebook_for_unrenderable_transform() -> None:
    contract = _contract({"deduplicate": {"keys": ["order_id"], "order_by": "length(region) DESC"}})

    assert can_render_transform(semantic_contract_from_mapping(contract)) is False

    artifacts = render_fabric_contract(contract).artifacts
    assert "workspace_silver_orders.fabric.notebook.py" not in artifacts
    assert "workspace_silver_orders.fabric.notebook.definition.json" not in artifacts
    assert "workspace_silver_orders.fabric.review.md" in artifacts
