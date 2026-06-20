import json

import pytest

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_databricks import DatabricksAdapter
from contractforge_databricks.sources import render_native_passthrough_plan


def test_render_native_passthrough_plan() -> None:
    plan = render_native_passthrough_plan(
        {
            "type": "native_passthrough",
            "system": "salesforce",
            "object": "Account",
            "watermark": {"column": "SystemModstamp"},
            "auth": {"type": "oauth2_jwt", "secret_scope": "sf_prod"},
        }
    )
    payload = json.loads(plan)

    assert payload["kind"] == "databricks_native_passthrough_plan"
    assert payload["system"] == "salesforce"
    assert payload["recommended_databricks_targets"] == ["lakeflow_connect"]
    assert payload["auth"]["secret_scope"] == "<redacted>"


def test_render_native_passthrough_plan_requires_system_and_object() -> None:
    with pytest.raises(ValueError, match="system and object"):
        render_native_passthrough_plan({"type": "native_passthrough", "system": "salesforce"})


def test_adapter_bundle_includes_native_passthrough_plan() -> None:
    adapter = DatabricksAdapter.from_evidence(
        target_table="main.bronze.accounts",
        runtime_type="serverless",
        spark_conf={"spark.databricks.serverless.enabled": "true"},
    )
    contract = semantic_contract_from_mapping(
        {
            "source": {
                "type": "native_passthrough",
                "system": "salesforce",
                "object": "Account",
                "auth": {"secret_scope": "sf_prod"},
            },
            "target": {"catalog": "main", "schema": "bronze", "table": "accounts"},
            "mode": "scd0_append",
        }
    )

    artifacts = adapter.render_contract(contract)

    assert "main_bronze_accounts.native_passthrough.json" in artifacts.artifacts
    assert "lakeflow_connect" in artifacts.artifacts["main_bronze_accounts.native_passthrough.json"]
