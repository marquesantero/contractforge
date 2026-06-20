from contractforge_core.capabilities.native import capability
from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_databricks import (
    DatabricksCapabilities,
    access_drift_report,
    apply_access_contract,
    apply_databricks_access_bundle,
    apply_databricks_annotations_bundle,
    apply_databricks_governance_bundle,
    apply_governance_contract,
    apply_shape,
    build_control_retention_plan,
    build_operational_cost_report,
    check_governance_contract,
    choose_write_strategy,
    detect_databricks_capabilities,
    deploy_databricks_bundle,
    deploy_databricks_project,
    evaluate_databricks_capabilities,
    evaluate_lakeflow_compatibility,
    execute_control_retention_plan,
    get_quality_rule,
    get_source_resolver,
    get_write_engine_parity_scenario,
    get_write_mode,
    governance_referenced_columns,
    ingest_databricks_bundle,
    ingest_databricks_contract,
    list_quality_rules,
    list_source_resolvers,
    list_write_engine_parity_scenarios,
    list_write_modes,
    plan_databricks_contract,
    register_preset,
    register_quality_rule,
    register_source_resolver,
    register_write_mode,
    render_access_sql,
    render_databricks_contract,
    render_governance_sql,
    render_lakeflow_auto_cdc_artifact,
    render_operational_cost_query,
    resolve_source_dataframe,
    run_available_now_stream,
    scenarios_for_engine,
    scenarios_for_mode,
    uc_capability_issues,
    unregister_quality_rule,
    unregister_source_resolver,
    unregister_write_mode,
    validate_governance_contract,
)


def test_plan_databricks_contract_from_mapping() -> None:
    result = plan_databricks_contract(
        {
            "source": {"type": "connector", "connector": "postgres"},
            "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
        },
        runtime_type="serverless",
        spark_conf={"spark.databricks.serverless.enabled": "true"},
    )

    assert result.status == "SUPPORTED"


def test_render_databricks_contract_from_mapping() -> None:
    artifacts = render_databricks_contract(
        {
            "source": {"type": "incremental_files", "path": "s3://bucket/orders", "format": "json"},
            "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
        },
        runtime_type="serverless",
        spark_conf={"spark.databricks.serverless.enabled": "true"},
    )

    assert "main_bronze_orders.review.md" in artifacts.artifacts
    assert "main_bronze_orders.source_autoloader.py" in artifacts.artifacts


def test_render_databricks_contract_accepts_environment() -> None:
    artifacts = render_databricks_contract(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
        },
        environment={"name": "prod", "adapter": "databricks", "evidence": {"catalog": "ops", "schema": "audit"}},
    )

    assert "`ops`.`audit`.`ctrl_ingestion_runs`" in artifacts.artifacts["main_bronze_orders.evidence_ddl.sql"]
    assert "ops.audit.ctrl_ingestion_runs" in artifacts.artifacts["main_bronze_orders.control_table_migrations.sql"]


def test_render_databricks_contract_accepts_adapter_extension_fields() -> None:
    artifacts = render_databricks_contract(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"catalog": "main", "schema": "silver", "table": "orders"},
            "mode": "scd1_upsert",
            "merge_keys": ["order_id"],
            "extensions": {
                "databricks": {
                    "cluster_columns": ["order_id"],
                    "write_engine": {"requested": "lakeflow_auto_cdc", "fallback_policy": "preview_only"},
                }
            },
        },
        runtime_type="serverless",
        spark_conf={"spark.databricks.serverless.enabled": "true"},
    )

    review = artifacts.artifacts["main_silver_orders.review.md"]

    assert "## Databricks Extensions" in review
    assert "cluster_columns" in review
    assert "write_engine" in review


def test_render_databricks_contract_redacts_adapter_extension_values() -> None:
    artifacts = render_databricks_contract(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
            "extensions": {"databricks": {"openlineage_producer": "https://u:secret@example.com/producer"}},
        },
        runtime_type="serverless",
        spark_conf={"spark.databricks.serverless.enabled": "true"},
    )

    review = artifacts.artifacts["main_bronze_orders.review.md"]

    assert "openlineage_producer" in review
    assert "secret" not in review
    assert "***REDACTED***" in review


def test_public_api_exposes_lakeflow_review_artifact() -> None:
    contract = {
        "source": {"type": "table", "table": "main.raw.orders_cdc"},
        "target": {"catalog": "main", "schema": "silver", "table": "orders"},
        "mode": "scd1_upsert",
        "merge_keys": ["order_id"],
    }
    semantic = semantic_contract_from_mapping(contract)

    compatibility = evaluate_lakeflow_compatibility(
        semantic,
        source_name="live.orders_cdc",
        keys=("order_id",),
        sequence_by="event_ts",
    )
    artifact = render_lakeflow_auto_cdc_artifact(
        semantic,
        source_name="live.orders_cdc",
        keys=("order_id",),
        sequence_by="event_ts",
    )

    assert compatibility.status == "compatible"
    assert artifact.compatibility.target_table == "main.silver.orders"


def test_public_api_exposes_runtime_capability_detection() -> None:
    caps = detect_databricks_capabilities("main.silver.orders")

    assert caps.target_table == "main.silver.orders"
    assert "databricks_runtime" in caps.capabilities
    assert callable(evaluate_databricks_capabilities)


def test_public_api_exposes_preset_registration() -> None:
    assert callable(register_preset)


def test_public_api_exposes_source_resolver_registry() -> None:
    assert callable(register_source_resolver)
    assert callable(get_source_resolver)
    assert callable(list_source_resolvers)
    assert callable(unregister_source_resolver)


def test_public_api_exposes_runtime_registries() -> None:
    assert callable(register_quality_rule)
    assert callable(get_quality_rule)
    assert callable(list_quality_rules)
    assert callable(unregister_quality_rule)
    assert callable(register_write_mode)
    assert callable(get_write_mode)
    assert callable(list_write_modes)
    assert callable(unregister_write_mode)


def test_public_api_exposes_canonical_write_engine_parity_helpers() -> None:
    assert callable(get_write_engine_parity_scenario)
    assert callable(list_write_engine_parity_scenarios)
    assert callable(scenarios_for_engine)
    assert callable(scenarios_for_mode)


def test_public_api_exposes_canonical_write_strategy_selection() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
        }
    )

    caps = DatabricksCapabilities(
        runtime_kind="databricks_serverless",
        target_table="main.bronze.orders",
        spark_version=None,
        capabilities={"delta_tables": capability("delta_tables", "supported", "test")},
    )

    decision = choose_write_strategy(contract, caps)

    assert decision.executable
    assert decision.engine == "delta_append"


def test_public_api_exposes_governance_runtime_helpers() -> None:
    assert callable(access_drift_report)
    assert callable(apply_access_contract)
    assert callable(apply_governance_contract)
    assert callable(check_governance_contract)
    assert callable(governance_referenced_columns)
    assert callable(render_access_sql)
    assert callable(render_governance_sql)
    assert callable(validate_governance_contract)


def test_public_api_exposes_canonical_cost_maintenance_and_uc_helpers() -> None:
    assert callable(build_operational_cost_report)
    assert callable(render_operational_cost_query)
    assert callable(build_control_retention_plan)
    assert callable(execute_control_retention_plan)
    assert uc_capability_issues("orders", [("row_filters", "table", "orders", "ERROR")])
    assert not uc_capability_issues("main.silver.orders", [("row_filters", "table", "orders", "ERROR")])


def test_public_api_exposes_databricks_bundle_execution_helpers() -> None:
    assert apply_databricks_access_bundle is not None
    assert apply_databricks_annotations_bundle is not None
    assert apply_databricks_governance_bundle is not None
    assert callable(deploy_databricks_bundle)
    assert callable(deploy_databricks_project)
    assert callable(ingest_databricks_bundle)
    assert callable(ingest_databricks_contract)
    assert callable(run_available_now_stream)


def test_public_api_exposes_databricks_shape_and_source_runtime_helpers() -> None:
    assert callable(apply_shape)
    assert callable(resolve_source_dataframe)
