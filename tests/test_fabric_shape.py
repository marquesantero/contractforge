from __future__ import annotations

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_fabric import can_render_shape, render_fabric_contract, render_flatten_helper


def _contract(shape: dict[str, object]) -> dict[str, object]:
    return {
        "source": {"type": "sql", "query": "SELECT '{\"id\":\"o1\",\"amount\":42}' AS payload"},
        "target": {"catalog": "workspace", "schema": "silver", "table": "events"},
        "mode": "overwrite",
        "shape": shape,
    }


def test_fabric_notebook_renders_parse_json_and_columns_before_transforms() -> None:
    notebook = render_fabric_contract(
        _contract(
            {
                "parse_json": [
                    {
                        "column": "payload",
                        "schema": "STRUCT<id: STRING, amount: DOUBLE>",
                        "alias": "payload_obj",
                        "cast_input": "STRING",
                    }
                ],
                "columns": {
                    "payload_obj.id": "event_id",
                    "payload_obj.amount": {"alias": "amount", "cast": "double"},
                },
            }
        )
    ).artifacts["workspace_silver_events.fabric.notebook.py"]

    compile(notebook, "workspace_silver_events.fabric.notebook.py", "exec")
    assert "df = df.withColumn('payload_obj', F.from_json(F.col('payload').cast('string'), 'STRUCT<id: STRING, amount: DOUBLE>'))" in notebook
    assert "df = df.select(" in notebook
    assert "F.col('payload_obj.id').alias('event_id')," in notebook
    assert "F.col('payload_obj.amount').cast('double').alias('amount')," in notebook

    read_pos = notebook.index("    _cf_rows_read = df.count()")
    shape_pos = notebook.index("    df = df.withColumn('payload_obj'")
    schema_pos = notebook.index("    _cf_validate_schema_policy(dataframe=df)")
    assert read_pos < shape_pos < schema_pos


def test_fabric_notebook_renders_flatten_helper_and_call() -> None:
    notebook = render_fabric_contract(
        _contract({"flatten": {"enabled": True, "separator": "__", "max_depth": 3, "include": ["payload"]}})
    ).artifacts["workspace_silver_events.fabric.notebook.py"]

    compile(notebook, "workspace_silver_events.fabric.notebook.py", "exec")
    assert "def _cf_flatten(df, separator, max_depth, include, exclude):" in notebook
    assert "df = _cf_flatten(" in notebook
    assert "separator='__'," in notebook
    assert "max_depth=3," in notebook
    assert "include=['payload']," in notebook
    compile(render_flatten_helper(), "flatten.py", "exec")


def test_fabric_notebook_renders_array_explode_before_columns() -> None:
    contract = _contract(
        {
            "arrays": [{"path": "items", "mode": "explode", "alias": "item"}],
            "columns": {"item.id": "item_id"},
        }
    )

    assert can_render_shape(semantic_contract_from_mapping(contract)) is True
    artifacts = render_fabric_contract(contract).artifacts
    notebook = artifacts["workspace_silver_events.fabric.notebook.py"]

    compile(notebook, "workspace_silver_events.fabric.notebook.py", "exec")
    assert "df = df.withColumn('item', F.explode(F.col('items')))" in notebook
    assert "F.col('item.id').alias('item_id')," in notebook
    assert notebook.index("    df = df.withColumn('item'") < notebook.index("    df = df.select(")


def test_fabric_shape_arrays_without_alias_remain_review_only() -> None:
    contract = _contract({"arrays": [{"path": "items", "mode": "explode"}]})

    assert can_render_shape(semantic_contract_from_mapping(contract)) is False
    artifacts = render_fabric_contract(contract).artifacts
    assert "workspace_silver_events.fabric.notebook.py" not in artifacts


def test_fabric_shape_cartesian_arrays_remain_review_only() -> None:
    contract = _contract({"arrays": [{"path": "items", "mode": "explode", "alias": "item", "allow_cartesian": True}]})

    assert can_render_shape(semantic_contract_from_mapping(contract)) is False
    artifacts = render_fabric_contract(contract).artifacts
    assert "workspace_silver_events.fabric.notebook.py" not in artifacts
