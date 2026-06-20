import json
import sys

import pytest

import contractforge_aws.runtime.glue_wait as glue_wait_runtime
from contractforge_aws import (
    AWSAdapter,
    deploy_aws_contract_to_glue,
    get_aws_glue_job_run_status,
    list_aws_subtargets,
    plan_aws_contract,
    publish_aws_contract_artifacts_to_s3,
    reconcile_aws_glue_job_run_evidence,
    register_aws_glue_job,
    register_aws_glue_job_definition_payload,
    render_aws_contract,
    render_aws_glue_job_run_evidence_sql,
    start_aws_glue_job_run,
    wait_aws_glue_job_run,
)
from contractforge_aws.capabilities import AWS_SUBTARGET_GLUE_ICEBERG, glue_iceberg_capabilities
from contractforge_aws.evidence import (
    glue_job_run_evidence,
    render_create_evidence_tables_sql,
    render_glue_run_evidence_sql,
    render_create_state_tables_sql,
)
from contractforge_aws.runtime import GlueJobDefinition, build_glue_job_payload, publish_rendered_artifacts_to_s3
from contractforge_aws.runtime.dependencies import require_boto3


def test_aws_glue_iceberg_capabilities_declare_reference_target() -> None:
    capabilities = glue_iceberg_capabilities()

    assert capabilities.platform == AWS_SUBTARGET_GLUE_ICEBERG
    assert capabilities.supports_append
    assert capabilities.supports_overwrite
    assert capabilities.supports_merge
    assert capabilities.supports_hash_diff
    assert capabilities.evidence_stores == ("iceberg_table",)
    assert "row_filters" in capabilities.review_required_semantics


def test_aws_public_subtarget_registry_lists_reference_target() -> None:
    assert list_aws_subtargets() == (AWS_SUBTARGET_GLUE_ICEBERG,)


def test_aws_plan_supports_simple_append_contract() -> None:
    result = plan_aws_contract(
        {
            "source": {"type": "s3", "path": "s3://landing/customers", "format": "parquet"},
            "target": {"catalog": "lake", "schema": "bronze", "table": "customers"},
            "mode": "scd0_append",
        }
    )

    assert result.status == "SUPPORTED"
    assert result.plan is not None
    assert result.plan.platform == AWS_SUBTARGET_GLUE_ICEBERG


def test_aws_plan_warns_for_unknown_adapter_extensions() -> None:
    result = plan_aws_contract(
        {
            "source": {"type": "s3", "path": "s3://landing/customers", "format": "parquet"},
            "target": {"catalog": "lake", "schema": "bronze", "table": "customers"},
            "mode": "scd0_append",
            "extensions": {"aws": {"unknown_feature": True}},
        }
    )

    assert result.status == "SUPPORTED_WITH_WARNINGS"
    assert "AWS_UNKNOWN_EXTENSION" in {warning.code for warning in result.warnings}


def test_aws_plan_accepts_known_adapter_extensions_without_warning() -> None:
    result = plan_aws_contract(
        {
            "source": {"type": "s3", "path": "s3://landing/customers", "format": "parquet"},
            "target": {"catalog": "lake", "schema": "bronze", "table": "customers"},
            "mode": "scd0_append",
            "extensions": {"aws": {"glue_job": {"worker_type": "G.1X"}}},
        }
    )

    assert "AWS_UNKNOWN_EXTENSION" not in {warning.code for warning in result.warnings}


def test_aws_plan_warns_for_unknown_nested_adapter_extension_fields() -> None:
    result = plan_aws_contract(
        {
            "source": {"type": "s3", "path": "s3://landing/customers", "format": "parquet"},
            "target": {"catalog": "lake", "schema": "bronze", "table": "customers"},
            "mode": "scd0_append",
            "extensions": {"aws": {"glue_job": {"worker_tpye": "G.2X"}}},
        }
    )

    assert result.status == "SUPPORTED_WITH_WARNINGS"
    assert "AWS_UNKNOWN_EXTENSION_FIELD" in {warning.code for warning in result.warnings}
    assert any("extensions.aws.glue_job.worker_tpye" in warning.message for warning in result.warnings)


def test_aws_plan_warns_for_wrong_adapter_extension_shape() -> None:
    result = plan_aws_contract(
        {
            "source": {"type": "s3", "path": "s3://landing/customers", "format": "parquet"},
            "target": {"catalog": "lake", "schema": "bronze", "table": "customers"},
            "mode": "scd0_append",
            "extensions": {"aws": {"glue_job": "use-big-workers"}},
        }
    )

    assert result.status == "SUPPORTED_WITH_WARNINGS"
    assert "AWS_EXTENSION_SHAPE_IGNORED" in {warning.code for warning in result.warnings}


def test_aws_plan_ignores_other_adapter_extension_blocks() -> None:
    result = plan_aws_contract(
        {
            "source": {"type": "s3", "path": "s3://landing/customers", "format": "parquet"},
            "target": {"catalog": "lake", "schema": "bronze", "table": "customers"},
            "mode": "scd0_append",
            "extensions": {"databricks": {"unknown_feature": True}},
        }
    )

    assert "AWS_UNKNOWN_EXTENSION" not in {warning.code for warning in result.warnings}


def test_aws_hash_diff_is_supported_with_performance_warning() -> None:
    result = plan_aws_contract(
        {
            "source": {"type": "jdbc", "table": "public.customers"},
            "target": {"catalog": "lake", "schema": "silver", "table": "customers"},
            "mode": "scd1_hash_diff",
            "merge_keys": ["customer_id"],
            "hash_keys": ["name", "email"],
        }
    )

    assert result.status == "SUPPORTED_WITH_WARNINGS"
    assert "AWS_HASH_DIFF_PERFORMANCE_UNVALIDATED" in {warning.code for warning in result.warnings}


def test_aws_hash_diff_requires_merge_keys_at_planning_boundary() -> None:
    result = plan_aws_contract(
        {
            "source": {"type": "jdbc", "table": "public.customers"},
            "target": {"catalog": "lake", "schema": "silver", "table": "customers"},
            "mode": "scd1_hash_diff",
            "hash_keys": ["name", "email"],
        }
    )

    assert result.status == "UNSUPPORTED"
    assert result.plan is None
    assert "AWS_HASH_DIFF_MERGE_KEYS_REQUIRED" in {blocker.code for blocker in result.blockers}


def test_aws_hash_diff_all_columns_except_strategy_plans_without_hash_keys() -> None:
    result = plan_aws_contract(
        {
            "source": {"type": "jdbc", "table": "public.customers"},
            "target": {"catalog": "lake", "schema": "silver", "table": "customers"},
            "mode": "scd1_hash_diff",
            "merge_keys": ["customer_id"],
            "hash_strategy": "all_columns_except",
            "hash_exclude_columns": ["updated_at"],
        }
    )

    assert result.status == "SUPPORTED_WITH_WARNINGS"
    assert "AWS_HASH_DIFF_PERFORMANCE_UNVALIDATED" in {warning.code for warning in result.warnings}


def test_aws_row_filters_require_review() -> None:
    result = plan_aws_contract(
        {
            "source": {"type": "s3", "path": "s3://landing/customers", "format": "parquet"},
            "target": {"catalog": "lake", "schema": "silver", "table": "customers"},
            "mode": "scd0_append",
            "access": {
                "row_filters": [
                    {
                        "name": "country_filter",
                        "function": "security.country_filter",
                        "columns": ["country"],
                    }
                ]
            },
        }
    )

    assert result.status == "REVIEW_REQUIRED"
    assert "REVIEW_REQUIRED" in {warning.code for warning in result.warnings}


def test_aws_expression_quality_is_supported_with_warning() -> None:
    result = plan_aws_contract(
        {
            "source": {"type": "s3", "path": "s3://landing/customers", "format": "parquet"},
            "target": {"catalog": "lake", "schema": "silver", "table": "customers"},
            "mode": "scd0_append",
            "quality_rules": {
                "expressions": [
                    {"name": "positive_amount", "expression": "amount > 0", "severity": "quarantine"}
                ]
            },
        }
    )

    assert result.status == "SUPPORTED_WITH_WARNINGS"
    assert "AWS_EXPRESSION_QUALITY_SPARK_SQL" in {warning.code for warning in result.warnings}
    assert not any(warning.code == "REVIEW_REQUIRED" for warning in result.warnings)


def test_aws_rejects_databricks_autoloader_source() -> None:
    result = plan_aws_contract(
        {
            "source": {"type": "autoloader", "path": "s3://landing/orders", "format": "json"},
            "target": {"catalog": "lake", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
        }
    )

    assert result.status == "UNSUPPORTED"
    assert result.plan is None
    assert [blocker.code for blocker in result.blockers] == ["AWS_SOURCE_AUTOLOADER_UNSUPPORTED"]


def test_aws_available_now_generic_provider_is_supported_with_warning() -> None:
    result = plan_aws_contract(
        {
            "source": {
                "type": "kafka_available_now",
                "bootstrap_servers": "broker:9092",
                "topic": "events",
                "checkpoint_location": "s3://state/events",
            },
            "target": {"catalog": "lake", "schema": "bronze", "table": "events"},
            "mode": "scd0_append",
        }
    )

    assert result.status == "SUPPORTED_WITH_WARNINGS"
    assert "AWS_AVAILABLE_NOW_STREAMING_PROVIDER_REVIEW" in {warning.code for warning in result.warnings}


def test_aws_available_now_eventhubs_kafka_path_is_validated() -> None:
    result = plan_aws_contract(
        {
            "source": {
                "type": "kafka_available_now",
                "system": "azure_eventhubs",
                "bootstrap_servers": "namespace.servicebus.windows.net:9093",
                "topic": "events",
                "checkpoint_location": "s3://state/events",
            },
            "target": {"catalog": "lake", "schema": "bronze", "table": "events"},
            "mode": "scd0_append",
        }
    )

    assert result.status == "SUPPORTED"
    assert "AWS_AVAILABLE_NOW_STREAMING_PROVIDER_REVIEW" not in {warning.code for warning in result.warnings}


def test_aws_runtime_config_sources_are_supported_with_warning() -> None:
    result = plan_aws_contract(
        {
            "source": {"type": "gcs", "path": "gs://landing/customers", "format": "json"},
            "target": {"catalog": "lake", "schema": "bronze", "table": "customers"},
            "mode": "scd0_append",
        }
    )

    assert result.status == "SUPPORTED_WITH_WARNINGS"
    assert "AWS_SOURCE_RUNTIME_CONFIG_REQUIRED" in {warning.code for warning in result.warnings}


def test_aws_connector_package_sources_are_supported_with_warning() -> None:
    result = plan_aws_contract(
        {
            "source": {"type": "kafka_bounded", "bootstrap_servers": "broker:9092", "topic": "events"},
            "target": {"catalog": "lake", "schema": "bronze", "table": "events"},
            "mode": "scd0_append",
        }
    )

    assert result.status == "SUPPORTED_WITH_WARNINGS"
    assert "AWS_SOURCE_CONNECTOR_PACKAGE_REQUIRED" in {warning.code for warning in result.warnings}


def test_aws_render_contract_returns_review_artifacts() -> None:
    artifacts = render_aws_contract(
        {
            "source": {"type": "s3", "path": "s3://landing/orders", "format": "json"},
            "target": {"catalog": "lake", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
        }
    )

    assert "lake_bronze_orders.review.md" in artifacts.artifacts
    assert "lake_bronze_orders.capabilities.json" in artifacts.artifacts
    assert "lake_bronze_orders.evidence_ddl.sql" in artifacts.artifacts
    assert "lake_bronze_orders.state_ddl.sql" in artifacts.artifacts
    assert "lake_bronze_orders.cost.sql" in artifacts.artifacts
    assert "lake_bronze_orders.iam_policy.json" in artifacts.artifacts
    assert "lake_bronze_orders.glue_job.py" in artifacts.artifacts
    assert "AWS Glue Iceberg Planning Review" in artifacts.artifacts["lake_bronze_orders.review.md"]
    glue_job = artifacts.artifacts["lake_bronze_orders.glue_job.py"]
    assert "from awsglue.context import GlueContext" in glue_job
    assert ".format('json')" in glue_job
    assert ".load('s3://landing/orders')" in glue_job
    assert "_cf_target_schema_for_write = _cf_describe_table_schema(spark, target_table)" in glue_job
    assert "if not _cf_target_schema_for_write:" in glue_job
    assert "_cf_writer = df.writeTo(target_table).using('iceberg')" in glue_job
    assert "_cf_writer.create()" in glue_job
    assert ".append()" in glue_job
    assert "glue_catalog.lake_bronze.orders" in glue_job
    assert glue_job.index("try:") < glue_job.index("CREATE DATABASE IF NOT EXISTS glue_catalog.`lake_bronze`")
    assert glue_job.index("CREATE DATABASE IF NOT EXISTS glue_catalog.`lake_bronze`") < glue_job.index("# Read source intent.")
    compile(glue_job, "lake_bronze_orders.glue_job.py", "exec")
    capabilities = json.loads(artifacts.artifacts["lake_bronze_orders.capabilities.json"])
    source_support = {item["source_type"]: item for item in capabilities["source_support"]}
    assert source_support["parquet"]["status"] == "SUPPORTED"
    assert source_support["delta"]["status"] == "SUPPORTED_WITH_WARNINGS"


def test_aws_render_contract_resolves_logical_catalog_refs() -> None:
    artifacts = render_aws_contract(
        {
            "source": {"type": "sql", "query": "select * from {{ table_ref:bronze.orders }}"},
            "target": {"catalog": "lake", "schema": "silver", "table": "orders_curated"},
            "layer": "silver",
            "mode": "scd0_overwrite",
        }
    )

    glue_job = artifacts.artifacts["lake_silver_orders_curated.glue_job.py"]

    assert "select * from glue_catalog.lake_bronze.orders" in glue_job
    assert "{{ table_ref:" not in glue_job
    compile(glue_job, "lake_silver_orders_curated.glue_job.py", "exec")


def test_aws_render_contract_redacts_adapter_extension_values() -> None:
    artifacts = render_aws_contract(
        {
            "source": {"type": "s3", "path": "s3://landing/orders", "format": "json"},
            "target": {"catalog": "lake", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
            "extensions": {"aws": {"glue_job": {"secret_argument": "super-secret"}}},
        }
    )

    review = artifacts.artifacts["lake_bronze_orders.review.md"]

    assert "## AWS Extensions" in review
    assert "secret_argument" in review
    assert "super-secret" not in review
    assert "***REDACTED***" in review


def test_aws_evidence_ddl_uses_core_control_table_schema() -> None:
    evidence_sql = render_create_evidence_tables_sql(database="ops")
    state_sql = render_create_state_tables_sql(database="ops")

    assert "CREATE DATABASE IF NOT EXISTS glue_catalog.`ops`" in evidence_sql
    assert "CREATE TABLE IF NOT EXISTS glue_catalog.`ops`.`ctrl_ingestion_runs`" in evidence_sql
    assert "`source_system` STRING" in evidence_sql
    assert "`metrics_json` STRING" in evidence_sql
    assert "USING iceberg" in evidence_sql
    assert "PARTITIONED BY (`run_date`)" in evidence_sql
    assert "CREATE TABLE IF NOT EXISTS glue_catalog.`ops`.`ctrl_ingestion_state`" in state_sql
    assert "`last_table_version` STRING" in state_sql


def test_aws_render_overwrite_uses_create_or_replace() -> None:
    artifacts = render_aws_contract(
        {
            "source": {"type": "parquet", "path": "s3://landing/products"},
            "target": {"catalog": "lake", "schema": "bronze", "table": "products"},
            "mode": "scd0_overwrite",
        }
    )

    glue_job = artifacts.artifacts["lake_bronze_products.glue_job.py"]

    assert ".format('parquet')" in glue_job
    assert "_cf_writer.createOrReplace()" in glue_job


def test_aws_render_applies_iceberg_table_properties_on_create_paths() -> None:
    artifacts = render_aws_contract(
        {
            "source": {"type": "parquet", "path": "s3://landing/products"},
            "target": {"catalog": "lake", "schema": "bronze", "table": "products"},
            "mode": "scd0_append",
            "extensions": {
                "aws": {
                    "iceberg": {
                        "table_properties": {
                            "format-version": "2",
                            "write.format.default": "parquet",
                        }
                    }
                }
            },
        }
    )

    glue_job = artifacts.artifacts["lake_bronze_products.glue_job.py"]

    assert "_cf_table_properties = {'format-version': '2', 'write.format.default': 'parquet'}" in glue_job
    assert "_cf_writer = _cf_writer.tableProperty(str(_cf_property_name), str(_cf_property_value))" in glue_job
    assert "_cf_writer.create()" in glue_job
    compile(glue_job, "lake_bronze_products.glue_job.py", "exec")


def test_aws_render_sets_iceberg_warehouse_extension() -> None:
    artifacts = render_aws_contract(
        {
            "source": {"type": "json", "path": "s3://landing/orders"},
            "target": {"catalog": "lake", "schema": "bronze", "table": "orders"},
            "mode": "scd0_overwrite",
            "extensions": {"aws": {"iceberg": {"warehouse": "s3://lakehouse/warehouse/"}}},
        }
    )

    glue_job = artifacts.artifacts["lake_bronze_orders.glue_job.py"]

    assert "spark.sql.catalog.glue_catalog.warehouse" in glue_job
    assert "s3://lakehouse/warehouse/" in glue_job
    assert "CREATE DATABASE IF NOT EXISTS glue_catalog.`lake_bronze` LOCATION 's3://lakehouse/warehouse/lake_bronze.db/'" in glue_job
    compile(glue_job, "lake_bronze_orders.glue_job.py", "exec")


def test_aws_render_scd1_upsert_uses_iceberg_merge_with_key_guards() -> None:
    artifacts = render_aws_contract(
        {
            "source": {"type": "jdbc", "url": "jdbc:postgresql://host/db", "table": "public.customers"},
            "target": {"catalog": "lake", "schema": "silver", "table": "customers"},
            "mode": "scd1_upsert",
            "merge_keys": ["customer_id"],
        }
    )

    glue_job = artifacts.artifacts["lake_silver_customers.glue_job.py"]

    assert "MERGE INTO {target_table} AS target" in glue_job
    assert "merge_keys = ['customer_id']" in glue_job
    assert "Missing merge_keys in source DataFrame" in glue_job
    assert "contains null merge_keys" in glue_job
    assert "contains duplicate merge_keys" in glue_job
    assert "_cf_target_schema_for_write = _cf_describe_table_schema(spark, target_table)" in glue_job
    assert "if not _cf_target_schema_for_write:" in glue_job
    assert "_cf_writer.create()" in glue_job
    assert "WHEN MATCHED THEN UPDATE SET {assignments}" in glue_job
    assert "WHEN NOT MATCHED THEN INSERT ({insert_columns}) VALUES ({insert_values})" in glue_job
    compile(glue_job, "lake_silver_customers.glue_job.py", "exec")


def test_aws_render_abortive_quality_checks_in_glue_job() -> None:
    artifacts = render_aws_contract(
        {
            "source": {"type": "parquet", "path": "s3://landing/orders"},
            "target": {"catalog": "lake", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
            "quality_rules": {
                "required_columns": ["order_id", "customer_id"],
                "unique_key": ["order_id"],
                "min_rows": 1,
            },
        }
    )

    glue_job = artifacts.artifacts["lake_bronze_orders.glue_job.py"]

    # Abort-severity rules are evaluated natively by Glue Data Quality and raise on failure.
    assert "from awsgluedq.transforms import EvaluateDataQuality" in glue_job
    assert "# Quality rules with 'abort' enforcement." in glue_job
    assert "EvaluateDataQuality.apply(" in glue_job
    assert "raise ValueError('Data quality (abort) failed: '" in glue_job
    assert "_cf_persist_quality_evidence(spark, 'glue_catalog.`lake_bronze_ops`.`ctrl_ingestion_quality`'" in glue_job
    assert ".append()" in glue_job
    compile(glue_job, "lake_bronze_orders.glue_job.py", "exec")


def test_aws_render_portable_preparation_in_glue_job() -> None:
    artifacts = render_aws_contract(
        {
            "source": {"type": "parquet", "path": "s3://landing/orders"},
            "target": {"catalog": "lake", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
            "select_columns": ["id", "amount", "is_valid"],
            "column_mapping": {"id": "order_id"},
            "filter_expression": "amount > 0 AND is_valid = true",
        }
    )

    glue_job = artifacts.artifacts["lake_bronze_orders.glue_job.py"]

    assert "select_columns = ['id', 'amount', 'is_valid']" in glue_job
    assert "column_mapping = {'id': 'order_id'}" in glue_job
    assert "filter_expression = 'amount > 0 AND is_valid = true'" in glue_job
    assert ".select(*select_columns)" in glue_job
    assert ".withColumnRenamed(source_column, target_column)" in glue_job
    assert ".where(filter_expression)" in glue_job
    assert ".append()" in glue_job
    compile(glue_job, "lake_bronze_orders.glue_job.py", "exec")


def test_aws_render_preparation_matches_databricks_order() -> None:
    artifacts = render_aws_contract(
        {
            "source": {"type": "parquet", "path": "s3://landing/orders"},
            "target": {"catalog": "lake", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
            "select_columns": ["raw"],
            "transform": {
                "shape": {
                    "columns": {
                        "raw": {"alias": "raw"},
                        "id": {"alias": "id", "expression": "get_json_object(raw, '$.id')"},
                    }
                },
                "derive": {"is_valid": "id IS NOT NULL"},
                "deduplicate": {
                    "keys": ["id"],
                    "order_by": [{"column": "id", "direction": "desc"}],
                },
            },
            "filter_expression": "is_valid = true",
        }
    )

    glue_job = artifacts.artifacts["lake_bronze_orders.glue_job.py"]

    select_at = glue_job.index("df = df.select(*select_columns)")
    shape_at = glue_job.index("df = df.select(", select_at + 1)
    derive_at = glue_job.index("transform_derive =")
    filter_at = glue_job.index("filter_expression = 'is_valid = true'")
    dedup_at = glue_job.index("deduplicate_keys = ['id']")
    assert select_at < shape_at < derive_at < filter_at < dedup_at
    compile(glue_job, "lake_bronze_orders.glue_job.py", "exec")


def test_aws_render_transform_deduplicate_in_glue_job() -> None:
    artifacts = render_aws_contract(
        {
            "source": {"type": "parquet", "path": "s3://landing/orders"},
            "target": {"catalog": "lake", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
            "transform": {
                "deduplicate": {
                    "keys": ["order_id"],
                    "order_by": [{"column": "updated_at", "direction": "desc", "nulls": "last"}],
                }
            },
        }
    )

    glue_job = artifacts.artifacts["lake_bronze_orders.glue_job.py"]

    assert "from pyspark.sql import Window" in glue_job
    assert "deduplicate_keys = ['order_id']" in glue_job
    assert "Window.partitionBy(*deduplicate_keys).orderBy(F.col('updated_at').desc_nulls_last())" in glue_job
    assert "F.row_number().over(deduplicate_window)" in glue_job
    assert ".filter(F.col('__cf_row_number') == 1)" in glue_job
    assert ".drop('__cf_row_number')" in glue_job
    compile(glue_job, "lake_bronze_orders.glue_job.py", "exec")


def test_aws_render_portable_transform_in_glue_job() -> None:
    artifacts = render_aws_contract(
        {
            "source": {"type": "parquet", "path": "s3://landing/orders"},
            "target": {"catalog": "lake", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
            "transform": {
                "cast": {"amount": "double"},
                "standardize": {
                    "customer_name": {
                        "trim": True,
                        "upper": True,
                        "normalize_whitespace": True,
                        "empty_as_null": True,
                    }
                },
                "derive": {"amount_band": "CASE WHEN amount > 100 THEN 'HIGH' ELSE 'LOW' END"},
                "composite_keys": {"order_line_key": ["order_id", "line_id"]},
            },
        }
    )

    glue_job = artifacts.artifacts["lake_bronze_orders.glue_job.py"]

    assert "from pyspark.sql import functions as F" in glue_job
    assert "transform_casts = {'amount': 'double'}" in glue_job
    assert "transform.standardize references missing columns" in glue_job
    assert "transform_derive = {'amount_band': \"CASE WHEN amount > 100 THEN 'HIGH' ELSE 'LOW' END\"}" in glue_job
    assert "transform_composite_keys = {'order_line_key': ['order_id', 'line_id']}" in glue_job
    assert "F.concat_ws('|', *composite_parts)" in glue_job
    assert ".append()" in glue_job
    compile(glue_job, "lake_bronze_orders.glue_job.py", "exec")


def test_aws_render_shape_parse_json_in_glue_job() -> None:
    artifacts = render_aws_contract(
        {
            "source": {"type": "parquet", "path": "s3://landing/events"},
            "target": {"catalog": "lake", "schema": "bronze", "table": "events"},
            "mode": "scd0_append",
            "shape": {
                "parse_json": [
                    {
                        "column": "payload",
                        "schema": "struct<id:string,amount:double>",
                        "cast_input": "STRING",
                        "alias": "payload_parsed",
                        "drop_source": True,
                    }
                ]
            },
        }
    )

    glue_job = artifacts.artifacts["lake_bronze_events.glue_job.py"]

    assert "from pyspark.sql import functions as F" in glue_job
    assert (
        "df = df.withColumn('payload_parsed', F.from_json(F.col('payload').cast('string'), 'struct<id:string,amount:double>'))"
        in glue_job
    )
    assert "df = df.drop('payload')" in glue_job
    assert ".append()" in glue_job
    compile(glue_job, "lake_bronze_events.glue_job.py", "exec")


def test_aws_shape_arrays_keeps_runtime_review_only() -> None:
    artifacts = render_aws_contract(
        {
            "source": {"type": "parquet", "path": "s3://landing/events"},
            "target": {"catalog": "lake", "schema": "bronze", "table": "events"},
            "mode": "scd0_append",
            "shape": {
                "parse_json": [{"column": "payload", "schema": "struct<items:array<string>>"}],
                "arrays": [{"path": "payload.items", "mode": "explode"}],
            },
        }
    )

    assert "lake_bronze_events.glue_job.py" not in artifacts.artifacts
    outline = artifacts.artifacts["lake_bronze_events.glue_job.todo.md"]
    assert "shape" in outline


def test_aws_shape_parse_json_without_schema_stays_review_only() -> None:
    artifacts = render_aws_contract(
        {
            "source": {"type": "parquet", "path": "s3://landing/events"},
            "target": {"catalog": "lake", "schema": "bronze", "table": "events"},
            "mode": "scd0_append",
            "schemas": {"event_schema": "struct<id:string>"},
            "shape": {"parse_json": [{"column": "payload", "schema_ref": "event_schema"}]},
        }
    )

    # schema_ref resolves to a concrete schema, so this remains renderable.
    glue_job = artifacts.artifacts["lake_bronze_events.glue_job.py"]
    assert "F.from_json(F.col('payload'), 'struct<id:string>')" in glue_job


def test_aws_quality_quarantine_filters_rows_and_records_evidence() -> None:
    # not_null defaults to a soft (quarantine) severity: it now renders natively via Glue
    # Data Quality row-level outcomes: failed rows are quarantined and removed before write.
    artifacts = render_aws_contract(
        {
            "source": {"type": "parquet", "path": "s3://landing/orders"},
            "target": {"catalog": "lake", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
            "quality_rules": {"not_null": ["order_id"]},
        }
    )

    glue_job = artifacts.artifacts["lake_bronze_orders.glue_job.py"]
    compile(glue_job, "lake_bronze_orders.glue_job.py", "exec")
    assert "# Quality rules with 'quarantine' enforcement (row-level)" in glue_job
    assert "IsComplete" in glue_job  # not_null -> DQDL IsComplete
    assert "_cf_persist_quality_evidence(spark," in glue_job
    assert "ctrl_ingestion_quarantine" in glue_job
    assert "key='rowLevelOutcomes'" in glue_job
    assert "DataQualityEvaluationResult = 'Passed'" in glue_job
    assert "raise ValueError('Data quality (abort) failed: '" not in glue_job


def test_aws_merge_key_guard_runs_before_quality_quarantine() -> None:
    artifacts = render_aws_contract(
        {
            "source": {"type": "parquet", "path": "s3://landing/customers"},
            "target": {"catalog": "lake", "schema": "silver", "table": "customers"},
            "mode": "scd1_hash_diff",
            "merge_keys": ["customer_id"],
            "hash_keys": ["name", "email"],
            "quality_rules": {"not_null": ["customer_id"]},
        }
    )

    glue_job = artifacts.artifacts["lake_silver_customers.glue_job.py"]

    merge_key_guard_at = glue_job.index(
        "# Validate merge-key integrity before quality quarantine can remove offending rows."
    )
    quarantine_at = glue_job.index("# Quality rules with 'quarantine' enforcement (row-level)")
    assert merge_key_guard_at < quarantine_at
    assert "scd1_hash_diff source contains null merge_keys" in glue_job
    assert "scd1_hash_diff source contains duplicate merge_keys" in glue_job
    compile(glue_job, "lake_silver_customers.glue_job.py", "exec")


def test_aws_render_scd1_hash_diff_uses_row_hash_merge() -> None:
    artifacts = render_aws_contract(
        {
            "source": {"type": "jdbc", "url": "jdbc:postgresql://host/db", "table": "public.customers"},
            "target": {"catalog": "lake", "schema": "silver", "table": "customers"},
            "mode": "scd1_hash_diff",
            "merge_keys": ["customer_id"],
            "hash_keys": ["name", "email"],
        }
    )

    glue_job = artifacts.artifacts["lake_silver_customers.glue_job.py"]
    performance_profile = artifacts.artifacts["lake_silver_customers.performance_profile.json"]
    performance_sql = artifacts.artifacts["lake_silver_customers.performance.sql"]

    assert "lake_silver_customers.glue_job.todo.md" not in artifacts.artifacts
    assert "AWS_HASH_DIFF_PERFORMANCE_UNVALIDATED" in performance_profile
    assert "generated_job_script_bytes" in performance_profile
    assert "no_change_replay" in performance_profile
    assert "changed_row_wave" in performance_profile
    assert "concurrent_or_overlap_guard" in performance_profile
    assert "duplicate_key_failure" in performance_profile
    assert "null_key_failure" in performance_profile
    assert "ctrl_ingestion_runs" in performance_sql
    assert "ctrl_ingestion_cost" in performance_sql
    assert "glue_dpu_seconds" in performance_sql
    assert "initial_load" in performance_sql
    assert "no_change_replay" in performance_sql
    assert "changed_row_wave" in performance_sql
    assert "'glue_catalog.lake_silver.customers'" in performance_sql
    assert "from pyspark.sql import functions as F" in glue_job
    assert "merge_keys = ['customer_id']" in glue_job
    assert "declared_hash_keys = ['name', 'email']" in glue_job
    assert "resolved_hash_exclude_columns" in glue_job
    assert "for key in merge_keys" in glue_job
    assert "missing_hash_columns = [column for column in hash_keys if column not in df.columns]" in glue_job
    assert "F.sha2(F.concat_ws('\\x1f', *hash_payload), 256)" in glue_job
    assert "F.lit('\\x00')" in glue_job
    assert "contains null merge_keys" in glue_job
    assert "contains duplicate merge_keys" in glue_job
    assert "_cf_target_schema_for_write = _cf_describe_table_schema(spark, target_table)" in glue_job
    assert "_cf_writer.create()" in glue_job
    assert "target_hash_view = 'contractforge_target_hashes'" in glue_job
    assert "_cf_hash_diff_candidate_count = int(df.count())" in glue_job
    assert "globals()['_cf_hash_diff_candidate_rows'] = _cf_hash_diff_candidate_count" in glue_job
    assert "if _cf_hash_diff_candidate_count == 0:" in glue_job
    assert "_cf_skip_reason = 'no_hash_changes'" in glue_job
    assert (
        "WHEN MATCHED AND (target.{row_hash_identifier} IS NULL OR target.{row_hash_identifier} <> "
        "source.{row_hash_identifier}) THEN UPDATE SET"
    ) in glue_job
    assert "WHEN NOT MATCHED THEN INSERT ({insert_columns}) VALUES ({insert_values})" in glue_job
    compile(glue_job, "lake_silver_customers.glue_job.py", "exec")


def test_aws_render_scd1_hash_diff_honors_hash_exclusions() -> None:
    artifacts = render_aws_contract(
        {
            "source": {"type": "parquet", "path": "s3://landing/customers"},
            "target": {"catalog": "lake", "schema": "silver", "table": "customers"},
            "mode": "scd1_hash_diff",
            "merge_keys": ["customer_id"],
            "hash_keys": ["name", "ingested_at"],
            "hash_exclude_columns": ["ingested_at"],
        }
    )

    glue_job = artifacts.artifacts["lake_silver_customers.glue_job.py"]
    assert "hash_exclude_columns = ['ingested_at']" in glue_job


def test_aws_render_scd1_hash_diff_supports_all_columns_except_strategy() -> None:
    artifacts = render_aws_contract(
        {
            "source": {"type": "parquet", "path": "s3://landing/customers"},
            "target": {"catalog": "lake", "schema": "silver", "table": "customers"},
            "mode": "scd1_hash_diff",
            "merge_keys": ["customer_id"],
            "hash_strategy": "all_columns_except",
            "hash_exclude_columns": ["updated_at"],
        }
    )

    glue_job = artifacts.artifacts["lake_silver_customers.glue_job.py"]
    assert "hash_strategy = 'all_columns_except'" in glue_job
    assert "declared_hash_keys = []" in glue_job
    assert "hash_keys = df.columns if hash_strategy == 'all_columns_except' else declared_hash_keys" in glue_job
    compile(glue_job, "lake_silver_customers.glue_job.py", "exec")


def test_aws_render_scd1_hash_diff_excludes_generated_columns_from_hash() -> None:
    artifacts = render_aws_contract(
        {
            "source": {"type": "parquet", "path": "s3://landing/customers"},
            "target": {"catalog": "lake", "schema": "silver", "table": "customers"},
            "mode": "scd1_hash_diff",
            "merge_keys": ["customer_id"],
            "hash_keys": ["name", "source_loaded_at_utc", "customer_band", "customer_uid"],
            "transform": {
                "derive": {"customer_band": "CASE WHEN spend > 1000 THEN 'VIP' ELSE 'STANDARD' END"},
                "composite_keys": {"customer_uid": ["customer_id", "tenant_id"]},
            },
        }
    )

    glue_job = artifacts.artifacts["lake_silver_customers.glue_job.py"]
    assert "resolved_hash_exclude_columns" in glue_job
    assert "'source_loaded_at_utc'" in glue_job
    assert "'customer_band'" in glue_job
    assert "'customer_uid'" in glue_job
    assert "hash_excluded = set(merge_keys) | set(resolved_hash_exclude_columns)" in glue_job
    assert "hash_input_columns = [column for column in hash_keys if column not in hash_excluded]" in glue_job


def test_aws_render_scd1_hash_diff_requires_merge_keys() -> None:
    artifacts = render_aws_contract(
        {
            "source": {"type": "parquet", "path": "s3://landing/customers"},
            "target": {"catalog": "lake", "schema": "silver", "table": "customers"},
            "mode": "scd1_hash_diff",
            "hash_keys": ["name"],
        }
    ).artifacts

    assert "lake_silver_customers.glue_job.py" not in artifacts
    assert "AWS_HASH_DIFF_MERGE_KEYS_REQUIRED" in artifacts["lake_silver_customers.review.md"]
    assert "lake_silver_customers.glue_job.todo.md" in artifacts


def test_aws_review_required_scd2_gets_specific_write_mode_review() -> None:
    artifacts = render_aws_contract(
        {
            "source": {"type": "parquet", "path": "s3://landing/customers"},
            "target": {"catalog": "lake", "schema": "silver", "table": "customers"},
            "mode": "scd2_historical",
            "merge_keys": ["customer_id"],
            "scd2_sequence_by": "updated_at",
        }
    ).artifacts

    assert "lake_silver_customers.glue_job.py" not in artifacts
    review = artifacts["lake_silver_customers.write_mode_review.md"]
    assert "AWS SCD2 Historical Review" in review
    assert "REVIEW_REQUIRED" in review
    assert "late-arriving policy" in review
    assert "must not render an executable job" in review


def test_aws_review_required_snapshot_gets_specific_write_mode_review() -> None:
    artifacts = render_aws_contract(
        {
            "source": {"type": "parquet", "path": "s3://landing/customers"},
            "target": {"catalog": "lake", "schema": "silver", "table": "customers"},
            "mode": "snapshot_soft_delete",
            "merge_keys": ["customer_id"],
        }
    ).artifacts

    review = artifacts["lake_silver_customers.write_mode_review.md"]
    assert "AWS Snapshot Soft Delete Review" in review
    assert "source snapshot is complete" in review


def test_aws_adapter_rejects_unknown_subtarget() -> None:
    try:
        plan_aws_contract(
            {
                "source": {"type": "s3", "path": "s3://landing/orders", "format": "json"},
                "target": {"catalog": "lake", "schema": "bronze", "table": "orders"},
                "mode": "scd0_append",
            },
            subtarget="aws_athena_iceberg",
        )
    except ValueError as exc:
        assert "Unsupported AWS adapter subtarget" in str(exc)
    else:
        raise AssertionError("unknown AWS subtarget should fail")


def test_aws_adapter_public_class_plans_with_declared_capabilities() -> None:
    adapter = AWSAdapter.glue_iceberg()

    assert adapter.capabilities().platform == AWS_SUBTARGET_GLUE_ICEBERG


def test_aws_publish_rendered_artifacts_to_s3_uses_supplied_client() -> None:
    artifacts = render_aws_contract(
        {
            "source": {"type": "s3", "path": "s3://landing/orders", "format": "json"},
            "target": {"catalog": "lake", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
        }
    )
    client = _FakeS3Client()

    published = publish_rendered_artifacts_to_s3(
        artifacts,
        bucket="contractforge-artifacts",
        prefix="dev/orders",
        s3_client=client,
    )

    assert published
    assert published[0].uri.startswith("s3://contractforge-artifacts/dev/orders/")
    assert {call["Bucket"] for call in client.calls} == {"contractforge-artifacts"}
    assert any(call["Key"].endswith("lake_bronze_orders.glue_job.py") for call in client.calls)
    assert any(call["ContentType"].startswith("text/x-python") for call in client.calls)
    definition_call = next(call for call in client.calls if str(call["Key"]).endswith(".glue_job_definition.json"))
    definition = json.loads(definition_call["Body"].decode("utf-8"))
    assert definition["Command"]["ScriptLocation"] == (
        "s3://contractforge-artifacts/dev/orders/runtime/contractforge_aws_runner.py"
    )
    assert definition["DefaultArguments"]["--CONTRACTFORGE_CONTRACT_URI"] == (
        "s3://contractforge-artifacts/dev/orders/runtime/lake_bronze_orders.contract.json"
    )


def test_aws_publish_contract_artifacts_to_s3_public_api() -> None:
    client = _FakeS3Client()

    published = publish_aws_contract_artifacts_to_s3(
        {
            "source": {"type": "parquet", "path": "s3://landing/products"},
            "target": {"catalog": "lake", "schema": "bronze", "table": "products"},
            "mode": "scd0_overwrite",
        },
        bucket="contractforge-artifacts",
        prefix="dev/products",
        s3_client=client,
    )

    assert any(item.key.endswith("lake_bronze_products.glue_job.py") for item in published)
    assert len(client.calls) == len(published)


def test_aws_publish_contract_artifacts_to_s3_uses_environment_artifact_uri() -> None:
    client = _FakeS3Client()

    published = publish_aws_contract_artifacts_to_s3(
        {
            "source": {"type": "parquet", "path": "s3://landing/products"},
            "target": {"catalog": "lake", "schema": "bronze", "table": "products"},
            "mode": "scd0_overwrite",
        },
        environment={
            "name": "prod",
            "adapter": "aws",
            "artifacts": {
                "uri": "s3://contractforge-artifacts/prod/products/",
                "include_normalized_contract": True,
            },
        },
        s3_client=client,
    )

    assert published
    assert {call["Bucket"] for call in client.calls} == {"contractforge-artifacts"}
    assert all(str(call["Key"]).startswith("prod/products/") for call in client.calls)
    normalized = next(
        call for call in client.calls if str(call["Key"]).endswith("normalized/lake_bronze_products.contract.json")
    )
    normalized_payload = json.loads(normalized["Body"].decode("utf-8"))
    assert normalized_payload["target"]["table"] == "products"


def test_aws_publish_contract_artifacts_to_s3_requires_destination() -> None:
    with pytest.raises(ValueError, match="--bucket or environment.artifacts.uri"):
        publish_aws_contract_artifacts_to_s3(
            {
                "source": {"type": "parquet", "path": "s3://landing/products"},
                "target": {"catalog": "lake", "schema": "bronze", "table": "products"},
                "mode": "scd0_overwrite",
            }
        )


def test_aws_deploy_contract_to_glue_publishes_and_registers_payload() -> None:
    s3_client = _FakeS3Client()
    glue_client = _FakeGlueClient(existing=False)

    deployment = deploy_aws_contract_to_glue(
        {
            "source": {"type": "parquet", "path": "s3://landing/products"},
            "target": {"catalog": "lake", "schema": "bronze", "table": "products"},
            "mode": "scd0_overwrite",
        },
        environment={
            "name": "prod",
            "adapter": "aws",
            "artifacts": {"uri": "s3://contractforge-artifacts/prod/products/"},
            "parameters": {
                "aws": {"glue_job": {"role_arn": "arn:aws:iam::123456789012:role/ContractForgeGlueRole"}}
            },
        },
        s3_client=s3_client,
        glue_client=glue_client,
    )

    assert deployment.action == "created"
    assert deployment.job_name == "contractforge_lake_bronze_products"
    assert deployment.script_uri == "s3://contractforge-artifacts/prod/products/runtime/contractforge_aws_runner.py"
    assert deployment.job_definition_uri.endswith("/lake_bronze_products.glue_job_definition.json")
    assert glue_client.created["Command"]["ScriptLocation"] == deployment.script_uri
    assert any(str(call["Key"]).endswith("runtime/lake_bronze_products.contract.json") for call in s3_client.calls)
    assert any(str(call["Key"]).endswith("runtime/lake_bronze_products.environment.json") for call in s3_client.calls)
    assert any(str(call["Key"]).endswith("lake_bronze_products.glue_job.py") for call in s3_client.calls)


def test_aws_runtime_dependency_error_is_actionable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "boto3", None)

    with pytest.raises(RuntimeError, match=r"contractforge-aws\[runtime\]"):
        require_boto3()


def test_aws_build_glue_job_payload_is_explicit() -> None:
    payload = build_glue_job_payload(
        GlueJobDefinition(
            name="cf-orders",
            role_arn="arn:aws:iam::123456789012:role/ContractForgeGlueRole",
            script_s3_uri="s3://contractforge-artifacts/dev/orders/glue_job.py",
        )
    )

    assert payload["Role"] == "arn:aws:iam::123456789012:role/ContractForgeGlueRole"
    assert payload["Command"]["Name"] == "glueetl"
    assert payload["Command"]["ScriptLocation"] == "s3://contractforge-artifacts/dev/orders/glue_job.py"
    assert payload["DefaultArguments"]["--datalake-formats"] == "iceberg"
    assert (
        payload["DefaultArguments"]["--conf"]
        == "spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions"
    )
    assert payload["GlueVersion"] == "4.0"


def test_aws_build_glue_job_payload_accepts_extra_default_arguments() -> None:
    payload = build_glue_job_payload(
        GlueJobDefinition(
            name="cf-orders",
            role_arn="arn:aws:iam::123456789012:role/ContractForgeGlueRole",
            script_s3_uri="s3://contractforge-artifacts/dev/orders/glue_job.py",
            default_arguments={"--TempDir": "s3://contractforge-artifacts/temp/", "--custom": "value"},
        )
    )

    assert payload["DefaultArguments"]["--TempDir"] == "s3://contractforge-artifacts/temp/"
    assert payload["DefaultArguments"]["--custom"] == "value"
    assert payload["DefaultArguments"]["--datalake-formats"] == "iceberg"
    assert "--conf" in payload["DefaultArguments"]


def test_aws_register_glue_job_creates_when_missing() -> None:
    client = _FakeGlueClient(existing=False)

    result = register_aws_glue_job(
        job_name="cf-orders",
        role_arn="arn:aws:iam::123456789012:role/ContractForgeGlueRole",
        script_s3_uri="s3://contractforge-artifacts/dev/orders/glue_job.py",
        glue_client=client,
    )

    assert result.action == "created"
    assert client.created["Name"] == "cf-orders"
    assert client.created["Command"]["ScriptLocation"].startswith("s3://")


def test_aws_register_glue_job_updates_when_existing() -> None:
    client = _FakeGlueClient(existing=True)

    result = register_aws_glue_job(
        job_name="cf-orders",
        role_arn="arn:aws:iam::123456789012:role/ContractForgeGlueRole",
        script_s3_uri="s3://contractforge-artifacts/dev/orders/glue_job.py",
        glue_client=client,
        number_of_workers=3,
    )

    assert result.action == "updated"
    assert client.updated["JobName"] == "cf-orders"
    assert client.updated["JobUpdate"]["NumberOfWorkers"] == 3


def test_aws_register_glue_job_definition_payload_creates_when_missing() -> None:
    client = _FakeGlueClient(existing=False)

    result = register_aws_glue_job_definition_payload(
        {
            "Name": "cf-orders",
            "Role": "arn:aws:iam::123456789012:role/ContractForgeGlueRole",
            "Command": {"Name": "glueetl", "ScriptLocation": "s3://artifacts/orders.py", "PythonVersion": "3"},
            "DefaultArguments": {"--datalake-formats": "iceberg"},
            "GlueVersion": "4.0",
            "NumberOfWorkers": 2,
            "contractforge_review_notes": ["not sent to AWS"],
        },
        glue_client=client,
    )

    assert result.action == "created"
    assert client.created["Name"] == "cf-orders"
    assert client.created["Command"]["ScriptLocation"] == "s3://artifacts/orders.py"
    assert "contractforge_review_notes" not in client.created


def test_aws_register_glue_job_definition_payload_accepts_rendered_json() -> None:
    client = _FakeGlueClient(existing=False)

    result = register_aws_glue_job_definition_payload(
        json.dumps(
            {
                "Name": "cf-orders",
                "Role": "arn:aws:iam::123456789012:role/ContractForgeGlueRole",
                "Command": {"Name": "glueetl", "ScriptLocation": "s3://artifacts/orders.py"},
            }
        ),
        glue_client=client,
    )

    assert result.action == "created"
    assert client.created["Name"] == "cf-orders"


def test_aws_register_glue_job_definition_payload_preserves_connections() -> None:
    client = _FakeGlueClient(existing=False)

    register_aws_glue_job_definition_payload(
        {
            "Name": "cf-orders",
            "Role": "arn:aws:iam::123456789012:role/ContractForgeGlueRole",
            "Command": {"Name": "glueetl", "ScriptLocation": "s3://artifacts/orders.py"},
            "Connections": {"Connections": ["cf-msk-vpc"]},
        },
        glue_client=client,
    )

    assert client.created["Connections"] == {"Connections": ["cf-msk-vpc"]}


def test_aws_register_glue_job_definition_payload_updates_when_existing() -> None:
    client = _FakeGlueClient(existing=True)

    result = register_aws_glue_job_definition_payload(
        {
            "Name": "cf-orders",
            "Role": "arn:aws:iam::123456789012:role/ContractForgeGlueRole",
            "Command": {"Name": "glueetl", "ScriptLocation": "s3://artifacts/orders.py"},
            "WorkerType": "G.2X",
        },
        glue_client=client,
    )

    assert result.action == "updated"
    assert client.updated["JobName"] == "cf-orders"
    assert client.updated["JobUpdate"]["WorkerType"] == "G.2X"
    assert "Name" not in client.updated["JobUpdate"]


def test_aws_register_glue_job_definition_payload_validates_script_location() -> None:
    with pytest.raises(ValueError, match="ScriptLocation"):
        register_aws_glue_job_definition_payload(
            {
                "Name": "cf-orders",
                "Role": "arn:aws:iam::123456789012:role/ContractForgeGlueRole",
                "Command": {"Name": "glueetl", "ScriptLocation": "file:///tmp/orders.py"},
            },
            glue_client=_FakeGlueClient(existing=False),
        )


def test_aws_register_glue_job_validates_script_uri() -> None:
    with pytest.raises(ValueError, match="script_s3_uri"):
        register_aws_glue_job(
            job_name="cf-orders",
            role_arn="arn:aws:iam::123456789012:role/ContractForgeGlueRole",
            script_s3_uri="file:///tmp/glue_job.py",
            glue_client=_FakeGlueClient(existing=False),
        )


def test_aws_start_glue_job_run_returns_run_id() -> None:
    client = _FakeGlueClient(existing=True)

    result = start_aws_glue_job_run(
        job_name="cf-orders",
        arguments={"--contractforge-run-id": "run-123"},
        glue_client=client,
    )

    assert result.job_name == "cf-orders"
    assert result.run_id == "jr_123"
    assert client.started == {
        "JobName": "cf-orders",
        "Arguments": {"--contractforge-run-id": "run-123"},
    }


def test_aws_start_glue_job_run_validates_arguments() -> None:
    with pytest.raises(ValueError, match="argument values"):
        start_aws_glue_job_run(
            job_name="cf-orders",
            arguments={"--bad": 123},  # type: ignore[dict-item]
            glue_client=_FakeGlueClient(existing=True),
        )


def test_aws_start_glue_job_run_rejects_adapter_owned_argument_overrides() -> None:
    with pytest.raises(ValueError, match="managed by ContractForge"):
        start_aws_glue_job_run(
            job_name="cf-orders",
            arguments={"--job-bookmark-option": "job-bookmark-disable"},
            glue_client=_FakeGlueClient(existing=True),
        )


def test_aws_get_glue_job_run_status() -> None:
    client = _FakeGlueClient(existing=True)

    status = get_aws_glue_job_run_status(
        job_name="cf-orders",
        run_id="jr_123",
        glue_client=client,
    )

    assert status.job_name == "cf-orders"
    assert status.run_id == "jr_123"
    assert status.state == "SUCCEEDED"
    assert status.started_on == "2026-05-29 10:00:00+00:00"


def test_aws_wait_glue_job_run_returns_success_status() -> None:
    client = _FakeGlueClient(existing=True, job_run_states=["RUNNING", "SUCCEEDED"])

    status = wait_aws_glue_job_run(
        job_name="cf-orders",
        run_id="jr_123",
        glue_client=client,
        poll_interval_seconds=0,
    )

    assert status.state == "SUCCEEDED"
    assert client.status_calls == ["jr_123", "jr_123"]


def test_aws_wait_glue_job_run_raises_on_failed_status() -> None:
    client = _FakeGlueClient(existing=True, job_run_states=["FAILED"])

    with pytest.raises(RuntimeError, match="FAILED"):
        wait_aws_glue_job_run(
            job_name="cf-orders",
            run_id="jr_123",
            glue_client=client,
            poll_interval_seconds=0,
        )


def test_aws_glue_job_run_evidence_maps_core_records() -> None:
    evidence = glue_job_run_evidence(
        {
            "Id": "jr_123",
            "JobName": "cf-orders",
            "JobRunState": "SUCCEEDED",
            "StartedOn": "2026-05-29T10:00:00+00:00",
            "CompletedOn": "2026-05-29T10:05:00+00:00",
            "ExecutionTime": 300,
            "DPUSeconds": 600.0,
            "WorkerType": "G.1X",
            "NumberOfWorkers": 2,
        },
        target_table="glue.bronze.orders",
        mode="scd0_append",
    )

    assert evidence.run.run_id == "jr_123"
    assert evidence.run.status == "SUCCESS"
    assert evidence.run.metrics["metrics_source"] == "glue_jobrun"
    assert evidence.run.metrics["runtime_type"] == "aws_glue"
    assert evidence.run.metrics["duration_seconds"] == 300
    assert evidence.cost is not None
    assert evidence.cost.signal_name == "glue_dpu_seconds"
    assert evidence.cost.signal_value == 600.0


def test_aws_reconcile_glue_job_run_evidence_public_api() -> None:
    client = _FakeGlueClient(existing=True)

    evidence = reconcile_aws_glue_job_run_evidence(
        job_name="cf-orders",
        run_id="jr_123",
        target_table="glue.bronze.orders",
        mode="scd0_append",
        glue_client=client,
    )

    assert evidence.run.run_id == "jr_123"
    assert evidence.run.target_table == "glue.bronze.orders"
    assert evidence.run.status == "SUCCESS"


def test_aws_render_glue_run_evidence_sql_redacts_payload() -> None:
    evidence = glue_job_run_evidence(
        {
            "Id": "jr_123",
            "JobName": "cf-orders",
            "JobRunState": "FAILED",
            "StartedOn": "2026-05-29T10:00:00+00:00",
            "CompletedOn": "2026-05-29T10:05:00+00:00",
            "ExecutionTime": 300,
            "DPUSeconds": 600.0,
            "StateDetail": "password=super-secret",
        },
        target_table="glue.bronze.orders",
        mode="scd0_append",
    )

    sql = render_glue_run_evidence_sql(evidence, database="ops")

    assert "INSERT INTO glue_catalog.`ops`.`ctrl_ingestion_runs`" in sql
    assert "INSERT INTO glue_catalog.`ops`.`ctrl_ingestion_cost`" in sql
    assert "`metrics_json`" in sql
    assert "glue_dpu_seconds" in sql
    assert "super-secret" not in sql
    assert "***REDACTED***" in sql


def test_aws_render_glue_job_run_evidence_sql_public_api() -> None:
    client = _FakeGlueClient(existing=True)

    sql = render_aws_glue_job_run_evidence_sql(
        job_name="cf-orders",
        run_id="jr_123",
        target_table="glue.bronze.orders",
        mode="scd0_append",
        database="ops",
        glue_client=client,
    )

    assert "ctrl_ingestion_runs" in sql
    assert "jr_123" in sql


class _FakeS3Client:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def put_object(self, **kwargs) -> None:
        self.calls.append(kwargs)


class _FakeGlueClient:
    def __init__(self, *, existing: bool, job_run_states=None) -> None:
        self.existing = existing
        self.job_run_states = list(job_run_states or ["SUCCEEDED"])
        self.created: dict[str, object] = {}
        self.updated: dict[str, object] = {}
        self.started: dict[str, object] = {}
        self.status_calls: list[str] = []

    def get_job(self, *, JobName: str) -> dict[str, object]:
        if self.existing:
            return {"Job": {"Name": JobName}}
        raise _FakeGlueNotFound()

    def create_job(self, **kwargs) -> dict[str, object]:
        self.created = kwargs
        return {"Name": kwargs["Name"]}

    def update_job(self, **kwargs) -> dict[str, object]:
        self.updated = kwargs
        return {"JobName": kwargs["JobName"]}

    def start_job_run(self, **kwargs) -> dict[str, object]:
        self.started = kwargs
        return {"JobRunId": "jr_123"}

    def get_job_run(self, **kwargs) -> dict[str, object]:
        self.status_calls.append(kwargs["RunId"])
        state = self.job_run_states.pop(0) if len(self.job_run_states) > 1 else self.job_run_states[0]
        return {
            "JobRun": {
                "Id": kwargs["RunId"],
                "JobRunState": state,
                "StartedOn": "2026-05-29 10:00:00+00:00",
                "CompletedOn": "2026-05-29 10:05:00+00:00",
                "ErrorMessage": "failed" if state == "FAILED" else None,
            }
        }


class _FakeGlueNotFound(Exception):
    response = {"Error": {"Code": "EntityNotFoundException"}}
