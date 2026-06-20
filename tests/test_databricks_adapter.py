import pytest

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_databricks import DatabricksAdapter, render_databricks_contract


def test_databricks_adapter_plans_and_renders_review_artifacts() -> None:
    adapter = DatabricksAdapter.from_evidence(
        target_table="main.silver.orders",
        runtime_type="serverless",
        spark_conf={"spark.databricks.serverless.enabled": "true"},
    )
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "connector", "connector": "postgres", "table": "public.orders"},
            "target": {"catalog": "main", "schema": "silver", "table": "orders"},
            "mode": "scd1_upsert",
            "access": {
                "column_masks": {
                    "email": {
                        "function": "main.security.mask_email",
                        "using_columns": ["email"],
                    }
                }
            },
            "merge_keys": ["order_id"],
        }
    )

    result = adapter.plan(contract)
    artifacts = adapter.render_contract(contract)

    assert result.status == "SUPPORTED"
    assert "main_silver_orders.review.md" in artifacts.artifacts
    assert "main_silver_orders.capabilities.json" in artifacts.artifacts
    assert "main_silver_orders.schema_policy.json" in artifacts.artifacts
    assert "main_silver_orders.annotations.sql" in artifacts.artifacts
    assert "main_silver_orders.annotations_audit.sql" in artifacts.artifacts
    assert "main_silver_orders.access_audit.sql" in artifacts.artifacts
    assert "main_silver_orders.databricks.yml" in artifacts.artifacts
    assert "main_silver_orders.state_ddl.sql" in artifacts.artifacts
    assert "main_silver_orders.openlineage.sql" in artifacts.artifacts
    assert "main_silver_orders.operations.json" in artifacts.artifacts
    assert "main_silver_orders.operations.sql" in artifacts.artifacts
    assert "main_silver_orders.diagnostics_ddl.sql" in artifacts.artifacts
    assert "main_silver_orders.cost.sql" in artifacts.artifacts
    assert "SCD1" in artifacts.artifacts["main_silver_orders.write_mode.sql"]
    assert "SET MASK main.security.mask_email" in artifacts.artifacts["main_silver_orders.governance.sql"]


def test_databricks_adapter_warns_for_unknown_adapter_extensions() -> None:
    adapter = DatabricksAdapter.from_evidence(
        target_table="main.bronze.orders",
        runtime_type="serverless",
        spark_conf={"spark.databricks.serverless.enabled": "true"},
    )
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
            "extensions": {"databricks": {"unknown_feature": True, "use_cache": True}},
        }
    )

    result = adapter.plan(contract)

    assert result.status == "SUPPORTED_WITH_WARNINGS"
    warnings = {warning.code: warning.message for warning in result.warnings}
    assert "DATABRICKS_UNKNOWN_EXTENSION" in warnings
    assert "use_cache" in "; ".join(warnings.values())


def test_databricks_adapter_rejects_top_level_extension_aliases() -> None:
    with pytest.raises(ValueError, match="cluster_columns"):
        render_databricks_contract(
            {
                "source": {"type": "table", "table": "main.raw.orders"},
                "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
                "mode": "scd0_append",
                "cluster_columns": ["order_id"],
            }
        )


def test_databricks_adapter_ignores_other_adapter_extension_blocks() -> None:
    adapter = DatabricksAdapter.from_evidence(
        target_table="main.bronze.orders",
        runtime_type="serverless",
        spark_conf={"spark.databricks.serverless.enabled": "true"},
    )
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
            "extensions": {"aws": {"unknown_feature": True}},
        }
    )

    result = adapter.plan(contract)

    assert "DATABRICKS_UNKNOWN_EXTENSION" not in {warning.code for warning in result.warnings}


def test_databricks_adapter_rejects_two_part_uc_governance() -> None:
    adapter = DatabricksAdapter.from_evidence(
        target_table="silver.orders",
        runtime_type="serverless",
        spark_conf={"spark.databricks.serverless.enabled": "true"},
    )
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "connector", "connector": "postgres"},
            "target": {"schema": "silver", "table": "orders"},
            "mode": "scd0_append",
            "access": {"row_filters": [{"name": "country_filter", "function": "main.sec.filter", "columns": ["country"]}]},
        }
    )

    result = adapter.plan(contract)

    assert result.status == "UNSUPPORTED"
    assert "ROW_FILTERS_UNSUPPORTED" in {blocker.code for blocker in result.blockers}


def test_databricks_adapter_renders_incremental_files_source_artifact() -> None:
    adapter = DatabricksAdapter.from_evidence(
        target_table="main.bronze.events",
        runtime_type="serverless",
        spark_conf={"spark.databricks.serverless.enabled": "true"},
    )
    contract = semantic_contract_from_mapping(
        {
            "source": {
                "type": "incremental_files",
                "path": "s3://bucket/events",
                "format": "json",
                "schema_tracking_location": "s3://bucket/_schemas/events",
            },
            "target": {"catalog": "main", "schema": "bronze", "table": "events"},
            "mode": "scd0_append",
        }
    )

    artifacts = adapter.render_contract(contract)

    assert "main_bronze_events.source_autoloader.py" in artifacts.artifacts
    assert ".format('cloudFiles')" in artifacts.artifacts["main_bronze_events.source_autoloader.py"]
