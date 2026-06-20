from __future__ import annotations

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_databricks.rendering.names import artifact_prefix, bundle_name, job_name, task_key


def test_databricks_uses_core_naming_for_derived_artifacts() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"catalog": "main", "schema": "silver", "table": "orders"},
            "layer": "silver",
            "domain": "sales",
            "naming": {
                "contract_basename": "orders_contract",
                "bundle_name": "orders-bundle",
                "job_name": "Orders Silver Job",
                "task_key": "orders_task",
            },
        }
    )

    assert artifact_prefix(contract) == "orders_contract"
    assert bundle_name(contract) == "orders-bundle"
    assert job_name(contract) == "Orders Silver Job"
    assert task_key(contract) == "orders_task"


def test_databricks_default_derived_names_do_not_rewrite_target_identifier() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"catalog": "main", "schema": "silver", "table": "b_events"},
            "layer": "bronze",
        }
    )

    assert artifact_prefix(contract) == "main_silver_b_events"
    assert bundle_name(contract) == "cf-bronze-b-events"
    assert task_key(contract) == "cf_bronze_b_events"
