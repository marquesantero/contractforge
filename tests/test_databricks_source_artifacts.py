from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_databricks.sources import render_source_artifacts


def test_render_source_artifacts_returns_empty_for_minimal_connector() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "connector", "connector": "postgres"},
            "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
        }
    )

    assert render_source_artifacts(contract) == {}


def test_render_source_artifacts_routes_jdbc_source() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {
                "type": "connector",
                "connector": "postgres",
                "url": "jdbc:postgresql://host/db",
                "table": "public.orders",
            },
            "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
        }
    )

    artifacts = render_source_artifacts(contract)

    assert list(artifacts) == ["main_bronze_orders.source_jdbc.py"]


def test_render_source_artifacts_routes_file_stream_intent_to_autoloader() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {
                "type": "s3",
                "intent": "file_stream",
                "path": "s3://bucket/landing/orders",
                "format": "json",
                "state": {
                    "storage": "external",
                    "location": {"type": "object_storage", "path": "s3://bucket/_checkpoints/orders"},
                },
            },
            "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
        }
    )

    artifacts = render_source_artifacts(contract)

    assert list(artifacts) == ["main_bronze_orders.source_autoloader.py"]
    assert ".format('cloudFiles')" in artifacts["main_bronze_orders.source_autoloader.py"]
    assert "checkpoint_location = 's3://bucket/_checkpoints/orders'" in artifacts["main_bronze_orders.source_autoloader.py"]
