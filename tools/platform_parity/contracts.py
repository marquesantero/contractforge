"""Shared Databricks/AWS/Snowflake/Fabric/GCP parity scenarios.

The scenarios in this module deliberately keep ingestion intent identical
across platforms. Only runtime binding is overlaid: source location,
environment and adapter-owned extensions.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Literal

PlatformName = Literal["databricks", "aws", "snowflake", "fabric", "gcp"]


@dataclass(frozen=True)
class ParityScenario:
    name: str
    description: str
    base_contract: dict[str, Any]
    databricks_overlay: dict[str, Any]
    aws_overlay: dict[str, Any]
    snowflake_overlay: dict[str, Any]
    fabric_overlay: dict[str, Any]
    gcp_overlay: dict[str, Any]
    databricks_environment: dict[str, Any]
    aws_environment: dict[str, Any]
    snowflake_environment: dict[str, Any]
    fabric_environment: dict[str, Any]
    gcp_environment: dict[str, Any]
    expected_databricks_status: str
    expected_aws_status: str
    expected_snowflake_status: str
    expected_fabric_status: str
    expected_gcp_status: str
    required_databricks_artifact_suffixes: tuple[str, ...]
    required_aws_artifact_suffixes: tuple[str, ...]
    required_snowflake_artifact_suffixes: tuple[str, ...]
    required_fabric_artifact_suffixes: tuple[str, ...]
    required_gcp_artifact_suffixes: tuple[str, ...]

    def contract_for(self, platform: PlatformName) -> dict[str, Any]:
        overlay = {
            "databricks": self.databricks_overlay,
            "aws": self.aws_overlay,
            "snowflake": self.snowflake_overlay,
            "fabric": self.fabric_overlay,
            "gcp": self.gcp_overlay,
        }[platform]
        return deep_merge(self.base_contract, overlay)

    def environment_for(self, platform: PlatformName) -> dict[str, Any]:
        return deepcopy(
            {
                "databricks": self.databricks_environment,
                "aws": self.aws_environment,
                "snowflake": self.snowflake_environment,
                "fabric": self.fabric_environment,
                "gcp": self.gcp_environment,
            }[platform]
        )


def platform_parity_scenarios() -> tuple[ParityScenario, ...]:
    return (
        _orders_append_quality(),
        _orders_overwrite_shape(),
        _customers_upsert(),
        _customers_hash_diff(),
        _customers_historical(),
        _customers_snapshot_soft_delete(),
        _governance_review_boundary(),
    )


def scenario_by_name(name: str) -> ParityScenario:
    for scenario in platform_parity_scenarios():
        if scenario.name == name:
            return scenario
    valid = ", ".join(item.name for item in platform_parity_scenarios())
    raise ValueError(f"Unknown parity scenario {name!r}. Valid scenarios: {valid}")


def portability_signature(contract: dict[str, Any]) -> dict[str, Any]:
    """Return the contract subset that must remain portable across adapters."""

    normalized = deepcopy(contract)
    source = normalized.get("source")
    if isinstance(source, dict):
        for key in (
            "type",
            "path",
            "stage",
            "url",
            "connection_path",
            "progress_location",
            "schema_tracking_location",
            "checkpoint_location",
            "options",
            "format",
            "file_format",
            "pattern",
        ):
            source.pop(key, None)
    normalized.pop("extensions", None)
    return normalized


def platform_delta(contract: dict[str, Any]) -> dict[str, Any]:
    """Return the adapter/runtime binding that is allowed to differ."""

    source = contract.get("source") if isinstance(contract.get("source"), dict) else {}
    return {
        "source": {
            key: source[key]
            for key in (
                "type",
                "path",
                "stage",
                "url",
                "connection_path",
                "progress_location",
                "schema_tracking_location",
                "checkpoint_location",
                "options",
                "format",
                "file_format",
                "pattern",
            )
            if key in source
        },
        "extensions": deepcopy(contract.get("extensions") or {}),
    }


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _common_environments() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    databricks = {
        "name": "parity_databricks",
        "adapter": "databricks",
        "evidence": {"catalog": "contractforge", "schema": "cf_parity_ops"},
        "parameters": {
            "databricks": {
                "runtime": "serverless",
                "warehouse_id": "replace-with-warehouse-or-job-runtime",
            }
        },
    }
    aws = {
        "name": "parity_aws",
        "adapter": "aws",
        "evidence": {"database": "contractforge_cf_parity_ops"},
        "parameters": {
            "aws": {
                "region": "us-east-1",
                "glue_job": {
                    "role_arn": "arn:aws:iam::123456789012:role/ContractForgeGlueParityRole",
                    "worker_type": "G.1X",
                    "number_of_workers": 2,
                    "timeout_minutes": 10,
                },
            }
        },
    }
    snowflake = {
        "name": "parity_snowflake",
        "adapter": "snowflake",
        "evidence": {"database": "CONTRACTFORGE", "schema": "CF_PARITY_OPS"},
        "artifacts": {"uri": '@"CONTRACTFORGE_TEST_DB"."PUBLIC"."CF_PARITY_ARTIFACTS"/platform-parity/'},
        "parameters": {
            "snowflake": {
                "warehouse": "COMPUTE_WH",
                "role": "CONTRACTFORGE_INGEST_ROLE",
                "task_database": "CONTRACTFORGE_TEST_DB",
                "task_schema": "PUBLIC",
                "runner_procedure": "CONTRACTFORGE_TEST_DB.PUBLIC.RUN_CONTRACTFORGE_CONTRACT",
                "runtime_wheel_uri": '@"CONTRACTFORGE_TEST_DB"."PUBLIC"."CF_PARITY_ARTIFACTS"/libs/contractforge_snowflake-0.1.0-py3-none-any.whl',
            }
        },
    }
    fabric = {
        "name": "parity_fabric",
        "adapter": "fabric",
        "evidence": {"lakehouse": "contractforge_lh", "schema": "contractforge"},
        "artifacts": {"uri": "abfss://workspace@onelake.dfs.fabric.microsoft.com/artifacts"},
        "runtime": {"kind": "notebook"},
        "parameters": {
            "fabric": {
                "tenant_id": "3fb3492c-48be-4ac6-ae3a-fec6a63cf4d1",
                "tenant_domain": "ticomcafe.com.br",
                "workspace_name": "cf-dev",
                "lakehouse_name": "contractforge_lh",
                "warehouse_name": "contractforge_wh",
            }
        },
    }
    gcp = {
        "name": "parity_gcp",
        "adapter": "gcp",
        "evidence": {"dataset": "contractforge_cf_parity_ops"},
        "parameters": {
            "gcp": {
                "project_id": "contractforge-parity",
                "location": "US",
                "dataset": "contractforge",
            }
        },
    }
    return databricks, aws, snowflake, fabric, gcp


def _source_overlays(
    dataset: str,
    columns: dict[str, str],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    databricks = {"source": {"path": f"dbfs:/tmp/contractforge/parity/{dataset}/"}}
    aws = {
        "source": {"path": f"s3://contractforge-parity-us-east-1/data/{dataset}/"},
        "extensions": {"aws": {"iceberg": {"warehouse": "s3://contractforge-parity-us-east-1/warehouse/"}}},
    }
    snowflake = {
        "source": {
            "type": "staged_files",
            "path": f'@"CONTRACTFORGE_TEST_DB"."PUBLIC"."CF_PARITY_DATA"/{dataset}/',
            "format": "json",
            "options": {
                "columns": columns,
                "file_format": "CONTRACTFORGE_TEST_DB.PUBLIC.CF_PARITY_JSON_FORMAT",
            },
        },
        "extensions": {"snowflake": {"explain_enabled": False}},
    }
    fabric = {"source": {"path": f"Files/contractforge/parity/{dataset}/"}}
    gcp = {"source": {"path": f"gs://contractforge-parity-us/data/{dataset}/"}}
    return databricks, aws, snowflake, fabric, gcp


def _snowflake_columns(*names: str) -> dict[str, str]:
    return {name: f"$1:{name}::STRING" for name in names}


def _base_target(table: str, layer: str = "bronze") -> dict[str, Any]:
    return {"catalog": "contractforge", "schema": f"cf_parity_{layer}", "table": table}


def _orders_append_quality() -> ParityScenario:
    databricks_env, aws_env, snowflake_env, fabric_env, gcp_env = _common_environments()
    dbx_source, aws_source, snowflake_source, fabric_source, gcp_source = _source_overlays(
        "orders_append",
        _snowflake_columns("order_id", "status", "amount"),
    )
    base = {
        "source": {"type": "json", "format": "json"},
        "target": _base_target("orders_append"),
        "layer": "bronze",
        "mode": "scd0_append",
        "schema_policy": "additive_only",
        "transform": {
            "cast": {"amount": "DOUBLE"},
            "standardize": {"status": {"upper": True, "trim": True}},
        },
        "quality_rules": {
            "required_columns": ["order_id", "status", "amount"],
            "not_null": ["order_id"],
            "accepted_values": {"status": ["NEW", "PAID", "CANCELLED"]},
            "min_rows": 1,
        },
        "annotations": {
            "table": {
                "description": "Parity smoke table for append and quality enforcement.",
                "tags": {"domain": "orders", "test": "platform-parity"},
            },
            "columns": {"order_id": {"description": "Business order identifier."}},
        },
    }
    return ParityScenario(
        name="orders_append_quality",
        description="Append JSON orders with portable casts, standardization and quality/quarantine.",
        base_contract=base,
        databricks_overlay=dbx_source,
        aws_overlay=aws_source,
        snowflake_overlay=snowflake_source,
        fabric_overlay=fabric_source,
        gcp_overlay=gcp_source,
        databricks_environment=databricks_env,
        aws_environment=aws_env,
        snowflake_environment=snowflake_env,
        fabric_environment=fabric_env,
        gcp_environment=gcp_env,
        expected_databricks_status="SUPPORTED",
        expected_aws_status="SUPPORTED",
        expected_snowflake_status="SUPPORTED",
        expected_fabric_status="SUPPORTED_WITH_WARNINGS",
        expected_gcp_status="SUPPORTED_WITH_WARNINGS",
        required_databricks_artifact_suffixes=(".review.md", ".quality.sql", ".annotations.sql", ".databricks.yml"),
        required_aws_artifact_suffixes=(".review.md", ".glue_job.py", ".evidence_ddl.sql", ".annotations.json"),
        required_snowflake_artifact_suffixes=(".contract.json", ".publish_manifest.json", ".planning.md"),
        required_fabric_artifact_suffixes=(
            ".fabric.review.md",
            ".fabric.notebook.py",
            ".fabric.notebook.definition.json",
            ".fabric.source_review.json",
        ),
        required_gcp_artifact_suffixes=(".gcp.contract.json", ".gcp.capabilities.json", ".gcp.write.sql"),
    )


def _orders_overwrite_shape() -> ParityScenario:
    databricks_env, aws_env, snowflake_env, fabric_env, gcp_env = _common_environments()
    dbx_source, aws_source, snowflake_source, fabric_source, gcp_source = _source_overlays(
        "orders_overwrite_shape",
        _snowflake_columns("order_id", "payload"),
    )
    base = {
        "source": {"type": "json", "format": "json"},
        "target": _base_target("orders_items", layer="silver"),
        "layer": "silver",
        "mode": "scd0_overwrite",
        "shape": {
            "parse_json": [
                {
                    "column": "payload",
                    "schema": "STRUCT<items:ARRAY<STRUCT<sku:STRING,quantity:INT>>, channel:STRING>",
                    "alias": "payload_obj",
                }
            ],
            "arrays": [{"path": "payload_obj.items", "mode": "explode", "alias": "item"}],
            "columns": {
                "order_id": {"cast": "STRING"},
                "item.sku": {"alias": "sku", "cast": "STRING"},
                "item.quantity": {"alias": "quantity", "cast": "INT"},
                "payload_obj.channel": {"alias": "channel", "cast": "STRING"},
            },
        },
        "quality_rules": {
            "required_columns": ["order_id", "sku", "quantity"],
            "expressions": [{"name": "positive_quantity", "expression": "quantity > 0", "severity": "quarantine"}],
        },
    }
    return ParityScenario(
        name="orders_overwrite_shape",
        description="Overwrite a shaped/exploded silver table from the same nested order intent.",
        base_contract=base,
        databricks_overlay=dbx_source,
        aws_overlay=aws_source,
        snowflake_overlay=snowflake_source,
        fabric_overlay=fabric_source,
        gcp_overlay=gcp_source,
        databricks_environment=databricks_env,
        aws_environment=aws_env,
        snowflake_environment=snowflake_env,
        fabric_environment=fabric_env,
        gcp_environment=gcp_env,
        expected_databricks_status="SUPPORTED",
        expected_aws_status="SUPPORTED_WITH_WARNINGS",
        expected_snowflake_status="REVIEW_REQUIRED",
        expected_fabric_status="SUPPORTED_WITH_WARNINGS",
        expected_gcp_status="UNSUPPORTED",
        required_databricks_artifact_suffixes=(".review.md", ".shape.sql", ".quality.sql", ".databricks.yml"),
        required_aws_artifact_suffixes=(".review.md", ".glue_job.py", ".evidence_ddl.sql"),
        required_snowflake_artifact_suffixes=(".contract.json", ".publish_manifest.json", ".planning.md"),
        required_fabric_artifact_suffixes=(
            ".fabric.review.md",
            ".fabric.notebook.py",
            ".fabric.notebook.definition.json",
            ".fabric.source_review.json",
        ),
        required_gcp_artifact_suffixes=(".gcp.contract.json", ".gcp.capabilities.json"),
    )


def _customers_upsert() -> ParityScenario:
    databricks_env, aws_env, snowflake_env, fabric_env, gcp_env = _common_environments()
    dbx_source, aws_source, snowflake_source, fabric_source, gcp_source = _source_overlays(
        "customers_upsert",
        _snowflake_columns("customer_id", "email", "updated_at"),
    )
    base = {
        "source": {"type": "json", "format": "json", "read": {"columns": ["customer_id", "email", "updated_at"]}},
        "target": _base_target("customers_current", layer="silver"),
        "layer": "silver",
        "mode": "scd1_upsert",
        "merge_keys": ["customer_id"],
        "schema_policy": "additive_only",
        "transform": {
            "deduplicate": {
                "keys": ["customer_id"],
                "order_by": [{"column": "updated_at", "direction": "desc", "nulls": "last"}],
            },
            "standardize": {"email": {"lower": True, "trim": True}},
        },
        "quality_rules": {
            "required_columns": ["customer_id", "email", "updated_at"],
            "not_null": ["customer_id"],
            "unique_key": ["customer_id"],
        },
    }
    return ParityScenario(
        name="customers_upsert",
        description="SCD1 upsert with deterministic deduplication and merge-key guards.",
        base_contract=base,
        databricks_overlay=dbx_source,
        aws_overlay=aws_source,
        snowflake_overlay=snowflake_source,
        fabric_overlay=fabric_source,
        gcp_overlay=gcp_source,
        databricks_environment=databricks_env,
        aws_environment=aws_env,
        snowflake_environment=snowflake_env,
        fabric_environment=fabric_env,
        gcp_environment=gcp_env,
        expected_databricks_status="SUPPORTED",
        expected_aws_status="SUPPORTED",
        expected_snowflake_status="SUPPORTED",
        expected_fabric_status="SUPPORTED_WITH_WARNINGS",
        expected_gcp_status="SUPPORTED_WITH_WARNINGS",
        required_databricks_artifact_suffixes=(".review.md", ".write_mode.sql", ".quality.sql", ".databricks.yml"),
        required_aws_artifact_suffixes=(".review.md", ".glue_job.py", ".evidence_ddl.sql"),
        required_snowflake_artifact_suffixes=(".contract.json", ".publish_manifest.json", ".planning.md"),
        required_fabric_artifact_suffixes=(
            ".fabric.review.md",
            ".fabric.notebook.py",
            ".fabric.notebook.definition.json",
            ".fabric.source_review.json",
        ),
        required_gcp_artifact_suffixes=(".gcp.contract.json", ".gcp.capabilities.json", ".gcp.write.sql"),
    )


def _customers_hash_diff() -> ParityScenario:
    databricks_env, aws_env, snowflake_env, fabric_env, gcp_env = _common_environments()
    dbx_source, aws_source, snowflake_source, fabric_source, gcp_source = _source_overlays(
        "customers_hash_diff",
        _snowflake_columns("customer_id", "lifetime_value", "updated_at"),
    )
    base = {
        "source": {
            "type": "json",
            "format": "json",
            "read": {"columns": ["customer_id", "lifetime_value", "customer_band", "updated_at"]},
        },
        "target": _base_target("customers_hashdiff", layer="silver"),
        "layer": "silver",
        "mode": "scd1_hash_diff",
        "merge_keys": ["customer_id"],
        "hash_keys": ["lifetime_value", "customer_band"],
        "hash_exclude_columns": ["updated_at"],
        "schema_policy": "additive_only",
        "transform": {
            "cast": {"lifetime_value": "DOUBLE"},
            "derive": {"customer_band": "CASE WHEN lifetime_value >= 1000 THEN 'VIP' ELSE 'STANDARD' END"},
        },
        "quality_rules": {
            "required_columns": ["customer_id", "lifetime_value"],
            "not_null": ["customer_id"],
        },
    }
    return ParityScenario(
        name="customers_hash_diff",
        description="SCD1 hash-diff update minimization with the same hash semantics.",
        base_contract=base,
        databricks_overlay=dbx_source,
        aws_overlay=aws_source,
        snowflake_overlay=snowflake_source,
        fabric_overlay=fabric_source,
        gcp_overlay=gcp_source,
        databricks_environment=databricks_env,
        aws_environment=aws_env,
        snowflake_environment=snowflake_env,
        fabric_environment=fabric_env,
        gcp_environment=gcp_env,
        expected_databricks_status="SUPPORTED",
        expected_aws_status="SUPPORTED_WITH_WARNINGS",
        expected_snowflake_status="SUPPORTED_WITH_WARNINGS",
        expected_fabric_status="SUPPORTED_WITH_WARNINGS",
        expected_gcp_status="REVIEW_REQUIRED",
        required_databricks_artifact_suffixes=(".review.md", ".write_mode.sql", ".quality.sql", ".databricks.yml"),
        required_aws_artifact_suffixes=(".review.md", ".glue_job.py", ".evidence_ddl.sql"),
        required_snowflake_artifact_suffixes=(".contract.json", ".publish_manifest.json", ".planning.md"),
        required_fabric_artifact_suffixes=(
            ".fabric.review.md",
            ".fabric.notebook.py",
            ".fabric.notebook.definition.json",
            ".fabric.source_review.json",
        ),
        required_gcp_artifact_suffixes=(
            ".gcp.contract.json",
            ".gcp.capabilities.json",
            ".gcp.advanced_write_mode_review.json",
        ),
    )


def _customers_historical() -> ParityScenario:
    databricks_env, aws_env, snowflake_env, fabric_env, gcp_env = _common_environments()
    dbx_source, aws_source, snowflake_source, fabric_source, gcp_source = _source_overlays(
        "customers_historical",
        _snowflake_columns("customer_id", "email", "status", "updated_at"),
    )
    base = {
        "source": {
            "type": "json",
            "format": "json",
            "read": {"columns": ["customer_id", "email", "status", "updated_at"]},
        },
        "target": _base_target("customers_history", layer="silver"),
        "layer": "silver",
        "mode": "historical",
        "merge_keys": ["customer_id"],
        "schema_policy": "additive_only",
        "scd2_change_columns": ["email", "status"],
        "scd2_effective_from_column": "updated_at",
        "scd2_sequence_by": "updated_at",
        "scd2_late_arriving_policy": "reject",
        "scd2_apply_as_deletes": "status = 'DELETE'",
        "quality_rules": {
            "required_columns": ["customer_id", "email", "status", "updated_at"],
            "not_null": ["customer_id", "updated_at"],
            "unique_key": ["customer_id"],
        },
    }
    return ParityScenario(
        name="customers_historical",
        description="Historical SCD2 customer history with effective dating, delete expression and late-arriving reject semantics.",
        base_contract=base,
        databricks_overlay=dbx_source,
        aws_overlay=aws_source,
        snowflake_overlay=snowflake_source,
        fabric_overlay=fabric_source,
        gcp_overlay=gcp_source,
        databricks_environment=databricks_env,
        aws_environment=aws_env,
        snowflake_environment=snowflake_env,
        fabric_environment=fabric_env,
        gcp_environment=gcp_env,
        expected_databricks_status="SUPPORTED",
        expected_aws_status="REVIEW_REQUIRED",
        expected_snowflake_status="REVIEW_REQUIRED",
        expected_fabric_status="SUPPORTED_WITH_WARNINGS",
        expected_gcp_status="REVIEW_REQUIRED",
        required_databricks_artifact_suffixes=(".review.md", ".write_mode.sql", ".quality.sql", ".databricks.yml"),
        required_aws_artifact_suffixes=(".review.md", ".write_mode_review.md", ".evidence_ddl.sql"),
        required_snowflake_artifact_suffixes=(".contract.json", ".publish_manifest.json", ".planning.md"),
        required_fabric_artifact_suffixes=(
            ".fabric.review.md",
            ".fabric.notebook.py",
            ".fabric.notebook.definition.json",
            ".fabric.source_review.json",
        ),
        required_gcp_artifact_suffixes=(
            ".gcp.contract.json",
            ".gcp.capabilities.json",
            ".gcp.advanced_write_mode_review.json",
        ),
    )


def _customers_snapshot_soft_delete() -> ParityScenario:
    databricks_env, aws_env, snowflake_env, fabric_env, gcp_env = _common_environments()
    dbx_source, aws_source, snowflake_source, fabric_source, gcp_source = _source_overlays(
        "customers_snapshot_soft_delete",
        _snowflake_columns("customer_id", "email", "status", "updated_at"),
    )
    base = {
        "source": {
            "type": "json",
            "format": "json",
            "read": {
                "columns": ["customer_id", "email", "status", "updated_at"],
                "source_complete": True,
            },
        },
        "target": _base_target("customers_snapshot", layer="silver"),
        "layer": "silver",
        "mode": "snapshot_reconcile_soft_delete",
        "merge_keys": ["customer_id"],
        "schema_policy": "additive_only",
        "quality_rules": {
            "required_columns": ["customer_id", "email", "status", "updated_at"],
            "not_null": ["customer_id"],
            "unique_key": ["customer_id"],
        },
    }
    return ParityScenario(
        name="customers_snapshot_soft_delete",
        description="Complete-source snapshot reconciliation that reactivates present rows and soft-deletes missing keys.",
        base_contract=base,
        databricks_overlay=dbx_source,
        aws_overlay=aws_source,
        snowflake_overlay=snowflake_source,
        fabric_overlay=fabric_source,
        gcp_overlay=gcp_source,
        databricks_environment=databricks_env,
        aws_environment=aws_env,
        snowflake_environment=snowflake_env,
        fabric_environment=fabric_env,
        gcp_environment=gcp_env,
        expected_databricks_status="SUPPORTED",
        expected_aws_status="REVIEW_REQUIRED",
        expected_snowflake_status="REVIEW_REQUIRED",
        expected_fabric_status="SUPPORTED_WITH_WARNINGS",
        expected_gcp_status="REVIEW_REQUIRED",
        required_databricks_artifact_suffixes=(".review.md", ".write_mode.sql", ".quality.sql", ".databricks.yml"),
        required_aws_artifact_suffixes=(".review.md", ".write_mode_review.md", ".evidence_ddl.sql"),
        required_snowflake_artifact_suffixes=(".contract.json", ".publish_manifest.json", ".planning.md"),
        required_fabric_artifact_suffixes=(
            ".fabric.review.md",
            ".fabric.notebook.py",
            ".fabric.notebook.definition.json",
            ".fabric.source_review.json",
        ),
        required_gcp_artifact_suffixes=(
            ".gcp.contract.json",
            ".gcp.capabilities.json",
            ".gcp.advanced_write_mode_review.json",
        ),
    )


def _governance_review_boundary() -> ParityScenario:
    databricks_env, aws_env, snowflake_env, fabric_env, gcp_env = _common_environments()
    dbx_source, aws_source, snowflake_source, fabric_source, gcp_source = _source_overlays(
        "governed_customers",
        _snowflake_columns("customer_id", "email", "country"),
    )
    base = {
        "source": {"type": "json", "format": "json"},
        "target": _base_target("customers_governed", layer="gold"),
        "layer": "gold",
        "mode": "scd0_overwrite",
        "access": {
            "row_filters": [
                {
                    "name": "country_filter",
                    "function": "contractforge.security.country_filter",
                    "columns": ["country"],
                }
            ],
            "column_masks": {
                "email": {
                    "function": "contractforge.security.mask_email",
                    "using_columns": ["email"],
                }
            },
        },
        "annotations": {
            "table": {
                "description": "Governance parity boundary scenario.",
                "tags": {"sensitivity": "internal"},
            },
            "columns": {
                "email": {
                    "pii": {"enabled": True, "type": "email", "sensitivity": "confidential"},
                    "description": "Customer email address.",
                }
            },
        },
    }
    return ParityScenario(
        name="governance_review_boundary",
        description="Same access intent, explicit AWS review boundary for Lake Formation equivalence.",
        base_contract=base,
        databricks_overlay=dbx_source,
        aws_overlay=aws_source,
        snowflake_overlay=snowflake_source,
        fabric_overlay=fabric_source,
        gcp_overlay=gcp_source,
        databricks_environment=databricks_env,
        aws_environment=aws_env,
        snowflake_environment=snowflake_env,
        fabric_environment=fabric_env,
        gcp_environment=gcp_env,
        expected_databricks_status="SUPPORTED",
        expected_aws_status="REVIEW_REQUIRED",
        expected_snowflake_status="SUPPORTED",
        expected_fabric_status="REVIEW_REQUIRED",
        expected_gcp_status="REVIEW_REQUIRED",
        required_databricks_artifact_suffixes=(".review.md", ".governance.sql", ".access_audit.sql", ".databricks.yml"),
        required_aws_artifact_suffixes=(".review.md", ".lakeformation.json", ".lakeformation_evidence.sql"),
        required_snowflake_artifact_suffixes=(".contract.json", ".publish_manifest.json", ".planning.md"),
        required_fabric_artifact_suffixes=(
            ".fabric.review.md",
            ".fabric.access.json",
            ".fabric.notebook.py",
            ".fabric.notebook.definition.json",
        ),
        required_gcp_artifact_suffixes=(".gcp.contract.json", ".gcp.capabilities.json", ".gcp.governance_ledger.json"),
    )
