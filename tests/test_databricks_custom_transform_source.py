import json

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_databricks import DatabricksAdapter


def test_databricks_bundle_includes_custom_transform_review_and_notebook_task() -> None:
    adapter = DatabricksAdapter.from_evidence(
        target_table="main.gold.customer_features",
        runtime_type="serverless",
        spark_conf={"spark.databricks.serverless.enabled": "true"},
    )
    contract = semantic_contract_from_mapping(
        {
            "source": {
                "type": "custom_transform",
                "intent": "custom_treatment",
                "inputs": [
                    {"alias": "orders", "table_ref": {"layer": "silver", "table": "orders"}},
                    {"alias": "customers", "table": "main.silver.customers"},
                ],
            },
            "target": {"catalog": "main", "schema": "gold", "table": "customer_features"},
            "mode": "overwrite",
            "transform": {
                "custom": {
                    "name": "customer_feature_engineering",
                    "output": "customer_features",
                    "expected_columns": ["customer_id", "order_count", "lifetime_value"],
                    "parameters": {"min_orders": 2},
                }
            },
            "quality_rules": {"not_null": ["customer_id"]},
            "extensions": {
                "databricks": {
                    "custom_transform": {
                        "notebook_path": "/Workspace/ContractForge/customer_features/treatment",
                        "task_key": "prepare_customer_features",
                        "base_parameters": {"contract": "customer_features.ingestion.yaml"},
                    }
                }
            },
        }
    )

    artifacts = adapter.render_contract(contract).artifacts

    review = json.loads(artifacts["main_gold_customer_features.custom_transform_review.json"])
    assert review["kind"] == "databricks_custom_transform_review_plan"
    assert review["inputs"][0]["alias"] == "orders"
    assert review["custom_transform"]["name"] == "customer_feature_engineering"
    assert "main_gold_customer_features.custom_transform_review.md" in artifacts
    bundle = artifacts["main_gold_customer_features.databricks.yml"]
    assert "task_key: prepare_customer_features" in bundle
    assert "notebook_path: /Workspace/ContractForge/customer_features/treatment" in bundle
    assert "depends_on:" in bundle
    assert "- task_key: prepare_customer_features" in bundle
