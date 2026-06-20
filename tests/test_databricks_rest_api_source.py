from __future__ import annotations

import json

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_databricks.sources import render_rest_api_review_plan, render_source_artifacts


def test_render_rest_api_review_plan_for_paginated_api() -> None:
    plan = render_rest_api_review_plan(
        {
            "type": "connector",
            "connector": "rest_api",
            "name": "orders_api",
            "request": {"url": "https://api.example.com/orders", "method": "GET"},
            "pagination": {"type": "cursor", "cursor_param": "cursor"},
            "auth": {"bearer_token": "raw-token"},
            "response": {"records_path": "$.items"},
            "incremental": {"watermark_param": "updated_since"},
        }
    )
    payload = json.loads(plan)

    assert payload["kind"] == "databricks_rest_api_review_plan"
    assert payload["recommended_databricks_targets"] == [
        "native_passthrough",
        "land_to_object_storage_then_incremental_files",
    ]
    assert payload["auth"]["bearer_token"] == "***REDACTED***"
    assert "custom Databricks Python API client" in payload["notes"][0]


def test_rest_api_connector_routes_to_review_artifact() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {
                "type": "connector",
                "connector": "rest_api",
                "name": "orders_api",
                "request": {"url": "https://api.example.com/orders"},
                "pagination": {"type": "page", "page_param": "page"},
            },
            "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
        }
    )

    artifacts = render_source_artifacts(contract)

    assert list(artifacts) == ["main_bronze_orders.source_rest_api_review.json"]
    assert "land_to_object_storage_then_incremental_files" in next(iter(artifacts.values()))
