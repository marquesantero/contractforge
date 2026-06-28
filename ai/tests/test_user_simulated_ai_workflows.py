from __future__ import annotations

import json
from pathlib import Path

import yaml

from contractforge_ai.agentic import IntentGenerationRequest, generate_from_intent
from contractforge_ai.generators.project import (
    generate_aws_glue_iceberg_project,
    generate_databricks_dab_project,
)
from contractforge_ai.project_structure import validate_project_structure
from contractforge_ai.projects import write_project_plan


def test_user_deterministic_geojson_project_minimizes_adapter_contract_differences(tmp_path: Path) -> None:
    schema = _schema(
        tmp_path,
        "usgs_geojson",
        [
            ("event_id", "STRING", False),
            ("event_time", "TIMESTAMP", True),
            ("magnitude", "DOUBLE", True),
            ("place", "STRING", True),
            ("longitude", "DOUBLE", True),
            ("latitude", "DOUBLE", True),
        ],
    )

    common = {
        "schema_path": schema,
        "project_name": "USGS GeoJSON",
        "connector": "http_file",
        "source_path": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson",
        "target_catalog": "analytics",
        "target_schema": "bronze",
        "target_table": "b_usgs_events",
        "layer": "bronze",
        "mode": "scd0_append",
        "owner": "data-platform",
        "schedule_cron": "0 6 * * *",
        "schedule_timezone": "America/Sao_Paulo",
    }

    databricks = generate_databricks_dab_project(**common)
    aws = generate_aws_glue_iceberg_project(**common)
    databricks_root = tmp_path / "databricks"
    aws_root = tmp_path / "aws"
    write_project_plan(databricks, databricks_root)
    write_project_plan(aws, aws_root)

    databricks_contract = _only_ingestion(databricks)
    aws_contract = _only_ingestion(aws)
    databricks_project = _artifact_yaml(databricks, "project.yaml")
    aws_project = _artifact_yaml(aws, "project.yaml")

    assert databricks_contract["source"]["type"] == "connection"
    assert aws_contract["source"]["type"] == "connection"
    assert databricks_contract["source"]["path"] == common["source_path"]
    assert aws_contract["source"]["path"] == common["source_path"]
    assert _portable_contract(databricks_contract) == _portable_contract(aws_contract)
    assert databricks_project["schedule"] == aws_project["schedule"]
    assert databricks_project["schedule"]["timezone"] == "America/Sao_Paulo"
    assert databricks_project["schedule"]["enabled"] is False
    assert validate_project_structure(databricks_root, adapters=("databricks",)).status in {
        "READY",
        "READY_WITH_WARNINGS",
        "NEEDS_DECISIONS",
    }
    assert validate_project_structure(aws_root, adapters=("aws",)).status in {
        "READY",
        "READY_WITH_WARNINGS",
        "NEEDS_DECISIONS",
    }


def test_user_deterministic_supabase_jdbc_projects_keep_connections_shared(tmp_path: Path) -> None:
    schema = _schema(
        tmp_path,
        "supabase_products",
        [
            ("product_id", "STRING", False),
            ("sku", "STRING", True),
            ("brand", "STRING", True),
            ("price", "DOUBLE", True),
            ("updated_at", "TIMESTAMP", True),
        ],
    )

    common = {
        "schema_path": schema,
        "project_name": "Supabase Products",
        "connector": "jdbc",
        "source_path": "public.products",
        "target_catalog": "analytics",
        "target_schema": "silver",
        "target_table": "s_products",
        "layer": "silver",
        "mode": "scd1_hash_diff",
        "owner": "data-platform",
        "schedule_cron": "0 2 * * *",
        "schedule_timezone": "UTC",
    }

    databricks = generate_databricks_dab_project(**common)
    aws = generate_aws_glue_iceberg_project(**common)
    databricks_contract = _only_ingestion(databricks)
    aws_contract = _only_ingestion(aws)
    databricks_connection = _connection(databricks)
    aws_connection = _connection(aws)

    assert databricks_contract["source"]["connection_path"] == "project://connections/source.yaml"
    assert aws_contract["source"]["connection_path"] == "project://connections/source.yaml"
    assert databricks_contract["merge_keys"] == ["product_id"]
    assert aws_contract["merge_keys"] == ["product_id"]
    assert databricks_connection == aws_connection
    assert databricks_connection["source"]["connector"] == "jdbc"
    assert databricks_contract["source"]["path"] == "public.products"
    assert aws_contract["source"]["path"] == "public.products"


def test_user_prompt_generates_multiplatform_medallion_project_with_schedule(tmp_path: Path) -> None:
    schema = _schema(
        tmp_path,
        "orders",
        [
            ("order_id", "STRING", False),
            ("customer_id", "STRING", True),
            ("amount", "DOUBLE", True),
            ("currency", "STRING", True),
            ("updated_at", "TIMESTAMP", True),
        ],
    )

    result = generate_from_intent(
        IntentGenerationRequest(
            prompt=(
                "Create a complete medallion project for Databricks and AWS from main.raw.orders_sample "
                "bronze to gold using scd1_hash_diff. Daily at 6 Sao Paulo time. "
                "Business owner: revenue. Technical owner: data-platform. Criticality: high. "
                "Required columns: order_id, amount. Unique key: order_id. "
                "Hash columns: customer_id, amount, currency, updated_at. amount must be >= 0. "
                "currency accepted values: USD, EUR, BRL. Gold final columns: order_id, customer_id, amount, currency."
            ),
            schema_path=str(schema),
        )
    )

    assert result.project is not None
    assert result.intent is not None
    assert set(result.intent.platform_hints) == {"databricks", "aws"}
    assert result.intent.schedule == {"cron": "0 6 * * *", "timezone": "America/Sao_Paulo"}
    assert result.layers == ["bronze", "silver", "gold"]

    project_root = tmp_path / "prompt_project"
    write_project_plan(result.project, project_root)
    project = yaml.safe_load((project_root / "project.yaml").read_text(encoding="utf-8"))
    silver = yaml.safe_load((project_root / "contracts" / "silver" / "s_orders.ingestion.yaml").read_text(encoding="utf-8"))
    gold = yaml.safe_load((project_root / "contracts" / "gold" / "g_orders.ingestion.yaml").read_text(encoding="utf-8"))

    assert project["environments"] == {
        "review": "environments/review.environment.yaml",
        "databricks": "environments/databricks.environment.yaml",
        "aws": "environments/aws.environment.yaml",
    }
    assert project["schedule"] == {"cron": "0 6 * * *", "timezone": "America/Sao_Paulo", "enabled": False}
    assert project["execution_order"][1]["depends_on"] == ["bronze_b_orders"]
    assert project["execution_order"][2]["depends_on"] == ["silver_s_orders"]
    assert silver["mode"] == "hash_diff_upsert"
    assert silver["source"]["type"] == "connection"
    assert silver["hash_keys"] == ["customer_id", "amount", "currency", "updated_at"]
    assert gold["transform"]["shape"]["columns"] == {
        "order_id": "order_id",
        "customer_id": "customer_id",
        "amount": "amount",
        "currency": "currency",
    }
    assert gold["quality_rules"]["not_null"] == ["order_id", "amount"]
    assert gold["quality_rules"]["unique_key"] == ["order_id"]
    assert validate_project_structure(project_root, adapters=("databricks", "aws")).status in {
        "READY",
        "READY_WITH_WARNINGS",
        "NEEDS_DECISIONS",
    }


def test_user_prompt_generates_all_schema_paths_in_one_project(tmp_path: Path) -> None:
    schemas = (
        _schema(tmp_path, "orders", [("order_id", "STRING", False), ("customer_id", "STRING", True), ("amount", "DOUBLE", True), ("updated_at", "TIMESTAMP", True)]),
        _schema(tmp_path, "customers", [("customer_id", "STRING", False), ("email", "STRING", True), ("status", "STRING", True), ("updated_at", "TIMESTAMP", True)]),
        _schema(tmp_path, "products", [("product_id", "STRING", False), ("sku", "STRING", True), ("price", "DOUBLE", True), ("updated_at", "TIMESTAMP", True)]),
    )

    result = generate_from_intent(
        IntentGenerationRequest(
            prompt=(
                "Create a complete medallion project for Databricks and AWS from s3://landing/supabase "
                "bronze to gold using scd1_hash_diff. Daily at 6 Sao Paulo time. "
                "Hash columns: updated_at. Products use scd1_upsert."
            ),
            schema_paths=schemas,
            default_catalog="analytics",
        )
    )

    assert result.project is not None
    assert result.schema_source == {"kind": "schema_paths", "paths": list(schemas), "count": 3}
    project_root = tmp_path / "multi_schema_project"
    write_project_plan(result.project, project_root)
    project = yaml.safe_load((project_root / "project.yaml").read_text(encoding="utf-8"))

    assert project["schedule"] == {"cron": "0 6 * * *", "timezone": "America/Sao_Paulo", "enabled": False}
    assert len(project["execution_order"]) == 9
    assert set(project["environments"]) == {"review", "databricks", "aws"}
    assert project["execution_order"][0]["name"] == "orders_bronze_b_orders"
    assert project["execution_order"][1]["depends_on"] == ["orders_bronze_b_orders"]
    assert project["execution_order"][2]["depends_on"] == ["orders_silver_s_orders"]

    bronze_orders = yaml.safe_load((project_root / "contracts" / "bronze" / "b_orders.ingestion.yaml").read_text(encoding="utf-8"))
    silver_orders = yaml.safe_load((project_root / "contracts" / "silver" / "s_orders.ingestion.yaml").read_text(encoding="utf-8"))
    silver_products = yaml.safe_load((project_root / "contracts" / "silver" / "s_products.ingestion.yaml").read_text(encoding="utf-8"))
    gold_customers = yaml.safe_load((project_root / "contracts" / "gold" / "g_customers.ingestion.yaml").read_text(encoding="utf-8"))

    assert bronze_orders["source"]["path"] == "s3://landing/supabase/orders"
    assert bronze_orders["source"]["type"] == "connection"
    assert silver_orders["source"]["table"] == "analytics.bronze.b_orders"
    assert silver_orders["hash_keys"] == ["updated_at"]
    assert silver_products["mode"] == "upsert"
    assert "hash_keys" not in silver_products
    assert gold_customers["source"]["table"] == "analytics.silver.s_customers"
    assert validate_project_structure(project_root, adapters=("databricks", "aws")).status in {
        "READY",
        "READY_WITH_WARNINGS",
        "NEEDS_DECISIONS",
    }


def test_user_prompt_schema_list_requires_at_least_schema_evidence_when_empty() -> None:
    result = generate_from_intent(
        IntentGenerationRequest(
            prompt="Create a medallion project for all schemas from s3://landing/orders.",
            schema_paths=(),
        )
    )

    assert result.status == "NEEDS_DECISIONS"
    assert result.project is not None
    assert result.project.artifacts[0].path == "AI_REVIEW.html"


def test_user_prompt_without_schema_stops_before_generation() -> None:
    result = generate_from_intent(
        IntentGenerationRequest(
            prompt=(
                "Create a Supabase medallion project for AWS and Databricks daily at 6 Sao Paulo time "
                "with scd1_hash_diff and product_id as key."
            )
        )
    )

    assert result.status == "NEEDS_DECISIONS"
    assert result.project is not None
    assert result.project.artifacts[0].path == "AI_REVIEW.html"
    assert "schema evidence is required" in result.project.artifacts[0].content
    assert result.intent is not None
    assert result.intent.schedule == {"cron": "0 6 * * *", "timezone": "America/Sao_Paulo"}
    assert result.policy_result is not None
    assert result.policy_result.action == "block"


def test_user_prompt_keeps_provider_out_of_deterministic_status(tmp_path: Path) -> None:
    schema = _schema(tmp_path, "events", [("event_id", "STRING", False), ("payload", "STRING", True)])
    provider = _StatusChangingProvider()

    result = generate_from_intent(
        IntentGenerationRequest(
            prompt="Create a bronze project from https://example.com/events.json into main.bronze.b_events.",
            schema_path=str(schema),
            provider=provider,
        )
    )

    assert result.project is not None
    assert provider.requests
    assert result.status in {"READY", "NEEDS_DECISIONS"}
    contract = _only_ingestion(result.project)
    assert contract["target"] == {"catalog": "main", "schema": "bronze", "table": "b_events"}
    assert contract["source"]["type"] == "connection"
    assert contract["source"]["path"] == "https://example.com/events.json"


class _StatusChangingProvider:
    name = "status-changing"

    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []

    def complete(self, prompt: str, *, system: str | None = None, options: object | None = None) -> str:
        self.requests.append({"prompt": prompt, "system": system, "options": options})
        return json.dumps(
            {
                "kind": "project_plan",
                "summary": "Provider claims this should be unsupported, but deterministic status owns readiness.",
                "recommendations": ["Do not let the provider override deterministic validation."],
                "evidence": ["Synthetic provider response for test."],
                "assumptions": [],
                "decisions_required": [],
                "confidence": 0.99,
                "review_required": False,
                "status": "UNSUPPORTED",
            }
        )


def _schema(tmp_path: Path, name: str, columns: list[tuple[str, str, bool]]) -> str:
    path = tmp_path / f"{name}.json"
    path.write_text(
        json.dumps({"columns": [{"name": column, "type": data_type, "nullable": nullable} for column, data_type, nullable in columns]}),
        encoding="utf-8",
    )
    return str(path)


def _only_ingestion(plan) -> dict:
    artifacts = [artifact for artifact in plan.artifacts if artifact.path.endswith(".ingestion.yaml")]
    assert len(artifacts) == 1 or plan.target == "intent-first-medallion"
    artifact = artifacts[0] if len(artifacts) == 1 else next(item for item in artifacts if "/bronze/" in item.path)
    return yaml.safe_load(artifact.content)


def _artifact_yaml(plan, path: str) -> dict:
    return yaml.safe_load(next(artifact.content for artifact in plan.artifacts if artifact.path == path))


def _connection(plan) -> dict:
    return yaml.safe_load(next(artifact.content for artifact in plan.artifacts if artifact.path == "connections/source.yaml"))


def _portable_contract(contract: dict) -> dict:
    return {
        key: value
        for key, value in contract.items()
        if key not in {"_metadata", "naming"}
    }
