"""Secret-safety guarantees for AWS Glue artifact rendering."""

from __future__ import annotations

import pytest

from contractforge_aws import render_aws_contract
from contractforge_aws.security import (
    assert_no_inline_jdbc_secrets,
    contains_secret_placeholder,
    render_secret_aware_literal,
    render_secret_resolver_helper,
    secret_placeholder_refs,
    validate_source_security,
)


def _jdbc_contract(password: str) -> dict:
    return {
        "source": {
            "type": "jdbc",
            "url": "jdbc:postgresql://db.internal:5432/app",
            "table": "public.customers",
            "auth": {"type": "basic", "username": "svc_reader", "password": password},
        },
        "target": {"catalog": "lake", "schema": "silver", "table": "customers"},
        "mode": "scd1_upsert",
        "merge_keys": ["customer_id"],
    }


def test_secret_placeholder_resolves_to_runtime_lookup_not_literal() -> None:
    artifacts = render_aws_contract(_jdbc_contract("{{ secret:rds_app/password }}"))
    glue_job = artifacts.artifacts["lake_silver_customers.glue_job.py"]

    assert "_cf_resolve_secret('rds_app', 'password')" in glue_job
    assert "import boto3" in glue_job
    assert "import json" in glue_job
    assert "boto3.client('secretsmanager')" in glue_job
    # The placeholder itself must not survive into the published artifact.
    assert "{{ secret:rds_app/password }}" not in glue_job
    compile(glue_job, "glue_job.py", "exec")


def test_review_comment_redacts_options() -> None:
    artifacts = render_aws_contract(_jdbc_contract("{{ secret:rds_app/password }}"))
    glue_job = artifacts.artifacts["lake_silver_customers.glue_job.py"]

    review_line = next(line for line in glue_job.splitlines() if line.lstrip().startswith("# {"))
    assert "***REDACTED***" in review_line
    assert "rds_app/password" not in review_line


def test_inline_password_is_refused() -> None:
    with pytest.raises(ValueError, match="secret:scope/key"):
        render_aws_contract(_jdbc_contract("super-secret-password"))


def test_inline_url_credentials_are_refused() -> None:
    contract = {
        "source": {
            "type": "jdbc",
            "url": "jdbc:postgresql://svc:hunter2@db.internal:5432/app",
            "table": "public.customers",
        },
        "target": {"catalog": "lake", "schema": "silver", "table": "customers"},
        "mode": "scd0_append",
    }
    with pytest.raises(ValueError, match="inline credentials"):
        render_aws_contract(contract)


def test_jdbc_without_secrets_does_not_inject_boto3() -> None:
    artifacts = render_aws_contract(
        {
            "source": {"type": "jdbc", "url": "jdbc:postgresql://host/db", "table": "public.orders"},
            "target": {"catalog": "lake", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
        }
    )
    glue_job = artifacts.artifacts["lake_bronze_orders.glue_job.py"]

    assert "import boto3" not in glue_job
    assert "_cf_resolve_secret" not in glue_job
    compile(glue_job, "glue_job.py", "exec")


def test_render_secret_aware_literal_handles_plain_and_embedded() -> None:
    assert render_secret_aware_literal("plain") == "'plain'"
    expr = render_secret_aware_literal("prefix-{{ secret:scope/key }}-suffix")
    assert expr == "'prefix-' + _cf_resolve_secret('scope', 'key') + '-suffix'"


def test_contains_secret_placeholder_is_recursive() -> None:
    assert contains_secret_placeholder({"auth": {"password": "{{ secret:s/k }}"}})
    assert not contains_secret_placeholder({"auth": {"username": "svc"}})


def test_secret_placeholder_refs_extracts_scope_and_key() -> None:
    refs = secret_placeholder_refs("{{ secret:scope/key }} and {{ secret:other/value }}")
    assert refs == (("scope", "key"), ("other", "value"))


def test_assert_no_inline_jdbc_secrets_passes_for_placeholder() -> None:
    assert_no_inline_jdbc_secrets({"password": "{{ secret:s/k }}", "user": "svc"})


def test_validate_source_security_rejects_jdbc_inline_password() -> None:
    with pytest.raises(ValueError, match="secret:scope/key"):
        validate_source_security(
            {
                "type": "jdbc",
                "url": "jdbc:postgresql://host/db",
                "table": "public.orders",
                "auth": {"type": "basic", "username": "svc", "password": "raw-password"},
            }
        )


def test_validate_source_security_accepts_non_executable_file_source() -> None:
    validate_source_security({"type": "s3", "path": "s3://bucket/orders", "format": "parquet"})


def test_validate_source_security_rejects_inline_sensitive_http_headers() -> None:
    with pytest.raises(ValueError, match="request.headers.Authorization"):
        validate_source_security(
            {
                "type": "rest_api",
                "request": {"url": "https://api.example.com/orders", "headers": {"Authorization": "Bearer raw"}},
            }
        )


def test_validate_source_security_accepts_secret_http_headers() -> None:
    validate_source_security(
        {
            "type": "rest_api",
            "request": {
                "url": "https://api.example.com/orders",
                "headers": {"Authorization": "Bearer {{ secret:api/token }}"},
            },
        }
    )


def test_validate_source_security_rejects_inline_http_auth_api_key() -> None:
    with pytest.raises(ValueError, match="auth.api_key"):
        validate_source_security(
            {
                "type": "rest_api",
                "request": {"url": "https://api.example.com/orders"},
                "auth": {"type": "api_key", "api_key": "raw-key"},
            }
        )


def test_validate_source_security_rejects_inline_http_cookie_header() -> None:
    with pytest.raises(ValueError, match="request.headers.Cookie"):
        validate_source_security(
            {
                "type": "http_json",
                "url": "https://api.example.com/orders.json",
                "request": {"headers": {"Cookie": "session=raw"}},
            }
        )


def test_resolver_helper_is_valid_python() -> None:
    compile(render_secret_resolver_helper(), "helper.py", "exec")


def test_file_source_secret_option_resolves_at_runtime() -> None:
    artifacts = render_aws_contract(
        {
            "source": {
                "type": "csv",
                "path": "s3://landing/orders",
                "format": "csv",
                "options": {"someConnectionToken": "{{ secret:ext_api/token }}"},
            },
            "target": {"catalog": "lake", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
        }
    )
    glue_job = artifacts.artifacts["lake_bronze_orders.glue_job.py"]

    assert "_cf_resolve_secret('ext_api', 'token')" in glue_job
    assert "import boto3" in glue_job
    assert "{{ secret:ext_api/token }}" not in glue_job
    compile(glue_job, "glue_job.py", "exec")


def test_plain_file_source_is_unchanged_and_has_no_resolver() -> None:
    artifacts = render_aws_contract(
        {
            "source": {"type": "parquet", "path": "s3://landing/orders"},
            "target": {"catalog": "lake", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
        }
    )
    glue_job = artifacts.artifacts["lake_bronze_orders.glue_job.py"]

    assert ".load('s3://landing/orders')" in glue_job
    assert "_cf_resolve_secret" not in glue_job
    assert "import boto3" not in glue_job


def test_iceberg_table_properties_reject_secret_placeholders() -> None:
    with pytest.raises(ValueError, match="table_properties must not contain secret placeholders"):
        render_aws_contract(
            {
                "source": {"type": "parquet", "path": "s3://landing/orders"},
                "target": {"catalog": "lake", "schema": "bronze", "table": "orders"},
                "mode": "scd0_append",
                "extensions": {
                    "aws": {
                        "iceberg": {
                            "table_properties": {
                                "s3.secret": "{{ secret:iceberg/key }}",
                            }
                        }
                    }
                },
            }
        )
