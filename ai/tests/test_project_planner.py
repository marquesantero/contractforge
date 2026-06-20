from contractforge_ai.planning import ProjectPlannerRequest, plan_project_from_intent


def test_plan_project_from_complete_intent_recommends_reviewable_targets():
    result = plan_project_from_intent(
        ProjectPlannerRequest(
            intent=(
                "Create a Databricks silver ingestion project from s3a://landing/orders "
                "into main.silver.orders using scd1_hash_diff. Owner data-team."
            ),
            schema_path="schemas/orders.json",
        )
    )

    assert result.status == "NEEDS_DECISIONS"
    assert result.intent.connector == "s3"
    assert result.intent.source_path == "s3a://landing/orders"
    assert result.intent.target_catalog == "main"
    assert result.intent.target_schema == "silver"
    assert result.intent.target_table == "orders"
    assert result.intent.project_name == "Orders"
    assert result.intent.layer == "silver"
    assert result.intent.mode == "hash_diff_upsert"
    assert "databricks" in result.intent.platform_hints
    assert "aws" not in result.intent.platform_hints
    assert any(item.target == "contractforge-yaml" for item in result.recommendations)
    assert any(item.target == "databricks-dab" for item in result.recommendations)
    assert not any(item.target == "aws-glue-iceberg" for item in result.recommendations)
    assert any(decision.path == "merge_keys" for decision in result.decisions_required)


def test_plan_project_from_ambiguous_intent_reports_missing_decisions():
    result = plan_project_from_intent(
        ProjectPlannerRequest(
            intent="Ingest customer data from an API into the lakehouse.",
            default_catalog="main",
            default_schema="bronze",
        )
    )

    assert result.status == "NEEDS_DECISIONS"
    assert result.intent.connector == "rest_api"
    assert result.intent.target_catalog == "main"
    assert result.intent.target_schema == "bronze"
    assert "source_path" in result.intent.missing_fields
    assert "target_table" in result.intent.missing_fields
    assert "schema_path" in result.intent.missing_fields
    assert all("<source-path>" in item.command for item in result.recommendations)


def test_plan_project_uses_preferred_target_when_supported():
    result = plan_project_from_intent(
        ProjectPlannerRequest(
            intent="Build a gold overwrite table from Snowflake SALES.ORDERS to analytics.gold.g_orders.",
            schema_path="schemas/orders.json",
            preferred_target="dbt",
        )
    )

    assert [item.target for item in result.recommendations] == ["dbt"]
    assert result.intent.connector == "snowflake_jdbc"
    assert result.intent.layer == "gold"
    assert result.intent.mode == "overwrite"


def test_plan_project_does_not_use_source_phrase_as_project_name():
    result = plan_project_from_intent(
        ProjectPlannerRequest(
            intent=(
                "Create a Databricks Asset Bundle project for a silver ContractForge ingestion "
                "from s3a://landing/orders_complex into main.silver.s_orders_complex using scd1_hash_diff."
            ),
            schema_path="schemas/orders.json",
            preferred_target="databricks-dab",
        )
    )

    assert result.intent.project_name == "S Orders Complex"
    assert "from s3a" not in result.recommendations[0].command
    assert '--project-name "S Orders Complex"' in result.recommendations[0].command


def test_plan_project_uses_explicit_named_project():
    result = plan_project_from_intent(
        ProjectPlannerRequest(
            intent=(
                "Create a project named Customer Orders Lakeflow from abfss://landing/orders "
                "into main.bronze.b_orders."
            ),
            schema_path="schemas/orders.json",
        )
    )

    assert result.intent.project_name == "Customer Orders Lakeflow"


def test_plan_project_for_aws_glue_s3_avoids_databricks_bundle_recommendation():
    result = plan_project_from_intent(
        ProjectPlannerRequest(
            intent=(
                "Create an AWS Glue bronze ingestion project from s3://landing/orders "
                "into analytics.bronze.b_orders using scd0_append."
            ),
            schema_path="schemas/orders.json",
        )
    )

    targets = {item.target for item in result.recommendations}

    assert "aws" in result.intent.platform_hints
    assert "databricks" not in result.intent.platform_hints
    assert "contractforge-yaml" in targets
    assert "aws-glue-iceberg" in targets
    assert "contractforge-python" in targets
    assert "databricks-dab" not in targets
    assert any("AWS Glue Spark and Iceberg" in item.reason for item in result.recommendations if item.target == "aws-glue-iceberg")


def test_plan_project_maps_each_stable_platform_to_its_adapter_target():
    cases = [
        (
            "Create a Snowflake bronze project from https://example.com/orders.json into analytics.bronze.b_orders.",
            "snowflake",
            "snowflake-sql-warehouse",
        ),
        (
            "Create a Fabric bronze project from abfss://landing/orders into analytics.bronze.b_orders.",
            "fabric",
            "fabric-lakehouse",
        ),
        (
            "Create a GCP BigQuery bronze project from gs://landing/orders.csv into analytics.bronze.b_orders.",
            "gcp",
            "gcp-bigquery",
        ),
    ]

    for intent, platform, target in cases:
        result = plan_project_from_intent(ProjectPlannerRequest(intent=intent, schema_path="schemas/orders.json"))
        targets = {item.target for item in result.recommendations}

        assert platform in result.intent.platform_hints
        assert target in targets
        assert "contractforge-yaml" in targets


def test_plan_project_for_neutral_s3_recommends_supported_adapter_paths():
    result = plan_project_from_intent(
        ProjectPlannerRequest(
            intent=(
                "Create a bronze ingestion project from s3://landing/orders "
                "into analytics.bronze.b_orders using scd0_append."
            ),
            schema_path="schemas/orders.json",
        )
    )

    targets = [item.target for item in result.recommendations]

    assert result.intent.platform_hints == []
    assert "contractforge-yaml" in targets
    assert "databricks-dab" in targets
    assert "aws-glue-iceberg" in targets


def test_plan_project_trims_explicit_name_before_source_clause():
    result = plan_project_from_intent(
        ProjectPlannerRequest(
            intent=(
                "Create a project named Customer Orders from https://example.com/orders.csv "
                "into main.bronze.b_orders."
            ),
            schema_path="schemas/orders.json",
        )
    )

    assert result.intent.project_name == "Customer Orders"


def test_plan_project_maps_autoloader_to_portable_incremental_files():
    result = plan_project_from_intent(
        ProjectPlannerRequest(
            intent=(
                "Create a Databricks bronze project with Auto Loader from s3://landing/orders "
                "into main.bronze.b_orders."
            ),
            schema_path="schemas/orders.json",
        )
    )

    assert result.intent.connector == "incremental_files"
    assert "databricks" in result.intent.platform_hints


def test_plan_project_maps_kafka_to_bounded_core_connector():
    result = plan_project_from_intent(
        ProjectPlannerRequest(
            intent="Create bronze ingestion from Kafka topic orders into main.bronze.b_orders.",
            schema_path="schemas/orders.json",
        )
    )

    assert result.intent.connector == "kafka_bounded"
    assert any("bounded stream" in signal.lower() for signal in result.intent.signals)


def test_plan_project_adds_core_support_message_for_uri_connectors():
    result = plan_project_from_intent(
        ProjectPlannerRequest(
            intent="Create an AWS ingestion from s3://landing/customers into bronze.customers",
            preferred_target="aws-glue-iceberg",
        )
    )

    assert result.intent.connector == "s3"
    assert "connector_supported_by_core:true" in result.intent.signals
    assert any("Supported by ContractForge Core" in signal for signal in result.intent.signals)


def test_plan_project_expands_aws_native_connector_to_passthrough():
    result = plan_project_from_intent(
        ProjectPlannerRequest(
            intent=(
                "Create an AWS ingestion from AppFlow Salesforce into analytics.bronze.b_accounts "
                "with minimal differences."
            ),
            schema_path="schemas/accounts.json",
        )
    )

    assert result.intent.connector == "native_passthrough"
    assert result.intent.source_system == "salesforce"
    assert "connector_supported_by_core:true" in result.intent.signals
    assert any("AppFlow is AWS-specific" in signal for signal in result.intent.signals)
    assert any(item.target == "aws-glue-iceberg" for item in result.recommendations)


def test_plan_project_expands_adls_without_collapsing_to_azure_blob():
    result = plan_project_from_intent(
        ProjectPlannerRequest(
            intent="Create Databricks bronze ingestion from Azure Data Lake into main.bronze.b_events.",
            schema_path="schemas/events.json",
        )
    )

    assert result.intent.connector == "adls"
    assert any("source type `adls`" in signal for signal in result.intent.signals)


def test_plan_project_extracts_prompt_intent_without_guessing():
    result = plan_project_from_intent(
        ProjectPlannerRequest(
            intent=(
                "Create Supabase medallion for AWS and Databricks daily at 6 Sao Paulo time. "
                "Source system: supabase. Use postgres JDBC from jdbc:postgresql://db.example/postgres "
                "into analytics.bronze.b_orders. Require PII masking, row filters, evidence, "
                "minimal differences between platforms, and freshness target 30 minutes."
            ),
            schema_path="schemas/orders.json",
        )
    )

    assert result.intent.connector == "postgres"
    assert result.intent.source_system == "supabase"
    assert result.intent.schedule_cron == "0 6 * * *"
    assert result.intent.schedule_timezone == "America/Sao_Paulo"
    assert result.intent.freshness == "near_real_time"
    assert result.intent.latency_target == "30 minutes"
    assert result.intent.portability_priority == "high"
    assert result.intent.governance == {
        "column_masks_required": True,
        "evidence_required": True,
        "pii": True,
        "row_filters_required": True,
    }
    assert {"aws", "databricks"}.issubset(set(result.intent.platform_hints))
    assert not any(decision.path == "schedule.timezone" for decision in result.decisions_required)


def test_plan_project_requires_timezone_for_scheduled_prompt():
    result = plan_project_from_intent(
        ProjectPlannerRequest(
            intent=(
                "Create AWS bronze ingestion daily at 6 from s3://landing/orders "
                "into analytics.bronze.b_orders."
            ),
            schema_path="schemas/orders.json",
        )
    )

    assert result.intent.schedule_cron == "0 6 * * *"
    assert result.intent.schedule_timezone is None
    assert any(decision.path == "schedule.timezone" for decision in result.decisions_required)
