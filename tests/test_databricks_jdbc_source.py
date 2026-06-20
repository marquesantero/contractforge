import pytest
import datetime as dt

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_databricks import DatabricksAdapter
from contractforge_databricks.sources import (
    generate_rds_iam_auth_token,
    infer_aws_region_from_rds_host,
    jdbc_options,
    parse_jdbc_host_port,
    render_jdbc_python,
)


def test_jdbc_options_from_connector_source() -> None:
    options = jdbc_options(
        {
            "type": "connector",
            "connector": "postgres",
            "url": "jdbc:postgresql://host/db",
            "table": "public.orders",
            "auth": {"type": "basic", "username": "app", "password": "{{ secret:scope/key }}"},
            "read": {"fetchsize": 1000, "partition_column": "id", "lower_bound": 1, "upper_bound": 1000, "num_partitions": 8},
        }
    )

    assert options["url"] == "jdbc:postgresql://host/db"
    assert options["dbtable"] == "public.orders"
    assert options["password"] == "{{ secret:scope/key }}"
    assert options["partitionColumn"] == "id"
    assert options["lowerBound"] == "1"
    assert options["upperBound"] == "1000"


def test_jdbc_options_rejects_table_and_query() -> None:
    with pytest.raises(ValueError, match="not both"):
        jdbc_options({"type": "jdbc", "url": "jdbc:x", "table": "t", "query": "select 1"})


def test_render_jdbc_python_rejects_inline_password() -> None:
    with pytest.raises(ValueError, match="JDBC 'password' must be provided via"):
        render_jdbc_python(
            {
                "type": "jdbc",
                "url": "jdbc:postgresql://host/db",
                "table": "public.orders",
                "auth": {"type": "basic", "username": "app", "password": "raw-password"},
            }
        )


def test_render_jdbc_python_accepts_secret_placeholder_password() -> None:
    code = render_jdbc_python(
        {
            "type": "jdbc",
            "url": "jdbc:postgresql://host/db",
            "table": "public.orders",
            "auth": {"type": "basic", "username": "app", "password": "{{ secret:scope/key }}"},
        }
    )

    assert ".format('jdbc')" in code
    assert ".option('dbtable', 'public.orders')" in code
    assert "{{ secret:scope/key }}" in code
    assert "***REDACTED***" in code


def test_jdbc_options_rejects_inline_credentials_in_url() -> None:
    with pytest.raises(ValueError, match="JDBC url embeds inline credentials"):
        jdbc_options({"type": "jdbc", "url": "jdbc:postgresql://user:password@host/db", "table": "public.orders"})


def test_jdbc_options_support_rds_iam_review_boundary() -> None:
    options = jdbc_options(
        {
            "type": "jdbc",
            "url": "jdbc:postgresql://orders.abc123.us-east-1.rds.amazonaws.com:5432/app",
            "table": "public.orders",
            "auth": {"type": "rds_iam", "username": "app_user"},
        }
    )

    assert options["user"] == "app_user"
    assert options["password"] == "{{rds_iam_token}}"
    assert options["ssl"] == "true"
    assert options["sslmode"] == "require"
    assert options["contractforge.rdsIamRegion"] == "us-east-1"


def test_rds_iam_helpers_parse_region_and_generate_deterministic_token() -> None:
    host, port = parse_jdbc_host_port("jdbc:postgresql://orders.abc123.us-east-1.rds.amazonaws.com/app")
    token = generate_rds_iam_auth_token(
        host=host,
        port=port,
        region=infer_aws_region_from_rds_host(host) or "",
        username="app_user",
        access_key="AKIDEXAMPLE",
        secret_key="wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY",
        now=dt.datetime(2026, 1, 2, 3, 4, 5, tzinfo=dt.timezone.utc),
    )

    assert host == "orders.abc123.us-east-1.rds.amazonaws.com"
    assert port == 5432
    assert "X-Amz-Algorithm=AWS4-HMAC-SHA256" in token
    assert "X-Amz-Date=20260102T030405Z" in token
    assert "X-Amz-Signature=" in token


def test_databricks_bundle_renders_jdbc_source_artifact() -> None:
    adapter = DatabricksAdapter.from_evidence(
        target_table="main.bronze.orders",
        runtime_type="serverless",
        spark_conf={"spark.databricks.serverless.enabled": "true"},
    )
    contract = semantic_contract_from_mapping(
        {
            "source": {
                "type": "connector",
                "connector": "postgres",
                "url": "jdbc:postgresql://host/db",
                "table": "public.orders",
            },
            "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
        }
    )

    artifacts = adapter.render_contract(contract)

    assert "main_bronze_orders.source_jdbc.py" in artifacts.artifacts
