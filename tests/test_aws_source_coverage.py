"""AWS source-connector coverage: unsupported sources route to review, not crash."""

from __future__ import annotations

import json

import pytest

from contractforge_aws import render_aws_contract, render_aws_native_passthrough_plan
from contractforge_aws.sources import aws_source_support, can_render_source, render_native_passthrough_plan


def _contract(source: dict) -> dict:
    return {
        "source": source,
        "target": {"catalog": "lake", "schema": "bronze", "table": "t"},
        "mode": "scd0_append",
    }


@pytest.mark.parametrize(
    "source",
    [
        {"type": "native_passthrough", "system": "salesforce"},
    ],
)
def test_unsupported_source_routes_to_review_outline(source: dict) -> None:
    artifacts = render_aws_contract(_contract(source))
    assert "lake_bronze_t.glue_job.py" not in artifacts.artifacts
    outline = artifacts.artifacts["lake_bronze_t.glue_job.todo.md"]
    assert "source connector is not rendered by the AWS adapter yet" in outline
    assert "`rest_api`" in outline
    assert "`native_passthrough` remains review-only" in outline


@pytest.mark.parametrize(
    "source,expected",
    [
        ({"type": "jdbc", "url": "jdbc:postgresql://h/db", "table": "public.t"}, True),
        ({"type": "parquet", "path": "s3://b/o"}, True),
        ({"type": "s3", "path": "s3://b/o", "format": "json"}, True),
        ({"type": "delta", "path": "s3://b/delta"}, True),
        ({"type": "gcs", "path": "gs://b/o", "format": "json"}, True),
        ({"type": "table", "table": "cat.sch.t"}, True),
        ({"type": "incremental_files", "path": "s3://b/o", "format": "json"}, True),
        ({"type": "http_json", "request": {"url": "https://api.example.com/x"}}, True),
        ({"type": "kafka_bounded", "bootstrap_servers": "b:9092", "topic": "t"}, True),
        ({"type": "delta_share", "profile_file": "s3://x/p", "table": "a.b.c"}, True),
        ({"type": "rest_api", "request": {"url": "https://api.example.com/x"}}, True),
        ({"type": "native_passthrough", "system": "salesforce"}, False),
    ],
)
def test_can_render_source_matches_renderer(source: dict, expected: bool) -> None:
    assert can_render_source(source) is expected


def test_file_sources_that_need_glue_runtime_configuration_are_warned() -> None:
    delta = aws_source_support({"type": "delta", "path": "s3://bucket/table"})
    gcs = aws_source_support({"type": "gcs", "path": "gs://bucket/orders", "format": "json"})

    assert delta["status"] == "SUPPORTED_WITH_WARNINGS"
    assert gcs["status"] == "SUPPORTED_WITH_WARNINGS"
    assert delta["native_mapping"] == "Spark file reader in Glue with runtime connector configuration"


def test_render_native_passthrough_plan_recommends_aws_native_services() -> None:
    payload = json.loads(
        render_native_passthrough_plan(
            {
                "type": "native_passthrough",
                "system": "salesforce",
                "object": "Account",
                "watermark": {"column": "SystemModstamp"},
                "auth": {"client_secret": "secret-value"},
            }
        )
    )

    assert payload["kind"] == "aws_native_passthrough_plan"
    assert payload["status"] == "REVIEW_REQUIRED"
    assert payload["auth"]["client_secret"] == "<redacted>"
    assert payload["recommended_aws_targets"] == ["appflow", "glue_native_connector"]
    assert payload["recommended_aws_paths"][0]["service"] == "Amazon AppFlow"
    assert payload["review_only_apply_candidates"][0]["aws_api"] == "appflow:CreateFlow"
    assert payload["review_only_apply_candidates"][0]["draft_request"]["flowName"] == "cf-salesforce-account"
    assert payload["review_only_apply_candidates"][1]["aws_api"] == "glue:CreateConnection"
    assert payload["contract_mapping"]["source.watermark"] == {"column": "SystemModstamp"}
    assert "AppFlow connector profile" in payload["review_required_inputs"]
    assert "This artifact does not execute AppFlow, DMS or Glue connector APIs." in payload["unsupported_claims"]


def test_render_native_passthrough_plan_recommends_dms_for_database_replication() -> None:
    payload = json.loads(
        render_native_passthrough_plan(
            {"type": "native_passthrough", "system": "postgres", "object": "public.orders"}
        )
    )

    assert payload["recommended_aws_targets"] == ["dms", "glue_jdbc"]
    assert payload["recommended_aws_paths"][0]["service"] == "AWS Database Migration Service"
    assert payload["review_only_apply_candidates"][0]["aws_api"] == "dms:CreateReplicationConfig"
    assert payload["review_only_apply_candidates"][0]["draft_request"]["TableMappings"]["rules"][0][
        "object-locator"
    ] == {"schema-name": "public", "table-name": "orders"}
    assert "DMS endpoint settings" in payload["review_required_inputs"]


def test_render_native_passthrough_plan_keeps_unknown_systems_review_only() -> None:
    payload = json.loads(
        render_native_passthrough_plan(
            {"type": "native_passthrough", "system": "custom_crm", "object": "Account"}
        )
    )

    assert payload["recommended_aws_targets"] == [
        "glue_custom_connector",
        "appflow_if_supported",
        "dms_if_database_replication",
    ]
    assert payload["recommended_aws_paths"][0]["service"] == "AWS Glue custom connector"
    assert "AppFlow application availability" in payload["review_required_inputs"]
    assert "DMS source/target support proof" in payload["review_required_inputs"]


def test_render_native_passthrough_plan_preserves_redacted_string_contract() -> None:
    plan = render_native_passthrough_plan(
        {
            "type": "native_passthrough",
            "system": "salesforce",
            "object": "Account",
            "watermark": {"column": "SystemModstamp"},
            "auth": {"client_secret": "secret-value"},
        }
    )

    assert '"kind": "aws_native_passthrough_plan"' in plan
    assert '"status": "REVIEW_REQUIRED"' in plan
    assert '"appflow"' in plan
    assert '"glue_native_connector"' in plan
    assert '"client_secret": "<redacted>"' in plan


def test_adapter_bundle_includes_native_passthrough_plan_when_descriptor_is_complete() -> None:
    artifacts = render_aws_contract(
        _contract({"type": "native_passthrough", "system": "salesforce", "object": "Account"})
    ).artifacts

    assert "lake_bronze_t.native_passthrough.json" in artifacts
    assert '"appflow"' in artifacts["lake_bronze_t.native_passthrough.json"]


def test_public_native_passthrough_renderer_validates_subtarget() -> None:
    plan = render_aws_native_passthrough_plan(
        {"type": "native_passthrough", "system": "postgres", "object": "public.orders"}
    )

    assert '"dms"' in plan
    assert '"glue_jdbc"' in plan
