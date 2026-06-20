import pytest

from contractforge_databricks.bundles import DatabricksJobSpec, render_databricks_asset_bundle


def test_render_databricks_asset_bundle() -> None:
    rendered = render_databricks_asset_bundle(
        DatabricksJobSpec(
            bundle_name="contractforge_orders",
            job_name="orders_ingestion",
            task_key="run_orders",
            notebook_path="/Workspace/ContractForge/orders/run",
        )
    )

    assert "bundle:" in rendered
    assert "name: contractforge_orders" in rendered
    assert "orders_ingestion:" in rendered
    assert "task_key: run_orders" in rendered
    assert "notebook_path: /Workspace/ContractForge/orders/run" in rendered


def test_render_databricks_asset_bundle_rejects_empty_fields() -> None:
    with pytest.raises(ValueError, match="job_name"):
        render_databricks_asset_bundle(
            DatabricksJobSpec(
                bundle_name="contractforge_orders",
                job_name="",
                task_key="run_orders",
                notebook_path="/Workspace/ContractForge/orders/run",
            )
        )

