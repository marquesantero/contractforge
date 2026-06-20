"""AWS Glue job-bookmark rendering for incremental_files sources."""

from __future__ import annotations

from contractforge_aws import register_aws_glue_job, render_aws_contract
from contractforge_aws.runtime import GlueJobDefinition, build_glue_job_payload
from contractforge_aws.sources import (
    glue_incremental_file_format_options,
    interpret_incremental_files_source,
    is_incremental_file_source,
)


def _incremental_contract(extra_source: dict | None = None) -> dict:
    source = {"type": "incremental_files", "path": "s3://landing/orders", "format": "json"}
    source.update(extra_source or {})
    return {
        "source": source,
        "target": {"catalog": "lake", "schema": "bronze", "table": "orders"},
        "mode": "scd0_append",
    }


def test_incremental_files_renders_glue_bookmark_read() -> None:
    artifacts = render_aws_contract(_incremental_contract())
    glue_job = artifacts.artifacts["lake_bronze_orders.glue_job.py"]

    assert "glue_context.create_dynamic_frame.from_options(" in glue_job
    assert "connection_type='s3'" in glue_job
    assert "format='json'" in glue_job
    assert "'paths': ['s3://landing/orders']" in glue_job
    assert "transformation_ctx='cf_incremental_files'" in glue_job
    assert ".toDF()" in glue_job
    assert "job-bookmark-option" in glue_job  # guidance comment
    # A full-scan spark.read must not be used for an incremental source.
    assert "spark.read" not in glue_job
    compile(glue_job, "lake_bronze_orders.glue_job.py", "exec")


def test_file_stream_intent_renders_glue_bookmark_read() -> None:
    contract = _incremental_contract(
        {
            "type": "s3",
            "intent": "file_stream",
            "path": "s3://landing/orders",
            "format": "json",
        }
    )
    artifacts = render_aws_contract(contract)
    glue_job = artifacts.artifacts["lake_bronze_orders.glue_job.py"]

    assert is_incremental_file_source(contract["source"]) is True
    assert interpret_incremental_files_source(contract["source"])["type"] == "incremental_files"
    assert "glue_context.create_dynamic_frame.from_options(" in glue_job
    assert "'paths': ['s3://landing/orders']" in glue_job
    assert "transformation_ctx='cf_incremental_files'" in glue_job
    assert "spark.read" not in glue_job


def test_jdbc_incremental_renders_glue_bookmark_read_and_deployment_flag() -> None:
    artifacts = render_aws_contract(
        {
            "source": {
                "type": "jdbc",
                "url": "jdbc:postgresql://orders.example.com/app",
                "table": "public.orders",
                "incremental": {"watermark_column": "updated_at", "sort_order": "asc"},
            },
            "target": {"catalog": "lake", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
        }
    ).artifacts
    glue_job = artifacts["lake_bronze_orders.glue_job.py"]
    definition = artifacts["lake_bronze_orders.glue_job_definition.json"]

    assert "glue_context.create_dynamic_frame.from_options(" in glue_job
    assert "connection_type='postgresql'" in glue_job
    assert "'jobBookmarkKeys': ['updated_at']" in glue_job
    assert "'jobBookmarkKeysSortOrder': 'asc'" in glue_job
    assert "transformation_ctx='cf_jdbc_bookmark'" in glue_job
    assert "spark.read" not in glue_job
    assert '"--job-bookmark-option": "job-bookmark-enable"' in definition
    compile(glue_job, "lake_bronze_orders.glue_job.py", "exec")


def test_plain_jdbc_keeps_spark_jdbc_reader() -> None:
    artifacts = render_aws_contract(
        {
            "source": {"type": "jdbc", "url": "jdbc:postgresql://orders.example.com/app", "table": "public.orders"},
            "target": {"catalog": "lake", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
        }
    ).artifacts
    glue_job = artifacts["lake_bronze_orders.glue_job.py"]

    assert "spark.read" in glue_job
    assert "cf_jdbc_bookmark" not in glue_job


def test_incremental_files_with_custom_options_renders_format_options() -> None:
    artifacts = render_aws_contract(_incremental_contract({"options": {"multiLine": "true"}}))
    glue_job = artifacts.artifacts["lake_bronze_orders.glue_job.py"]

    assert "format_options={'multiLine': True}" in glue_job
    assert "transformation_ctx='cf_incremental_files'" in glue_job
    compile(glue_job, "lake_bronze_orders.glue_job.py", "exec")


def test_incremental_csv_options_translate_to_glue_dynamic_frame_options() -> None:
    source = {
        "type": "incremental_files",
        "path": "s3://landing/orders",
        "format": "csv",
        "options": {"header": True, "inferSchema": True, "delimiter": ";"},
    }
    artifacts = render_aws_contract(_incremental_contract(source))
    glue_job = artifacts.artifacts["lake_bronze_orders.glue_job.py"]

    assert glue_incremental_file_format_options(source) == {"separator": ";", "withHeader": True}
    assert "format_options={'separator': ';', 'withHeader': True}" in glue_job
    assert "format_options={'delimiter': ';'" not in glue_job
    assert "format_options={'header': True" not in glue_job
    compile(glue_job, "lake_bronze_orders.glue_job.py", "exec")


def test_incremental_files_renders_no_input_skip_before_preparation() -> None:
    artifacts = render_aws_contract(
        {
            "source": {
                "type": "incremental_files",
                "path": "s3://landing/orders",
                "format": "csv",
                "options": {"header": True},
            },
            "target": {"catalog": "lake", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
            "transform": {"cast": {"order_id": "string"}},
        }
    )
    glue_job = artifacts.artifacts["lake_bronze_orders.glue_job.py"]

    assert "_cf_no_input_skip = len(df.columns) == 0" in glue_job
    assert "_cf_run_status = 'SKIPPED'" in glue_job
    assert "_cf_skip_reason = 'no_new_input'" in glue_job
    assert glue_job.index("_cf_no_input_skip = len(df.columns) == 0") < glue_job.index("df = df.withColumn")
    assert "if not _cf_no_input_skip:" in glue_job
    assert "globals().get('_cf_run_status', 'SUCCESS')" in glue_job
    assert "globals().get('_cf_skip_reason')" in glue_job
    compile(glue_job, "lake_bronze_orders.glue_job.py", "exec")


def test_incremental_files_with_unsupported_format_stays_review_only() -> None:
    artifacts = render_aws_contract(_incremental_contract({"format": "text"}))

    assert "lake_bronze_orders.glue_job.py" not in artifacts.artifacts
    assert "lake_bronze_orders.glue_job.todo.md" in artifacts.artifacts


def test_incremental_files_plan_warns_about_bookmark_enablement() -> None:
    from contractforge_aws import plan_aws_contract

    result = plan_aws_contract(_incremental_contract())

    assert result.status == "SUPPORTED_WITH_WARNINGS"
    codes = {warning.code for warning in result.warnings}
    assert "AWS_INCREMENTAL_FILES_STRATEGY_REVIEW" in codes


def test_glue_job_payload_enables_bookmark_when_requested() -> None:
    enabled = build_glue_job_payload(
        GlueJobDefinition(
            name="cf-orders",
            role_arn="arn:aws:iam::123456789012:role/Role",
            script_s3_uri="s3://artifacts/glue_job.py",
            enable_job_bookmark=True,
        )
    )
    disabled = build_glue_job_payload(
        GlueJobDefinition(
            name="cf-orders",
            role_arn="arn:aws:iam::123456789012:role/Role",
            script_s3_uri="s3://artifacts/glue_job.py",
        )
    )

    assert enabled["DefaultArguments"]["--job-bookmark-option"] == "job-bookmark-enable"
    assert disabled["DefaultArguments"]["--job-bookmark-option"] == "job-bookmark-disable"


def test_register_glue_job_propagates_bookmark_flag() -> None:
    class _Glue:
        def __init__(self) -> None:
            self.created: dict = {}

        def get_job(self, *, JobName: str):
            raise _NotFound()

        def create_job(self, **kwargs):
            self.created = kwargs
            return {"Name": kwargs["Name"]}

    class _NotFound(Exception):
        response = {"Error": {"Code": "EntityNotFoundException"}}

    client = _Glue()
    register_aws_glue_job(
        job_name="cf-orders",
        role_arn="arn:aws:iam::123456789012:role/Role",
        script_s3_uri="s3://artifacts/glue_job.py",
        glue_client=client,
        enable_job_bookmark=True,
    )

    assert client.created["DefaultArguments"]["--job-bookmark-option"] == "job-bookmark-enable"
