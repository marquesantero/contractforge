import json

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_databricks import render_databricks_contract
from contractforge_databricks.sources import render_source_metadata_json, source_metadata_from_contract


def test_source_metadata_from_jdbc_contract_is_redacted() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {
                "type": "connector",
                "connector": "postgres",
                "system": "crm",
                "table": "public.orders",
                "options": {"fetchsize": 1000},
                "auth": {"user": "app", "password": "raw-secret"},
                "incremental": {"watermark": {"column": "updated_at", "type": "timestamp"}},
            },
            "target": {"catalog": "main", "schema": "silver", "table": "orders"},
            "mode": "scd1_upsert",
            "merge_keys": ["order_id"],
        }
    )

    metadata = source_metadata_from_contract(contract)

    assert metadata["target_table"] == "main.silver.orders"
    assert metadata["source_type"] == "connector"
    assert metadata["source_connector"] == "postgres"
    assert metadata["source_system"] == "crm"
    assert metadata["source_path"] == "public.orders"
    assert metadata["source_options"] == {"fetchsize": 1000}
    assert metadata["source_auth"]["password"] == "***REDACTED***"
    assert metadata["source_incremental"]["watermark"]["column"] == "updated_at"


def test_render_source_metadata_json_is_stable() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "incremental_files", "path": "s3://bucket/orders", "format": "json"},
            "target": {"table": "orders"},
            "mode": "scd0_append",
        }
    )

    payload = json.loads(render_source_metadata_json(contract))

    assert payload["source_provider"] == "aws"
    assert payload["source_capabilities"]["incremental"] is True


def test_adapter_bundle_includes_source_metadata_artifact() -> None:
    artifacts = render_databricks_contract(
        {
            "source": {
                "type": "http_json",
                "url": "https://example.test/orders.json?token=secret-token",
                "auth": {"type": "bearer_token", "token": "secret-token"},
                "options": {"timeout_seconds": 30},
            },
            "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
        },
        runtime_type="serverless",
        spark_conf={"spark.databricks.serverless.enabled": "true"},
    )

    payload = artifacts.artifacts["main_bronze_orders.source_metadata.json"]

    assert "secret-token" not in payload
    assert '"source_type": "http_json"' in payload
    assert '"timeout_seconds": 30' in payload
