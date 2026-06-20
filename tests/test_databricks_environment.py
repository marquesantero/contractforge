import pytest

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_databricks import DatabricksAdapter, DatabricksEnvironment, render_databricks_contract


def test_databricks_environment_from_core_contract() -> None:
    environment = DatabricksEnvironment.from_contract(
        {
            "environment": {
                "name": "prod",
                "adapter": "databricks",
                "runtime": {"kind": "serverless"},
                "deployment": {"workspace_path": "/Workspace/CF", "target": "prod"},
                "evidence": {"catalog": "main", "schema": "cf_ops"},
                "parameters": {"databricks": {"job.max_concurrent_runs": 1}},
            }
        }
    )

    assert environment.name == "prod"
    assert environment.runtime_kind == "serverless"
    assert environment.workspace_path == "/Workspace/CF"
    assert environment.bundle_target == "prod"
    assert environment.evidence_schema == "cf_ops"
    assert environment.parameters == {"job.max_concurrent_runs": 1}


def test_databricks_environment_rejects_wrong_adapter() -> None:
    with pytest.raises(ValueError, match="environment.adapter='databricks'"):
        DatabricksEnvironment.from_contract({"name": "prod", "adapter": "aws"})


def test_databricks_rendering_uses_environment_locations() -> None:
    artifacts = render_databricks_contract(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
        },
        environment={
            "name": "prod",
            "adapter": "databricks",
            "deployment": {"workspace_path": "/Workspace/CF", "target": "prod"},
            "evidence": {"catalog": "main", "schema": "cf_ops"},
        },
    )

    assert "CREATE SCHEMA IF NOT EXISTS `main`.`cf_ops`;" in artifacts.artifacts["main_bronze_orders.evidence_ddl.sql"]
    assert "FROM `main`.`cf_ops`.`ctrl_ingestion_runs`" in artifacts.artifacts["main_bronze_orders.cost.sql"]
    assert "notebook_path: /Workspace/CF/main_bronze_orders/run" in artifacts.artifacts["main_bronze_orders.databricks.yml"]
    assert "  prod:" in artifacts.artifacts["main_bronze_orders.databricks.yml"]


def test_databricks_adapter_environment_runtime_feeds_capability_evidence() -> None:
    adapter = DatabricksAdapter.from_evidence(
        target_table="main.bronze.orders",
        spark_conf={"spark.databricks.serverless.enabled": "true"},
        environment={"name": "prod", "adapter": "databricks", "runtime": {"kind": "serverless"}},
    )
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
        }
    )

    assert adapter.environment.name == "prod"
    assert adapter.plan(contract).status == "SUPPORTED"
